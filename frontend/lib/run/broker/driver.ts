// The scripted parties for a live demo order: Summit's buying agent, our provider and investigator
// seats act against Jeff's backend on a timer while the canvas watches the event stream. Only
// the controller's decision is a human click (see the decisions route).
import { createHash } from "node:crypto";
import { ROWS, S, type Case } from "../scenario";
import { BrokerError, createDraft, draftCommand, events as brokerEvents, getOrder, orderCommand, session, uploadSource, type Role } from "./client";
import type { BrokerOrder } from "./types";

/** Summit's moves. The presenter makes them from the customer view; the driver waits for each. */
export type BuyerMove = { action: "approve" } | { action: "accept" } | { action: "object"; text: string };
export type BuyerGate = "approve" | "review"; // what the run is waiting for: contract approval, or accept / object

export interface Run {
  id: string; // the broker entity id, once the draft exists
  case: Case;
  tokens: Record<Role, string>;
  error?: string;
  finished: boolean;
  awaiting: BuyerGate | null;
  move: ((m: BuyerMove) => void) | null;
  /** Resolves once the parties have supplied everything a controller decision needs (the clarification, in the grey case). */
  ready: Promise<void>;
  markReady: () => void;
}

/** Pauses the scripted parties until the presenter, as Summit, makes a move of the right kind. */
function waitBuyer(run: Run, gate: BuyerGate): Promise<BuyerMove> {
  return new Promise((resolve) => { run.awaiting = gate; run.move = (m) => { run.awaiting = null; run.move = null; resolve(m); }; });
}
export function buyerMove(run: Run, m: BuyerMove): { status: number; detail?: string } {
  const ok = run.awaiting === "approve" ? m.action === "approve" : run.awaiting === "review" ? m.action !== "approve" : false;
  if (!ok || !run.move) return { status: 409, detail: run.awaiting ? `The order is waiting for Summit to ${run.awaiting === "approve" ? "approve the contract" : "accept or object"}` : "The order is not waiting on Summit right now" };
  run.move(m);
  return { status: 200 };
}

const key = () => crypto.randomUUID();
const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));
const PACE = 1400; // between party actions, so the canvas can follow
const ANSWER = 500; // between Summit's intake answers: the interview is the agent at work, not the moment to read along
// market-v1 takes numeric values only, so the suppressed ZIP stays out of the vendor panel and the coverage
const SOURCE_ROWS = ROWS.flatMap((r) => (r.count === null ? [] : [{ zip: r.zip, count: r.count }]));

/** Our order in the backend's parameters: SF ZIPs, a fitness-interest metric, no missing records. */
export function parameters(now: Date) {
  const zips = SOURCE_ROWS.map((r) => r.zip);
  return {
    freshness_basis: "observed_at", max_age_days: 90, as_of: now.toISOString(),
    geography: "San Francisco", boundary_version: "2026-Q3", region_ids: zips,
    reference_period: "2026-Q3", metric_name: "adults_25_34_interested_in_fitness", metric_unit: "people",
    entity_unit: "region", coverage_ids: zips, max_missing_records: 0,
    revision_policy: "exact_accepted_versions", conflict_policy: "UNKNOWN", output_schema: "market-v1", output_format: "json",
  } as Record<string, unknown>;
}

/** The vendor panel as a source snapshot. Version 1 carries the case's flaw; version 2 is clean. */
export function sourceSnapshot(c: Case, version = 1) {
  const flawed = version === 1;
  const rows = SOURCE_ROWS
    .filter((r) => !(flawed && c === "red" && r.zip === "94110")) // the vendor's list lacks the Mission ZIP
    .map((r) => ({ entity_id: r.zip, region_id: r.zip, value: r.count, observed_at: flawed && c === "amber" && r.zip === "94110" ? null : "2026-10-10T00:00:00Z" }));
  return {
    source_id: "vendor-fitness-panel", version, geography: "San Francisco", boundary_version: "2026-Q3", reference_period: "2026-Q3",
    metric_name: "adults_25_34_interested_in_fitness", metric_unit: "people", entity_unit: "region",
    published_at: "2026-10-20T00:00:00Z", exported_at: "2026-10-24T00:00:00Z", rows,
  };
}
const bytes = (v: unknown) => Buffer.from(JSON.stringify(v));

