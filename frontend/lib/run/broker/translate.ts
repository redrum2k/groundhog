// Maps Jeff's broker event stream onto the canvas's 5-step model. Pure: the same snapshot always
// yields the same RunEvents, and the output is append-only as the stream grows, so the client's
// seq cursor stays valid across polls.
import type { ContractLine, Delivery, Message, RunEvent, Step, ZipCount } from "../contract";
import type { Case, Draft } from "../scenario";
import { AREA_BY_ZIP, MAIN, S } from "../scenario";
import type { BrokerCheck, BrokerEvent, BrokerOrder, BrokerSnapshot, DataRow } from "./types";

type Lane = Exclude<Case, "shared">;

/** The eight accepted requirements, in the order the backend checks them, with our wording. */
const DIMENSIONS: [string, string[], (p: Record<string, unknown>) => string][] = [
  ["freshness", ["freshness_basis", "max_age_days", "as_of"], (p) => `Fresh: ${p.freshness_basis ?? "observation"} within ${p.max_age_days} days of the as-of date`],
  ["geography", ["geography", "boundary_version", "region_ids"], (p) => `${p.geography} only, ${count(p.region_ids)} ZIPs, boundary ${p.boundary_version}`],
  ["reference_period", ["reference_period"], (p) => `Reference period ${p.reference_period}`],
  ["metric", ["metric_name", "metric_unit"], (p) => `Metric: ${words(p.metric_name)}, in ${p.metric_unit}`],
  ["entity_unit", ["entity_unit"], (p) => `One record per ${p.entity_unit}`],
  ["coverage", ["coverage_ids", "max_missing_records"], (p) => `Every ZIP present: ${count(p.coverage_ids)} expected, ${p.max_missing_records} may be missing`],
  ["source_lineage", ["revision_policy", "conflict_policy"], () => "Exact accepted source versions; conflicts need review"],
  ["output_schema", ["output_schema", "output_format"], (p) => `Output: ${p.output_schema} as ${String(p.output_format ?? "json").toUpperCase()}`],
];
const count = (v: unknown) => (Array.isArray(v) ? v.length : 0);
const words = (v: unknown) => String(v ?? "").replace(/_/g, " ");
const dimensionOf = (field: string) => DIMENSIONS.find(([, fields]) => fields.includes(field))?.[0];

const money = (m?: { amount_minor: number; decimals: number } | null) => (m ? m.amount_minor / 10 ** m.decimals : 0);
const minutes = (from: string, to: string | null) => (to ? Math.max(1, Math.round((Date.parse(to) - Date.parse(from)) / 60_000)) : null);

function rowsToSheet(rows: DataRow[], missing: string[] = []): ZipCount[] {
  const sheet: ZipCount[] = rows.map((r) => ({ zip: r.entity_id, area: AREA_BY_ZIP[r.entity_id] ?? r.region_id, count: Math.round(r.value), flag: r.observed_at ? undefined : "withheld" }));
  for (const zip of missing) if (!sheet.some((r) => r.zip === zip)) sheet.push({ zip, area: AREA_BY_ZIP[zip] ?? "", count: 0, flag: "missing" });
  return sheet.sort((a, b) => a.zip.localeCompare(b.zip));
}

