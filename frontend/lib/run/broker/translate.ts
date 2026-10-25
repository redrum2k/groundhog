// Maps Jeff's broker event stream onto the canvas's 5-step model. Pure: the same snapshot always
// yields the same RunEvents, and the output is append-only as the stream grows, so the client's
// seq cursor stays valid across polls.
import type { ContractLine, Message, RunEvent, Step, ZipCount } from "../contract";
import type { Case, Draft } from "../scenario";
import { AREA_BY_ZIP, MAIN, S } from "../scenario";
import type { BrokerCheck, BrokerEvent, BrokerOrder, BrokerSnapshot, DataRow } from "./types";

type Detour = "dispute" | "unknown" | "failed";
/** Who settled a dispute, per Jeff's `dispute.assessed`: the model (validated by code), the rules alone, or nobody yet. */
type DecidedBy = "model" | "rules" | "unresolved";
type Assessed = { kind: "justified" | "not_justified" | "unclear"; reason: string; decided_by: DecidedBy; references?: { artifact_id: string; version: number; locator: string; value: string }[] };

/** The eight accepted requirements, in the order the backend checks them, with our wording. */
const DIMENSIONS: [string, string[], (p: Record<string, unknown>) => string, string][] = [
  ["freshness", ["freshness_basis", "max_age_days", "as_of"], (p) => `Fresh: ${p.freshness_basis ?? "observation"} within ${p.max_age_days} days of the as-of date`, "How fresh the data must be"],
  ["geography", ["geography", "boundary_version", "region_ids"], (p) => `${p.geography} only, ${count(p.region_ids)} ZIPs, boundary ${p.boundary_version}`, "Which area, boundary and ZIPs"],
  ["reference_period", ["reference_period"], (p) => `Reference period ${p.reference_period}`, "Which reference period"],
  ["metric", ["metric_name", "metric_unit"], (p) => `Metric: ${words(p.metric_name)}, in ${p.metric_unit}`, "Which metric, in what unit"],
  ["entity_unit", ["entity_unit"], (p) => `One record per ${p.entity_unit}`, "One record per what"],
  ["coverage", ["coverage_ids", "max_missing_records"], (p) => `Every ZIP present: ${count(p.coverage_ids)} expected, ${p.max_missing_records} may be missing`, "Which ZIPs must be present, and how many may be missing"],
  ["source_lineage", ["revision_policy", "conflict_policy"], () => "Exact accepted source versions; conflicts need review", "Exact accepted source versions; conflicts need review"],
  ["output_schema", ["output_schema", "output_format"], (p) => `Output: ${p.output_schema} as ${String(p.output_format ?? "json").toUpperCase()}`, "Output schema and format"],
];
const count = (v: unknown) => (Array.isArray(v) ? v.length : 0);
const words = (v: unknown) => String(v ?? "").replace(/_/g, " ").replace(/\b(\d+) (\d+)\b/g, "$1-$2"); // adults_25_34 reads as a range
const dimensionOf = (field: string) => DIMENSIONS.find(([, fields]) => fields.includes(field))?.[0];
const lineFor = (d: string, answered: Record<string, unknown>): ContractLine => ({ id: d, text: DIMENSIONS.find(([id]) => id === d)![2](answered), check: "code" });
const askFor = (d: string): ContractLine => ({ id: d, text: DIMENSIONS.find(([id]) => id === d)![3], check: "code" });

const POLICY = {
  accepted: "Both parties accepted the specification digest",
  authorized: "Base authorization opens on acceptance (mock)",
  checks: "Deterministic checks against the accepted specification",
  freeCorrection: "Our-fault policy: one free correction per order",
  clarified: "Both parties accepted the clarification",
  escalate: "Two questions used; unresolved evidence goes to the controller",
  captured: "Customer acceptance with every gate passed",
};

const money = (m?: { amount_minor: number; decimals: number } | null) => (m ? m.amount_minor / 10 ** m.decimals : 0);
const minutes = (from: string, to: string | null) => (to ? Math.max(1, Math.round((Date.parse(to) - Date.parse(from)) / 60_000)) : null);