/** Runs the scripted parties for one case. Resolves when the parties have nothing left to do. */
export async function drive(run: Run, onId: (id: string) => void): Promise<void> {
  const t = run.tokens;
  const now = new Date();
  const params = parameters(now);
  try {
    let d = await createDraft(t.customer, { idempotency_key: key(), intent: `${S.order}, for an ad campaign.` });
    run.id = d.id; onId(d.id);
    await sleep(PACE);
    d = (await uploadSource(t.provider, "drafts", d.id, { idempotency_key: key(), expected_revision: d.revision, filename: "vendor-fitness-panel.json", content_base64: bytes(sourceSnapshot(run.case)).toString("base64") })) as typeof d;
    const cmd = async (who: Role, body: Record<string, unknown>) => { d = await draftCommand(t[who], d.id, { idempotency_key: key(), expected_revision: d.revision, ...body }); };
    for (const q of [...d.questions]) if (q.answer_id === null) { await sleep(ANSWER); await cmd("customer", { verb: "answer_intake", question_id: q.id, value: params[q.field] }); }
    for (const field of [...d.unresolved_fields]) {
      await cmd("controller", { verb: "clarify_intake", field });
      const q = [...d.questions].reverse().find((q) => q.field === field)!;
      await sleep(ANSWER); await cmd("customer", { verb: "answer_intake", question_id: q.id, value: params[field] });
    }
    await sleep(PACE);
    await cmd("provider", { verb: "offer", capability: "SUPPORTED", price: { amount_minor: S.price * 100, currency: "USDSIM", decimals: 2 } });
    await waitBuyer(run, "approve");
    await cmd("customer", { verb: "accept_specification", digest: d.acceptance_digest, authorization_expires_at: new Date(now.getTime() + 2 * 3_600_000).toISOString() });
    const oid = d.order_id!;
    const ocmd = async (who: Role, body: Record<string, unknown>) => { const cur = await getOrder(t[who], oid); return orderCommand(t[who], oid, { idempotency_key: key(), expected_revision: cur.revision, ...body }); };
    await sleep(PACE * 1.5);
    let o = await ocmd("provider", { verb: "produce" });
    await sleep(PACE * 2);
    if (run.case === "shared" || run.case === "green") {
      await reviewGate(run, oid, ocmd);
    } else if (run.case === "red") {
      // The first check failed on coverage: the vendor's revision lacked 94110. The complete
      // revision, accepted by both sides as a clarification, lets the free correction pass.
      await sleep(PACE * 1.5);
      await clarifyWithRevision(run, oid, 2);
      await finish(run, oid, ocmd);
    } else if (run.case === "amber") {
      // The engine asks the provider; the provider answers twice; the case goes to the controller.
      for (let round = 0; round < 2; round++) {
        const q = (await getOrder(t.provider, oid)).questions.find((q) => q.status === "OPEN");
        if (!q) break;
        await sleep(PACE * 1.5);
        o = await ocmd(q.recipient, { verb: "answer", question_id: q.id, text: round === 0 ? "Our panel has no observation date for 94110 this quarter; the vendor files it under a different category." : "The category is the vendor's choice, not a data error." });
      }
      // Both sides accept the dated revision while the controller holds the case; her resume
      // then rechecks the delivery against it.
      await sleep(PACE);
      await clarifyWithRevision(run, oid, 2);
      run.markReady();
      await finish(run, oid, ocmd);
    }
  } catch (err) {
    run.error = err instanceof BrokerError ? `Backend answered ${err.status}: ${err.detail}` : err instanceof Error ? err.message : String(err);
    console.error(`[broker-run] ${run.case} ${run.id}: ${run.error}`);
  } finally {
    run.finished = true;
    run.markReady(); // never leave a decision waiting on a run that stopped
  }
}

