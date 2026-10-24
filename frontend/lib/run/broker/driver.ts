// The scripted parties for a live demo order: Acme's buying agent, our provider and investigator
// seats act against Jeff's backend on a timer while the canvas watches the event stream. Only
// the controller's decision is a human click (see the decisions route).
import type { Case } from "../scenario";
import { ROWS, S } from "../scenario";
import { BrokerError, createDraft, draftCommand, events as brokerEvents, getOrder, orderCommand, session, uploadSource, type Role } from "./client";

export interface Run {
  id: string; // the broker entity id, once the draft exists
  case: Case;
  tokens: Record<Role, string>;
  error?: string;
  finished: boolean;
}

const key = () => crypto.randomUUID();
const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));
const PACE = 1400; // between party actions, so the canvas can follow
// Legacy market-v1 requires numeric values. Offer only released demo rows and
// freeze that same coverage; never turn the aggregate fixture's nulls into counts.
const SOURCE_ROWS = ROWS.flatMap((row) => row.count === null ? [] : [{ zip: row.zip, count: row.count }]);

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

/** The vendor panel as a source snapshot. The grey case leaves one ZIP without an observation date. */
export function sourceSnapshot(c: Case, version = 1) {
  return {
    source_id: "vendor-fitness-panel", version, geography: "San Francisco", boundary_version: "2026-Q3", reference_period: "2026-Q3",
    metric_name: "adults_25_34_interested_in_fitness", metric_unit: "people", entity_unit: "region",
    published_at: "2026-10-20T00:00:00Z", exported_at: "2026-10-24T00:00:00Z",
    rows: SOURCE_ROWS.map((r) => ({ entity_id: r.zip, region_id: r.zip, value: r.count, observed_at: c === "amber" && version === 1 && r.zip === "94110" ? null : "2026-10-10T00:00:00Z" })),
  };
}
const encode = (v: unknown) => Buffer.from(JSON.stringify(v)).toString("base64");

/** Runs the scripted parties for one case. Resolves when the parties have nothing left to do. */
export async function drive(run: Run, onId: (id: string) => void): Promise<void> {
  const t = run.tokens;
  const now = new Date();
  const params = parameters(now);
  try {
    let d = await createDraft(t.customer, { idempotency_key: key(), intent: `${S.order}, for an ad campaign.` });
    run.id = d.id; onId(d.id);
    await sleep(PACE);
    d = (await uploadSource(t.provider, "drafts", d.id, { idempotency_key: key(), expected_revision: d.revision, filename: "vendor-fitness-panel.json", content_base64: encode(sourceSnapshot(run.case)) })) as typeof d;
    const cmd = async (who: Role, body: Record<string, unknown>) => { d = await draftCommand(t[who], d.id, { idempotency_key: key(), expected_revision: d.revision, ...body }); };
    for (const q of [...d.questions]) if (q.answer_id === null) { await sleep(PACE * 0.6); await cmd("customer", { verb: "answer_intake", question_id: q.id, value: params[q.field] }); }
    for (const field of [...d.unresolved_fields]) {
      await cmd("controller", { verb: "clarify_intake", field });
      const q = [...d.questions].reverse().find((q) => q.field === field)!;
      await sleep(PACE * 0.6); await cmd("customer", { verb: "answer_intake", question_id: q.id, value: params[field] });
    }
    await sleep(PACE);
    await cmd("provider", { verb: "offer", capability: "SUPPORTED", price: { amount_minor: S.price * 100, currency: "USDSIM", decimals: 2 } });
    await sleep(PACE);
    await cmd("customer", { verb: "accept_specification", digest: d.acceptance_digest, authorization_expires_at: new Date(now.getTime() + 2 * 3_600_000).toISOString() });
    const oid = d.order_id!;
    const ocmd = async (who: Role, body: Record<string, unknown>) => { const cur = await getOrder(t[who], oid); return orderCommand(t[who], oid, { idempotency_key: key(), expected_revision: cur.revision, ...body }); };
    await sleep(PACE * 1.5);
    let o = await ocmd("provider", { verb: "produce" });
    await sleep(PACE * 2);
    if (run.case === "shared") {
      await ocmd("customer", { verb: "accept_delivery" });
    } else if (run.case === "green") {
      await ocmd("customer", { verb: "dispute", text: "Counts look low. Oakland should be in there." });
      await sleep(PACE * 1.5);
      o = await ocmd("investigator", { verb: "investigate" });
      await sleep(PACE * 2);
      if (o.resolution === "NO_REMEDY") await ocmd("customer", { verb: "accept_delivery" });
    } else if (run.case === "amber") {
      // The engine asks the provider; the provider answers twice; the case goes to the controller.
      for (let round = 0; round < 2; round++) {
        const q = (await getOrder(t.provider, oid)).questions.find((q) => q.status === "OPEN");
        if (!q) break;
        await sleep(PACE * 1.5);
        o = await ocmd(q.recipient, { verb: "answer", question_id: q.id, text: round === 0 ? "Our panel has no observation date for 94110 this quarter; the vendor files it under a different category." : "The category is the vendor's choice, not a data error." });
      }
      // The case now waits on the controller. Her resume re-verifies the accepted sources, so
      // without a mutually accepted amendment it stays held: the engine's rule, shown as is.
      await waitForAcceptance(run, oid);
    } else {
      run.error = "The red case has no live mapping yet; play it recorded.";
    }
  } catch (err) {
    run.error = err instanceof BrokerError ? `Backend answered ${err.status}: ${err.detail}` : err instanceof Error ? err.message : String(err);
  } finally {
    run.finished = true;
  }
}

/** After the controller resumes a held case, the buyer accepts once a review window opens. */
async function waitForAcceptance(run: Run, oid: string) {
  for (let i = 0; i < 600; i++) {
    await sleep(1000);
    const o = await getOrder(run.tokens.customer, oid);
    const state = o.base_order?.order.order_state;
    if (state === "delivered") { await sleep(PACE); await orderCommand(run.tokens.customer, oid, { idempotency_key: key(), expected_revision: o.revision, verb: "accept_delivery" }); return; }
    if (state === "closed" || state === "failed") return;
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
  return { id: "", case: c, tokens, finished: false };
}

export { brokerEvents };