/** The steps a detour takes in the backend's own terms. */
function detourSteps(lane: Lane, kind: "dispute" | "unknown" | "failed"): Step[] {
  if (kind === "dispute") return [
    { id: "investigate", kind: "investigate", title: "Investigate", detail: "The accepted spec against the delivery", panel: true },
    { id: "verdict", kind: "verdict", title: lane === "red" ? "They're right" : "We're right", detail: lane === "red" ? "A requirement failed" : "Delivered as accepted" },
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
  const { events, order, rows } = snapshot;
  const base = order.base_order?.order;
  const price = money(base?.snapshot?.price) || S.price;
  const messagesById = new Map((order.messages ?? []).map((m) => [m.id, m]));
  const out: [Draft, string][] = [];
  let at = "";
  const emit = (d: Draft) => out.push([d, at]);
  const say = (step: string, message: Message, attempt = 1) => emit({ type: "message", step, message, attempt });

  const answered: Record<string, unknown> = {};
  const drafted = new Set<string>();
  const asked = new Set<string>();
  let delivery = 0, reviews = 0, detour: "dispute" | "unknown" | "failed" | null = null, verifications = 0;
  const lines = (): ContractLine[] => DIMENSIONS.filter(([d]) => drafted.has(d)).map(([d, , text]) => ({ id: d, text: text(answered), check: "code" }));
  const stepsWithWindow = (window: number | null): Step[] => MAIN.map((s) => s.kind === "review" ? { ...s, detail: window ? `${window}-minute window to accept or dispute` : "Accept or dispute" } : s.kind === "paid" ? { ...s, detail: `$${price} authorized · mock` } : s);

  for (const e of events) {
    const p = e.payload;
    at = e.timestamp;
    switch (e.type) {
      case "spec.draft_created": {
        emit({ type: "steps_planned", steps: stepsWithWindow(null) });
        emit({ type: "step_started", step: "clarify" });
        const intent = order.messages[0];
        if (intent) say("clarify", { id: intent.id, from: "buyer", text: intent.text });
        break;
      }
      case "spec.question_requested": {
        const q = p.question as { id: string; field: string; prompt: string };
        const dim = dimensionOf(q.field);
        say("clarify", { id: q.id, from: "agent", text: q.prompt, asks: dim });
        if (dim && !asked.has(dim)) { asked.add(dim); emit({ type: "contract_line_asked", step: "clarify", line: { id: dim, text: DIMENSIONS.find(([d]) => d === dim)![2](answered), check: "code" } }); }
        break;
      }
      case "spec.answer_received": {
        const m = messagesById.get(String(p.answer_id));
        if (!m) break;
        say("clarify", { id: m.id, from: "buyer", text: plain(m.text) });
        if (m.field) answered[m.field] = parse(m.text);
        for (const [d, fields, text] of DIMENSIONS) if (!drafted.has(d) && fields.every((f) => f in answered)) { drafted.add(d); emit({ type: "contract_line_drafted", step: "clarify", line: { id: d, text: text(answered), check: "code" } }); }
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
        say("clarify", { id: `accept-${e.sequence}`, from: "buyer", text: "Approved." });
        emit({ type: "contract_approved", step: "clarify", contract: { version: 1, buyer: S.buyer, title: S.order, price, lines: lines() }, allowedBy: "Both parties accepted the specification digest" });
        emit({ type: "step_completed", step: "clarify" });
        emit({ type: "step_started", step: "paid" });
        emit({ type: "payment_authorized", payment: { id: "order", amount: price, rail: "mock", network: "base-sepolia", mock: true }, allowedBy: "Base authorization opens on acceptance (mock)" });
        emit({ type: "step_completed", step: "paid" });
        break;
      }
      case "delivery.published": {
        delivery = Number(p.delivery_version ?? delivery + 1);
        emit({ type: "step_started", step: "produce", attempt: delivery });
        const d: Delivery = { version: delivery, file: "market-data.json", rows: rowsToSheet(rows) };
        emit({ type: "delivery_ready", step: "produce", attempt: delivery, delivery: d });
        break;
      }
      case "verification.completed": {
        verifications += 1;
        const verdict = String(p.verdict);
        const checks = verdict === "PASS" ? passAll() : currentChecks(base?.data_verification?.checks ?? []);
        const step = detour ? "investigate" : "produce";
        if (detour === "dispute") {
          const failed = checks.filter((c) => !c.passed);
          emit({ type: "evidence_found", step, evidence: { id: `verification-${verifications}`, kind: "sheet_cell", label: failed.length ? `Verification · ${failed.length} of ${checks.length} requirements failed` : `Verification · ${checks.length} of ${checks.length} requirements passed`, file: "market-data.json", row: "", column: "", value: failed.length ? null : "passed", note: failed.map((c) => c.detail).join(" ") || "Every accepted requirement held against the delivered rows and the pinned sources.", source: { kind: "none", reason: "The verification report is the backend's own check" } } });
        }
        for (const c of checks) emit(c.passed ? { type: "check_passed", step, attempt: delivery, lineId: c.id, detail: c.detail } : { type: "check_failed", step, attempt: delivery, lineId: c.id, reason: c.detail ?? "did not pass" });
        if (detour && verdict === "PASS") {
          const kind = detour === "dispute" ? (order.resolution === "CORRECTED" ? "agree" : "disagree") : "agree";
          emit({ type: "step_completed", step: "investigate" });
          if (detour === "unknown") { emit({ type: "step_completed", step: "grey" }); emit({ type: "step_completed", step: "decide" }); }
          else { emit({ type: "step_started", step: "verdict" }); emit({ type: "verdict", step: "verdict", verdict: { kind, decidedBy: "rules", evidenceIds: [], reason: kind === "agree" ? "A requirement failed and was corrected." : "Every accepted requirement passed; nothing was missing from what was agreed." }, allowedBy: "Deterministic checks against the accepted specification" }); emit({ type: "step_completed", step: "verdict" }); }
          detour = null;
        } else if (!detour && verdict === "PASS") emit({ type: "step_completed", step: "produce", attempt: delivery });
        else if (verdict === "FAIL" && !detour) { detour = "failed"; emit({ type: "steps_planned", steps: detourSteps(laneOf(lane), "failed") }); emit({ type: "step_started", step: "investigate" }); }
        else if (verdict !== "PASS" && !detour) {
          detour = "unknown";
          emit({ type: "steps_planned", steps: detourSteps(laneOf(lane), "unknown") });
          emit({ type: "step_started", step: "investigate" });
          for (const c of checks.filter((c) => !c.passed)) emit({ type: "evidence_found", step: "investigate", evidence: { id: `unknown-${verifications}-${c.id}`, kind: "sheet_cell", label: `Unknown · ${words(c.id)}`, file: "market-data.json", row: "", column: "", value: null, note: c.detail ?? "", source: { kind: "none", reason: "The source file lacks this fact" } } });
        }
        break;
      }
      case "correction.required":
        if (detour === "failed") { emit({ type: "step_completed", step: "investigate" }); emit({ type: "step_started", step: "verdict" }); emit({ type: "verdict", step: "verdict", verdict: { kind: "agree", decidedBy: "rules", evidenceIds: [], reason: "A requirement failed; one free correction is reserved." }, allowedBy: "Our-fault policy: one free correction per order" }); emit({ type: "step_completed", step: "verdict" }); }
        break;
      case "review.opened": {
        reviews += 1;
        const window = minutes(e.timestamp, (p.deadline as string | null) ?? null);
        if (window) emit({ type: "steps_planned", steps: stepsWithWindow(window) });
        emit({ type: "delivery_ready", step: "review", attempt: reviews, delivery: { version: delivery, file: "market-data.json", rows: rowsToSheet(rows), reviewClosesAt: (p.deadline as string | undefined) ?? undefined } });
        emit({ type: "step_started", step: "review", attempt: reviews });
        break;
      }
      case "case.opened": {
        detour = "dispute";
        emit({ type: "dispute_opened", step: "review", attempt: reviews, dispute: { id: String(p.issue_id), claim: base?.complaint ?? "Disputed", raisedBy: S.buyerAgent } });
        emit({ type: "step_waiting", step: "review", attempt: reviews, waitingOn: S.buyer });
        emit({ type: "steps_planned", steps: detourSteps(laneOf(lane), "dispute") });
        emit({ type: "step_started", step: "investigate" });
        say("investigate", { id: `claim-${e.sequence}`, from: "buyer", text: base?.complaint ?? "Disputed." });
        break;
      }
      case "question.requested": {
        const q = p.question as { id: string; text: string; recipient: string };
        say("investigate", { id: q.id, from: "agent", text: q.text });
        emit({ type: "step_waiting", step: "investigate", waitingOn: q.recipient === "customer" ? S.buyer : q.recipient === "provider" ? "the provider" : S.controller });
        break;
      }
      case "answer.received": {
        const m = messagesById.get(String(p.answer_id));
        if (m) say("investigate", { id: m.id, from: m.actor_id === "customer" ? "buyer" : "agent", text: m.text });
        break;
      }
      case "case.escalated": {
        const task = p.task as { id: string; reason: string; missing_facts: string[] };
        if (detour !== "unknown") { detour = "unknown"; emit({ type: "steps_planned", steps: detourSteps(laneOf(lane), "unknown") }); }
        emit({ type: "step_completed", step: "investigate" });
        emit({ type: "step_started", step: "grey" });
        emit({ type: "verdict", step: "grey", verdict: { kind: "grey", decidedBy: "rules", evidenceIds: [], reason: task.reason }, allowedBy: "Two questions used; unresolved evidence goes to the controller" });
        emit({ type: "step_completed", step: "grey" });
        emit({ type: "step_started", step: "decide" });
        say("decide", { id: task.id, from: "agent", text: `${task.reason} Missing: ${task.missing_facts.join("; ")}` });
        emit({ type: "step_waiting", step: "decide", waitingOn: S.controller });
        break;
      }
      case "human.decision": {
        const decision = String(p.decision);
        emit({ type: "controller_decided", step: "decide", action: decision === "RESUME" ? "approve" : "reject", by: S.controller, note: String(p.explanation ?? ""), binding: { deliveryVersion: base?.binding.delivery_version ?? delivery, evidenceVersion: base?.binding.evidence_version ?? 0 } });
        say("decide", { id: `decision-${e.sequence}`, from: "controller", text: String(p.explanation ?? decision) });
        if (decision !== "RESUME") emit({ type: "step_waiting", step: "decide", waitingOn: S.controller });
        break;
      }
      case "review.accepted": {
        say("review", { id: `accepted-${e.sequence}`, from: "buyer", text: "Accepted." }, reviews);
        emit({ type: "step_completed", step: "review", attempt: reviews });
        emit({ type: "step_started", step: "captured" });
        if (base?.payment_phase === "booked") {
          emit({ type: "payment_captured", paymentId: "order", captureTx: null, allowedBy: "Customer acceptance with every gate passed" });
          const entries = base.ledger.map((l) => ({ id: l.entry_id, memo: l.reason === "customer_acceptance" ? "Payment captured on acceptance" : `${words(l.kind)} payment, ${words(l.reason)}`, debit: "Cash", credit: "Revenue", amount: money(l.amount) }));
          emit({ type: "books_posted", step: "captured", entries, margin: { revenue: entries.reduce((a, l) => a + l.amount, 0), cost: 0 } });
          emit({ type: "step_completed", step: "captured" });
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

const laneOf = (c: Case): Lane => (c === "shared" ? "green" : c);
const parse = (text: string): unknown => { try { return JSON.parse(text); } catch { return text; } };
const plain = (text: string) => { const v = parse(text); return Array.isArray(v) ? v.join(", ") : typeof v === "string" ? v : text; };

/** Which chip the fold shows depends on what the stream said; expose for tests. */
export const BROKER_EVENT_TYPES = ["spec.draft_created", "spec.question_requested", "spec.answer_received", "spec.provider_accepted", "spec.accepted", "delivery.published", "verification.completed", "correction.required", "review.opened", "case.opened", "question.requested", "answer.received", "case.escalated", "human.decision", "review.accepted"] as const;
export type { BrokerEvent, BrokerOrder };