function rowsToSheet(rows: DataRow[]): ZipCount[] {
  return rows
    .map((r): ZipCount => ({ zip: r.entity_id, area: AREA_BY_ZIP[r.entity_id] ?? r.region_id, count: Math.round(r.value), flag: r.observed_at ? undefined : "withheld" }))
    .sort((a, b) => a.zip.localeCompare(b.zip));
}

/** The steps a detour takes, in the backend's own terms. */
function detourSteps(kind: Detour, resolution: BrokerOrder["resolution"], decidedBy?: DecidedBy): Step[] {
  if (kind === "dispute") return [
    { id: "investigate", kind: "investigate", title: "Investigate", detail: "Contract against the delivery", panel: true },
    { id: "verdict", kind: "verdict", title: resolution === "CORRECTED" ? "They're right" : "We're right", detail: decidedBy === "model" ? "Decided by model, verified by code" : decidedBy === "rules" ? "Decided by rules" : resolution === "CORRECTED" ? "A requirement failed" : "Delivered as accepted" },
  ];
  if (kind === "failed") return [
    { id: "investigate", kind: "investigate", title: "Check failed", detail: "A requirement did not pass", panel: true },
    { id: "verdict", kind: "verdict", title: "Our miss", detail: "One free correction" },
  ];
  return [
    { id: "investigate", kind: "investigate", title: "Investigate", detail: "A fact the sources don't settle", panel: true },
    { id: "grey", kind: "grey", title: "Grey area", detail: "Evidence can't decide" },
    { id: "decide", kind: "decide", title: `${S.controller} decides`, detail: "Controller review", panel: true },
  ];
}

