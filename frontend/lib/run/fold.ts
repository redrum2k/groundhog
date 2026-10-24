// Folds one case's event stream into what the canvas and panel show. Pure, so the recorded
// scenario and the live poll go through the same function.
import type {
  Amendment, Binding, ContractLine, ControllerAction, DataContract, Delivery, Dispute, Evidence, JournalEntry, Margin, Message, Payment,
  RuleUpdate, RunEvent, Step, Verdict,
} from "./contract";
import { captionFor, chipFor, type Case, type Ending } from "./scenario";
import type { PaymentStateChanged } from "../runs.generated";

export type NS = "idle" | "running" | "done" | "waiting" | "fail" | "grey";
export type OrbMode = "float" | "carry" | "look" | "inspect" | "wait" | "happy";
export interface Check { passed: boolean; reason?: string; fix?: string; detail?: string }
export interface NodeState {
  step: Step;
  status: NS;
  attempt: number;
  chip?: string;
  waitingOn?: string;
  messages: Message[];
  asked: string[]; // contract lines the agent has asked about
  drafted: ContractLine[];
  pending: Record<string, ContractLine>; // lines the agent has asked about but not settled
  checks: Record<string, Check>;
  evidence: Evidence[];
  verdict?: Verdict;
  decision?: { action: ControllerAction; by: string; note: string };
  delivery?: Delivery;
  contract?: DataContract;
  amendment?: Amendment;
  rule?: RuleUpdate;
  entries?: JournalEntry[];
  margin?: Margin;
  allowedBy: string[];
}
export interface Card { id: string; node: string; text: string; tone: "ev" | "rule" | "claim" }
export interface Coin { text: string; locked?: boolean; done?: boolean }
export interface View {
  nodes: Record<string, NodeState>;
  order: string[]; // step ids in plan order
  orb: { step: string; mode: OrbMode };
  coin: Coin | null;
  loops: string[]; // lane step ids whose work was carried back to Produce
  cards: Card[];
  contract: DataContract;
  caption: string;
  dispute?: Dispute;
  evidence: Record<string, Evidence>;
  deliveries: Delivery[];
  payments: Payment[];
  captured: Record<string, string | null>;
  paymentStates: Record<string, PaymentStateChanged["state"]>;
  lastLane?: string; // the lane step the orb was on before going back up
  started: number; // step starts so far, for the caption's counter
  reviewWindow?: string; // from the server's review deadline, when a live stream sets one
  lastSeq: number;
  binding?: Binding;
}
export interface FoldContext { lane: Case; ending: Ending; learned: boolean; contract: DataContract; live?: boolean }

const blankNode = (step: Step): NodeState => ({ step, status: "idle", attempt: 1, messages: [], asked: [], drafted: [], pending: {}, checks: {}, evidence: [], allowedBy: [] });
const LANE_KINDS = new Set(["investigate", "verdict", "amend", "grey", "decide"]);

export function emptyView(contract: DataContract): View {
  return { nodes: {}, order: [], orb: { step: "clarify", mode: "float" }, coin: null, loops: [], cards: [], contract, caption: "", evidence: {}, deliveries: [], payments: [], captured: {}, paymentStates: {}, started: 0, lastSeq: 0 };
}