/** The provider supplies a new source revision; both parties accept it as a clarification of the spec. */
async function clarifyWithRevision(run: Run, oid: string, version: number) {
  const t = run.tokens;
  const raw = bytes(sourceSnapshot(run.case, version));
  let cur = await getOrder(t.provider, oid);
  await uploadSource(t.provider, "orders", oid, { idempotency_key: key(), expected_revision: cur.revision, filename: `vendor-fitness-panel-v${version}.json`, content_base64: raw.toString("base64") });
  await sleep(PACE);
  cur = await getOrder(t.customer, oid);
  const spec = { ...cur.original_specification!, version, sources: [{ source_id: "vendor-fitness-panel", version, sha256: createHash("sha256").update(raw).digest("hex") }] };
  const effective = new Date(Date.now() + 2000).toISOString();
  const proposed = await orderCommand(t.customer, oid, { idempotency_key: key(), expected_revision: cur.revision, verb: "propose_amendment", specification: spec, effective_at: effective });
  const amendment = proposed.amendments?.at(-1);
  if (!amendment) throw new Error("The backend did not record the proposed amendment");
  for (const who of ["customer", "provider"] as Role[]) {
    await sleep(PACE * 0.6);
    cur = await getOrder(t[who], oid);
    await orderCommand(t[who], oid, { idempotency_key: key(), expected_revision: cur.revision, verb: "accept_amendment", amendment_id: amendment.id, digest: amendment.digest });
  }
  await sleep(2500); // past the amendment's effective time
}

type Cmd = (who: Role, body: Record<string, unknown>) => Promise<BrokerOrder>;

/** Delivered: Summit accepts, or objects in their own words and the agent answers by the contract. */
async function reviewGate(run: Run, oid: string, ocmd: Cmd) {
  let move = await waitBuyer(run, "review");
  if (move.action === "object") {
    await ocmd("customer", { verb: "dispute", text: move.text });
    await sleep(PACE * 2); // long enough to watch the orb walk to the source on the canvas
    const o = await ocmd("investigator", { verb: "investigate" });
    if (o.resolution !== "NO_REMEDY") return finish(run, oid, ocmd); // the objection was right: the engine corrects
    move = await waitBuyer(run, "review");
  }
  if (move.action === "accept") await ocmd("customer", { verb: "accept_delivery" });
}

/** After the parties' last move: produce the free correction when the engine allows it, then Summit reviews. */
async function finish(run: Run, oid: string, ocmd: Cmd): Promise<void> {
  let produced = false;
  for (let i = 0; i < 600; i++) {
    const o = await getOrder(run.tokens.customer, oid);
    const b = o.base_order?.order;
    if (!b) return;
    if (b.order_state === "processing" && b.regeneration_pending && b.binding && !produced) { produced = true; await sleep(PACE); await ocmd("provider", { verb: "produce" }); }
    else if (b.order_state === "delivered") return reviewGate(run, oid, ocmd);
    else if (b.order_state === "closed" || b.order_state === "failed") return;
    await sleep(1000);
  }
}

/** The controller's click, bound to the task the backend currently has open. */
export async function decide(run: Run, action: "approve" | "reject" | "ask" | "escalate", note: string): Promise<{ status: number; detail?: string }> {
  if (action === "ask" || action === "escalate") return { status: 422, detail: "The backend's controller can resume or hold; asking and escalating are not commands it has." };
  try {
    const o = await getOrder(run.tokens.controller, run.id);
    const task = o.human_tasks.find((t) => t.state === "OPEN");
    if (!task) return { status: 409, detail: "No open controller task on this order" };
    await orderCommand(run.tokens.controller, run.id, { idempotency_key: key(), expected_revision: o.revision, verb: "resolve_human", task_id: task.id, decision: action === "approve" ? "RESUME" : "RETAIN_HOLD", text: note });
    return { status: 200 };
  } catch (err) {
    return err instanceof BrokerError ? { status: err.status === 403 ? 403 : 409, detail: err.detail } : { status: 502, detail: String(err) };
  }
}

export async function newRun(c: Case): Promise<Run> {
  const roles: Role[] = ["customer", "provider", "investigator", "controller"];
  const tokens = Object.fromEntries(await Promise.all(roles.map(async (r) => [r, await session(r)]))) as Record<Role, string>;
  let markReady = () => {};
  const ready = new Promise<void>((r) => { markReady = r; });
  return { id: "", case: c, tokens, finished: false, awaiting: null, move: null, ready, markReady };
}

export { brokerEvents };