export function translate(snapshot: BrokerSnapshot, lane: Case): RunEvent[] {
  const { events, order, checksBySeq, rowsByVersion } = snapshot;
  const rowsFor = (version: number) => rowsByVersion[version] ?? rowsByVersion[Math.max(0, ...Object.keys(rowsByVersion).map(Number))] ?? [];
  const base = order.base_order?.order;
  const price = money(base?.snapshot?.price) || S.price;
  const messagesById = new Map((order.messages ?? []).map((m) => [m.id, m]));
  const out: [Draft, string][] = [];
  let at = "";
  const emit = (d: Draft) => out.push([d, at]);
  const say = (step: string, message: Message, attempt = 1) => emit({ type: "message", step, message, attempt });
  const caption = (text: string) => emit({ type: "caption", text });
  const completed = new Set<string>();
  const complete = (step: string, attempt = 1) => { const k = `${step}#${attempt}`; if (!completed.has(k)) { completed.add(k); emit({ type: "step_completed", step, attempt }); } };

  const answered: Record<string, unknown> = {};
  const answers: Record<string, { id: string; text: string }> = {}; // Acme's own words per contract line, to cite
  const pendingQuestions = new Map<string, Message>(); // the backend asks everything up front; each question shows when Acme answers it, as a conversation
  const drafted = new Set<string>();
  const asked = new Set<string>();
  let contractVersion = 0;
  let delivery = 0, reviews = 0, verifications = 0;
  let detour: Detour | null = null, detourDelivery = 0, detourStep = "investigate", resumed = false, verdictDone = false, controllerOpen = false;
  let assessment: { reason: string; decidedBy: DecidedBy; evidenceIds: string[] } | null = null; // the bounded assessment, when the backend flag is on
  let sourceVersion = 1; // the vendor panel version pinned at acceptance; a clarification brings v2
  // A message on the decide step reads as activity; while the controller's task is open the gate is re-asserted after it
  const holdForController = () => { if (controllerOpen && detourStep === "decide") emit({ type: "step_waiting", step: "decide", waitingOn: S.controller }); };
  const lines = (): ContractLine[] => [...drafted].map((d) => lineFor(d, answered)); // in the order the interview settled them, so approval and review list the same thing
  const stepsWithWindow = (window: number | null): Step[] => MAIN.map((s) => s.kind === "review" ? { ...s, detail: window ? `${window}-minute review window` : "Accept or dispute" } : s.kind === "paid" ? { ...s, detail: `$${price} authorized` } : s);
  // What the agent reads at the source during a dispute: the engine re-runs every accepted line against the pinned vendor data and the delivery
  const sourceLines = (checked: boolean) => [
    { id: "src-pin", text: `LOOKUP vendor panel v${sourceVersion} · pinned at acceptance`, checked },
    { id: "src-lines", text: `CHECK ${lines().length} contract lines · against the source`, checked },
    { id: "src-counts", text: "COMPARE delivered counts · with the source", checked },
  ];
  const closeDetour = () => {
    if (!detour) return;
    if (detour === "dispute" && !verdictDone) {
      const kind = order.resolution === "CORRECTED" ? "agree" : "disagree";
      const cites: string[] = [];
      if (kind === "disagree") {
        const geo = answers.geography;
        if (geo) {
          cites.push("cite-geography");
          emit({ type: "evidence_found", step: "investigate", evidence: { id: "cite-geography", kind: "interview_quote", label: `Contract: ${answered.geography} only`, note: "The geography line of the contract, in Acme's own words.", speaker: S.buyerAgent, quote: geo.text, source: { kind: "message", messageId: geo.id } } });
        }
        const zips = count(answered.coverage_ids);
        cites.push("cite-coverage");
        emit({ type: "evidence_found", step: "investigate", evidence: { id: "cite-coverage", kind: "sheet_cell", label: `${zips} of ${zips} ZIPs delivered`, note: "Every ZIP the contract names is in the delivery.", file: "market-data.json", row: "", column: "", value: `${zips} of ${zips}`, source: { kind: "cell", version: delivery, row: "", column: "" } } });
        say("investigate", { id: `defense-${delivery}`, from: "agent", text: `Checked the delivery against every accepted line again: all pass. The contract covers ${answered.geography} only, ${zips} ZIPs, and all ${zips} are in the delivery. Nothing was missing from what was agreed, and there is no charge for asking.`, attach: cites.map((evidenceId) => ({ kind: "evidence" as const, evidenceId })) });
      }
      complete("investigate");
      emit({ type: "step_started", step: "verdict" });
      emit({ type: "verdict", step: "verdict", verdict: { kind, decidedBy: "rules", evidenceIds: [...cites, ...(assessment?.evidenceIds ?? [])], reason: assessment ? `${assessment.decidedBy === "model" ? "Decided by the model, verified by code: " : ""}${assessment.reason}` : kind === "agree" ? "A requirement failed and was corrected." : "Every accepted requirement passed; nothing was missing from what was agreed." }, allowedBy: POLICY.checks });
      emit({ type: "aside", step: "verdict", text: kind === "disagree" ? "Settled by the contract and the source. No human needed." : "Our miss, caught by the checks. Corrected at our cost, no human needed." });
      verdictDone = true;
    }
    for (const s of detourSteps(detour, order.resolution)) complete(s.id);
    detour = null; resumed = false; verdictDone = false;
  };

  for (const e of events) {
    const p = e.payload;
    at = e.timestamp;
    switch (e.type) {
      case "spec.draft_created": {
        emit({ type: "steps_planned", steps: stepsWithWindow(null) });
        emit({ type: "step_started", step: "clarify" });
        const intent = order.messages?.[0];
        if (intent) say("clarify", { id: intent.id, from: "buyer", text: intent.text });
        caption("Our agent interviews Acme's buying agent. Each answer becomes a line in the contract.");
        break;
      }
      case "spec.question_requested": {
        const q = p.question as { id: string; field: string; prompt: string };
        const dim = dimensionOf(q.field);
        pendingQuestions.set(q.id, { id: q.id, from: "agent", text: q.prompt, asks: dim });
        if (dim && !asked.has(dim)) { asked.add(dim); emit({ type: "contract_line_asked", step: "clarify", line: askFor(dim) }); }
        break;
      }
      case "spec.answer_received": {
        const m = messagesById.get(String(p.answer_id));
        if (!m) break;
        const q = pendingQuestions.get(String(p.question_id));
        if (q) { pendingQuestions.delete(q.id); say("clarify", q); }
        say("clarify", { id: m.id, from: "buyer", text: m.field ? wordsFor(m.field, m.text) : plain(m.text) });
        if (m.field) answered[m.field] = parse(m.text);
        const dim = m.field ? dimensionOf(m.field) : undefined;
        if (dim) answers[dim] = { id: m.id, text: plain(m.text) };
        for (const [d, fields] of DIMENSIONS) if (!drafted.has(d) && fields.every((f) => f in answered)) { drafted.add(d); emit({ type: "contract_line_drafted", step: "clarify", line: lineFor(d, answered) }); }
        break;
      }
      case "spec.provider_accepted":
        say("clarify", { id: `offer-${e.sequence}`, from: "agent", text: `Supported. Price: $${price}. Approve?` });
        break;
      case "spec.accepted": {
        // The accepted spec is the source of truth for the lines from here on
        for (const r of order.original_specification?.requirements ?? []) {
          for (const [k, val] of Object.entries(r.parameters)) if (val !== null && val !== undefined && !(Array.isArray(val) && val.length === 0)) answered[k] = val;
          drafted.add(r.dimension);
        }
        contractVersion = 1;
        say("clarify", { id: `accept-${e.sequence}`, from: "buyer", text: "Approved." });
        emit({ type: "contract_approved", step: "clarify", contract: { version: 1, buyer: S.buyer, title: S.order, price, lines: lines() }, allowedBy: POLICY.accepted });
        complete("clarify");
        emit({ type: "step_started", step: "paid" });
        emit({ type: "payment_authorized", payment: { id: "order", amount: price, rail: "mock", network: "base-sepolia", mock: true }, allowedBy: POLICY.authorized });
        complete("paid");
        caption(`Acme approves the contract. The backend opens a $${price} authorization; it is only taken once the data is accepted.`);
        break;
      }
      case "delivery.published": {
        delivery = Number(p.delivery_version ?? delivery + 1);
        emit({ type: "step_started", step: "produce", attempt: delivery });
        emit({ type: "delivery_ready", step: "produce", attempt: delivery, delivery: { version: delivery, file: "market-data.json", rows: rowsToSheet(rowsFor(delivery)) } });
        caption(delivery > 1 ? "Back to Produce with the clarified contract. The correction is on us." : "We build the counts from the vendor's data and check every accepted requirement.");
        break;
      }
      case "verification.completed": {
        verifications += 1;
        const verdict = String(p.verdict);
        const checks = verdict === "PASS" ? passAll() : currentChecks(checksBySeq[e.sequence] ?? base?.data_verification?.checks ?? []);
        const failed = checks.filter((c) => !c.passed);
        const rerun = detour !== null && delivery > detourDelivery;
        const step = detour === null || rerun ? "produce" : detourStep;
        const attempt = step === "produce" ? delivery : 1;
        if (detour === "unknown" && resumed && !rerun) say("decide", { id: `recheck-${e.sequence}`, from: "agent", text: verdict === "PASS" ? "Rechecked against the clarified contract: it passes." : "Rechecked against the clarified contract. The delivery was built from the old revision, so it fails and the correction is free." });
        if (detour === "dispute" && !rerun) emit({ type: "source_checked", step: "investigate", lines: sourceLines(true) });
        for (const c of checks) emit(c.passed ? { type: "check_passed", step, attempt, lineId: c.id, detail: c.detail } : { type: "check_failed", step, attempt, lineId: c.id, reason: c.detail ?? "did not pass" });
        if (verdict === "PASS") {
          const wasRerun = rerun;
          closeDetour();
          if (step === "produce") complete("produce", attempt);
          caption(wasRerun ? "Rechecked against the clarified contract: every requirement passes." : "Every accepted requirement passed.");
        } else if (verdict === "FAIL") {
          if (!detour) {
            detour = "failed"; detourDelivery = delivery; detourStep = "investigate";
            emit({ type: "steps_planned", steps: detourSteps("failed", order.resolution) });
            emit({ type: "step_started", step: "investigate" });
            for (const c of failed) emit({ type: "evidence_found", step: "investigate", evidence: { id: `fail-${verifications}-${c.id}`, kind: "sheet_cell", label: `Failed · ${words(c.id)}`, file: "market-data.json", row: "", column: "", value: null, note: c.detail ?? "", source: { kind: "none", reason: "The verification report is the backend's own check" } } });
            caption(`A check failed: ${failed[0]?.detail ?? "a requirement did not pass"} The engine reserves one free correction.`);
          }
        } else if (!detour) {
          detour = "unknown"; detourDelivery = delivery; detourStep = "investigate";
          emit({ type: "steps_planned", steps: detourSteps("unknown", order.resolution) });
          emit({ type: "step_started", step: "investigate" });
          for (const c of failed) emit({ type: "evidence_found", step: "investigate", evidence: { id: `unknown-${verifications}-${c.id}`, kind: "sheet_cell", label: `Unknown · ${words(c.id)}`, file: "market-data.json", row: "", column: "", value: null, note: c.detail ?? "", source: { kind: "none", reason: "The source file lacks this fact" } } });
          caption("The sources don't settle every requirement. The agent can ask up to two questions before a person decides.");
        }
        break;
      }
      case "correction.required": {
        if (verdictDone) break;
        if (detour === "failed") {
          complete("investigate");
          emit({ type: "step_started", step: "verdict" });
          emit({ type: "verdict", step: "verdict", verdict: { kind: "agree", decidedBy: "rules", evidenceIds: [], reason: "A requirement failed; one free correction is reserved." }, allowedBy: POLICY.freeCorrection });
          complete("verdict");
          verdictDone = true;
          caption("Our miss: the vendor's revision didn't meet the contract. The rerun is on us.");
        } else if (detour === "unknown" && resumed) {
          emit({ type: "verdict", step: "decide", verdict: { kind: "agree", decidedBy: "controller", evidenceIds: [], reason: `${S.controller} resumed with the clarified contract; the old delivery fails it, so the correction is free.` }, allowedBy: POLICY.freeCorrection });
          complete("decide");
          verdictDone = true;
          caption(`${S.controller} resumed the case. The old delivery fails the clarified contract, so the correction is free.`);
        }
        break;
      }
      case "evidence.source_added": {
        sourceVersion = Number((p.source as { version?: number } | undefined)?.version ?? sourceVersion);
        if (!detour) break; // the first upload happens on the draft, before anything is on screen
        const src = p.source as { version: number } | undefined;
        say(detourStep, { id: `source-${e.sequence}`, from: "agent", text: `Supplied revision ${src?.version ?? ""} of the vendor's source.` });
        holdForController();
        break;
      }
      case "spec.amendment_accepted": {
        contractVersion += 1;
        const step = detour ? detourStep : "clarify";
        say(step, { id: `amend-${e.sequence}`, from: "buyer", text: `Both sides accepted the clarification: contract v${contractVersion} pins the new revision.` });
        emit({ type: "contract_approved", step, contract: { version: contractVersion, buyer: S.buyer, title: S.order, price, lines: lines() }, allowedBy: POLICY.clarified });
        caption(`Both parties accepted the clarification. The contract is now v${contractVersion}.`);
        holdForController();
        break;
      }
      case "review.opened": {
        reviews += 1;
        const window = minutes(e.timestamp, (p.deadline as string | null) ?? null);
        if (window) emit({ type: "steps_planned", steps: stepsWithWindow(window) });
        emit({ type: "delivery_ready", step: "review", attempt: reviews, delivery: { version: delivery, file: "market-data.json", rows: rowsToSheet(rowsFor(delivery)), reviewClosesAt: (p.deadline as string | undefined) ?? undefined } });
        emit({ type: "step_started", step: "review", attempt: reviews });
        caption(window ? `Delivered. Acme has ${window} minutes to accept or dispute.` : "Delivered. Acme can accept or dispute.");
        break;
      }
      case "case.opened": {
        detour = "dispute"; detourDelivery = delivery; detourStep = "investigate";
        emit({ type: "dispute_opened", step: "review", attempt: reviews, dispute: { id: String(p.issue_id), claim: base?.complaint ?? "Disputed", raisedBy: S.buyerAgent } });
        emit({ type: "step_waiting", step: "review", attempt: reviews, waitingOn: S.buyer });
        emit({ type: "steps_planned", steps: detourSteps("dispute", order.resolution) });
        emit({ type: "step_started", step: "investigate" });
        emit({ type: "source_checked", step: "investigate", lines: sourceLines(false) });
        say("investigate", { id: `claim-${e.sequence}`, from: "buyer", text: base?.complaint ?? "Disputed." });
        caption(`Acme disputes: “${base?.complaint ?? "the delivery"}”. The payment stays held until it's resolved.`);
        break;
      }
      case "dispute.assessed": {
        // Jeff's bounded assessment: the model proposes, code validates, the server owns the effective outcome.
        // A fallback never reads as model-decided.
        const a = p as unknown as Assessed;
        const refs = (a.references ?? []).slice(0, 4);
        const ids = refs.map((_, i) => `assessed-${e.sequence}-${i}`);
        refs.forEach((r, i) => emit({ type: "evidence_found", step: "investigate", evidence: { id: ids[i], kind: "claim", label: r.value.length > 48 ? `${r.value.slice(0, 45)}…` : r.value, note: `${r.artifact_id} v${r.version}, ${r.locator}`, speaker: r.artifact_id, quote: r.value, source: { kind: "none", reason: `${r.artifact_id} v${r.version}, ${r.locator}` } } }));
        const who = a.decided_by === "model" ? "The model read the objection against the contract; code verified each fact it cited." : a.decided_by === "rules" ? "The rules settle this without the model." : "Neither the model nor the rules settle this.";
        say("investigate", { id: `assessed-${e.sequence}`, from: "agent", text: `${who} ${a.reason}`, attach: ids.map((evidenceId) => ({ kind: "evidence" as const, evidenceId })) });
        assessment = { reason: a.reason, decidedBy: a.decided_by, evidenceIds: ids };
        if (a.kind === "unclear") {
          if (detour !== "unknown") { detour = "unknown"; detourDelivery = delivery; emit({ type: "steps_planned", steps: detourSteps("unknown", order.resolution) }); }
          caption("Not settled by the model or the rules. The agent can ask up to two questions before a person decides.");
        } else {
          emit({ type: "steps_planned", steps: detourSteps("dispute", order.resolution, a.decided_by) });
          caption(a.decided_by === "model" ? "Decided by the model, verified by code." : "Decided by rules.");
        }
        break;
      }
      case "question.requested": {
        const q = p.question as { id: string; text: string; recipient: string };
        say("investigate", { id: q.id, from: "agent", text: q.text });
        emit({ type: "step_waiting", step: "investigate", waitingOn: q.recipient === "customer" ? S.buyer : q.recipient === "provider" ? "the provider" : S.controller });
        caption(`The agent asks ${q.recipient === "customer" ? "Acme" : "the provider"} for the missing fact. Two questions at most.`);
        break;
      }
      case "answer.received": {
        const m = messagesById.get(String(p.answer_id));
        if (m) say("investigate", { id: m.id, from: m.actor_id === "customer" ? "buyer" : "agent", text: m.text });
        break;
      }
      case "case.escalated": {
        const task = p.task as { id: string; reason: string; missing_facts: string[] };
        if (detour !== "unknown") { detour = "unknown"; detourDelivery = delivery; emit({ type: "steps_planned", steps: detourSteps("unknown", order.resolution) }); }
        complete("investigate");
        emit({ type: "step_started", step: "grey" });
        emit({ type: "verdict", step: "grey", verdict: { kind: "grey", decidedBy: "rules", evidenceIds: [], reason: task.reason }, allowedBy: POLICY.escalate });
        complete("grey");
        detourStep = "decide";
        emit({ type: "step_started", step: "decide" });
        emit({ type: "aside", step: "decide", text: `Neither the contract nor the source settles this. One call for ${S.controller}.` });
        say("decide", { id: task.id, from: "agent", text: `${task.reason} Missing: ${task.missing_facts.join("; ")}` });
        emit({ type: "step_waiting", step: "decide", waitingOn: S.controller });
        controllerOpen = true;
        caption(`The rules can't decide, so it goes to ${S.controller}, our controller, with the evidence.`);
        break;
      }
      case "human.decision": {
        const decision = String(p.decision);
        emit({ type: "controller_decided", step: "decide", action: decision === "RESUME" ? "approve" : "reject", by: S.controller, note: String(p.explanation ?? ""), binding: { deliveryVersion: base?.binding?.delivery_version ?? delivery, evidenceVersion: base?.binding?.evidence_version ?? 0 } });
        say("decide", { id: `decision-${e.sequence}`, from: "controller", text: String(p.explanation ?? decision) });
        controllerOpen = decision !== "RESUME";
        if (decision === "RESUME") { resumed = true; caption(`${S.controller} resumes the case: the backend rechecks the delivery against the current contract.`); }
        else { emit({ type: "step_waiting", step: "decide", waitingOn: S.controller }); caption(`${S.controller} keeps the hold. Nothing moves until new evidence or an accepted clarification.`); }
        break;
      }
      case "review.accepted": {
        say("review", { id: `accepted-${e.sequence}`, from: "buyer", text: "Accepted." }, reviews);
        complete("review", reviews);
        emit({ type: "step_started", step: "captured" });
        if (base?.payment_phase === "booked") {
          emit({ type: "payment_captured", paymentId: "order", captureTx: null, allowedBy: POLICY.captured });
          const entries = base.ledger.map((l) => ({ id: l.entry_id, memo: l.reason === "customer_acceptance" ? "Payment captured on acceptance" : `${words(l.kind)} payment, ${words(l.reason)}`, debit: "Cash", credit: "Revenue", amount: money(l.amount) }));
          const revenue = entries.reduce((a, l) => a + l.amount, 0);
          emit({ type: "books_posted", step: "captured", entries, margin: { revenue, cost: 0 } });
          complete("captured");
          caption(`Accepted. $${revenue} captured (mock) and booked.`);
        }
        break;
      }
    }
  }
  return out.map(([d, when], i) => ({ track: lane, ...d, seq: i + 1, at: when }) as RunEvent);

  function passAll() { return DIMENSIONS.map(([d]) => ({ id: d, passed: true, detail: undefined as string | undefined })); }
  function currentChecks(checks: BrokerCheck[]) {
    return DIMENSIONS.map(([d]) => { const c = checks.find((c) => c.requirement_id === `req-${d}`); return { id: d, passed: c?.verdict === "PASS", detail: c?.explanation }; });
  }
}

const parse = (text: string): unknown => { try { return JSON.parse(text); } catch { return text; } };
const plain = (text: string) => { const v = parse(text); return Array.isArray(v) ? v.join(", ") : typeof v === "string" ? v : text; };
/** Acme's answer in words. The backend keeps the machine value; the customer reads what they meant. */
const wordsFor = (field: string, text: string): string => {
  const v = parse(text);
  if (Array.isArray(v)) return v.join(", ");
  const s = String(v);
  switch (field) {
    case "as_of": return `As of ${new Date(s).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" })}`;
    case "max_age_days": return `${s} days`;
    case "freshness_basis": return s === "observed_at" ? "The observation date" : words(s);
    case "metric_name": return words(s);
    case "entity_unit": return `One per ${s}`;
    case "max_missing_records": return s === "0" ? "None may be missing" : `${s} may be missing`;
    case "revision_policy": return s === "exact_accepted_versions" ? "Exact accepted versions only" : words(s);
    case "conflict_policy": return s === "UNKNOWN" ? "Flag conflicts for review" : words(s.toLowerCase());
    case "output_format": return s.toUpperCase();
    default: return plain(text);
  }
};

export type { BrokerEvent, BrokerOrder };