const money = (v: View) => v.payments.reduce((sum, p) => sum + p.amount, 0);
function coinFor(v: View): Coin | null {
  if (!v.payments.length) return null;
  const labels: Record<PaymentStateChanged["state"], string> = {
    blocked_parent:"waiting for parent return", awaiting_signature:"awaiting funding",
    funding_pending:"funding pending", funded:"held", capture_pending:"capture pending",
    captured:"captured", void_pending:"return pending", voided:"returned",
    uncertain:"outcome uncertain", failed:"payment needs review",
    expired_not_returned:"expired · not returned", reorg_hold:"reorg hold",
  };
  if (v.payments.some(p => v.paymentStates[p.id])) {
    const states = v.payments.map(p => v.paymentStates[p.id] ?? (p.id in v.captured ? "captured" : "funded"));
    return {
      text:v.payments.map((p,i)=>`$${p.amount} ${labels[states[i]]}${p.mock ? " · mock" : ""}`).join(" + "),
      done:states.every(s=>s==="captured" || s==="voided"),
      locked:states.some(s=>!["captured","voided","awaiting_signature","blocked_parent"].includes(s)),
    };
  }
  const parts = v.payments.map((p) => `$${p.amount}`).join(" + ");
  if (v.payments.every((p) => p.id in v.captured)) return { text: `$${money(v)} captured${v.payments.some((p) => p.mock) ? " · mock" : ""}`, done: true };
  if (v.payments.every((p) => p.rail === "mock")) return { text: `${parts} authorized`, locked: !!v.dispute };
  return { text: `${parts} held${v.payments.some(p => p.mock) ? " · mock" : ""}`, locked: !!v.dispute };
}

/** Applies one event; mutates and returns the same view so callers can fold incrementally. */
export function apply(v: View, e: RunEvent, ctx: FoldContext): View {
  if (e.seq <= v.lastSeq) return v;
  v.lastSeq = e.seq;
  if (e.type === "delivery_ready" && e.delivery.reviewClosesAt) v.reviewWindow = windowLabel(Date.parse(e.delivery.reviewClosesAt) - Date.parse(e.at));
  const caption = ctx.live ? (e.type === "message" ? e.message.text : e.type === "state_changed" ? e.reason ?? e.state : "") : captionFor(e, { lane: ctx.lane, ending: ctx.ending, learned: ctx.learned, captured: money(v), reviewWindow: v.reviewWindow });
  if (e.type === "steps_planned") {
    for (const s of e.steps) { v.nodes[s.id] ??= blankNode(s); v.nodes[s.id].step = s; if (!v.order.includes(s.id)) v.order.push(s.id); }
    return v;
  }
  if (e.type === "caption") { v.caption = e.text; return v; }
  if (e.type === "payment_authorized") { v.payments = [...v.payments.filter(p => p.id !== e.payment.id), e.payment]; v.coin = coinFor(v); return v; }
  if (e.type === "payment_captured") { v.captured[e.paymentId] = e.captureTx; v.coin = coinFor(v); return v; }
  if (e.type === "payment_state_changed") {
    v.payments = [...v.payments.filter(p => p.id !== e.payment.id), e.payment];
    v.paymentStates[e.payment.id] = e.state;
    v.coin = coinFor(v);
    return v;
  }
  // Historical run effects already carried a state, before the explicit payment effect.
  if (e.type === "state_changed" && e.paymentState && v.payments.length === 1) {
    v.paymentStates[v.payments[0].id] = e.paymentState;
    v.coin = coinFor(v);
  }
  const n = v.nodes[e.step];
  if (!n) return v; // an event for a step that was never planned: ignore rather than crash the canvas
  const attempt = e.attempt ?? 1;
  if (attempt > n.attempt) { Object.assign(n, blankNode(n.step), { attempt }); v.cards = v.cards.filter(c => c.node !== e.step); }
  if ("allowedBy" in e && !n.allowedBy.includes(e.allowedBy)) n.allowedBy.push(e.allowedBy);
  switch (e.type) {
    case "state_changed": v.binding = e.binding; n.waitingOn = e.reason ?? undefined; break;
    case "step_started":
      n.status = "running"; n.waitingOn = undefined; v.started += 1;
      if (attempt > 1 && n.step.kind === "produce" && v.lastLane) v.loops = [...v.loops, v.lastLane];
      if (LANE_KINDS.has(n.step.kind)) v.lastLane = e.step;
      v.orb = { step: e.step, mode: n.step.kind === "investigate" ? "inspect" : n.step.kind === "clarify" ? "look" : n.step.kind === "produce" ? "carry" : "float" };
      if (n.step.kind === "review" && attempt === 1 && v.nodes.produce) v.nodes.produce.status = "done";
      break;
    case "step_waiting": n.status = "waiting"; n.waitingOn = e.waitingOn; if (n.step.kind === "decide") v.orb = { step: e.step, mode: "wait" }; break;
    case "step_completed":
      n.status = n.verdict && n.verdict.decidedBy === "rules" ? (n.verdict.kind === "agree" ? "fail" : n.verdict.kind === "grey" ? "grey" : "done") : "done";
      n.waitingOn = undefined;
      if (n.step.kind === "captured") v.orb = { step: e.step, mode: "happy" };
      break;
    case "message": if (n.status === "waiting") n.status = "running"; n.messages.push(e.message); if (e.message.asks) n.asked.push(e.message.asks); break;
    case "contract_line_asked": if (!n.asked.includes(e.line.id)) n.asked.push(e.line.id); n.pending[e.line.id] = e.line; break;
    case "contract_line_approved":
    case "contract_line_drafted": n.drafted.push(e.line); delete n.pending[e.line.id]; break;
    case "contract_approved": n.contract = e.contract; v.contract = e.contract; break;
    case "delivery_ready": n.delivery = e.delivery; v.deliveries = [...v.deliveries.filter((d) => d.version !== e.delivery.version), e.delivery]; break;
    case "check_passed": n.checks[e.lineId] = { passed: true, detail: e.detail ?? undefined }; break;
    case "check_failed": n.checks[e.lineId] = { passed: false, reason: e.reason }; break;
    case "check_fixed": n.checks[e.lineId] = { passed: true, reason: n.checks[e.lineId]?.reason, fix: e.fix, detail: e.fix }; break;
    case "evidence_found":
      n.evidence.push(e.evidence); v.evidence[e.evidence.id] = e.evidence;
      v.cards = [...v.cards, { id: e.evidence.id, node: e.step, text: e.evidence.label, tone: e.evidence.kind === "claim" ? "claim" : "ev" }];
      break;
    case "dispute_opened": v.dispute = e.dispute; v.coin = coinFor(v); break;
    case "verdict": n.verdict = e.verdict; break;
    case "controller_decided": n.decision = { action: e.action, by: e.by, note: e.note }; break;
    case "amendment_signed": n.amendment = e.amendment; break;
    case "rule_updated": n.rule = e.rule; v.cards = [...v.cards, { id: e.rule.id, node: e.step, text: e.rule.label, tone: "rule" }]; break;
    case "books_posted": n.entries = e.entries; n.margin = e.margin ?? undefined; break;
  }
  n.chip = ctx.live ? (n.waitingOn ?? n.status) : chipFor(n.step, {
    status: n.status, attempt: n.attempt, checks: Object.values(n.checks).filter((c) => c.passed).length, lines: v.contract.lines.length, sources: n.evidence.length,
    verdictKind: n.verdict?.kind ?? laneVerdict(v)?.kind, verdictBy: n.verdict?.decidedBy, amendmentPrice: n.amendment?.price ?? laneAmendment(v)?.price,
    waitingOn: n.waitingOn, learned: ctx.learned, disputed: !!v.dispute, decided: n.decision?.action, ruled: !!n.rule,
  });
  if (caption) v.caption = caption;
  return v;
}

/** "10 minutes" or "48 hours", whichever the deadline is closest to. */
const windowLabel = (ms: number) => (ms < 2 * 3_600_000 ? `${Math.max(1, Math.round(ms / 60_000))} minutes` : `${Math.round(ms / 3_600_000)} hours`);

const laneVerdict = (v: View) => (v.nodes.decide ?? v.nodes.verdict)?.verdict;
const laneAmendment = (v: View) => v.nodes.amend?.amendment ?? v.nodes.decide?.amendment;

export function project(events: RunEvent[], ctx: FoldContext): View {
  return events.reduce((v, e) => apply(v, e, ctx), emptyView(ctx.contract));
}

export function bindingFor(v: View): Binding {
  if (v.binding) return v.binding;
  return { deliveryVersion: Math.max(0, ...v.deliveries.map((d) => d.version)), evidenceVersion: Object.keys(v.evidence).length };
}

export const basescan = (tx: string) => `https://sepolia.basescan.org/tx/${tx}`;
