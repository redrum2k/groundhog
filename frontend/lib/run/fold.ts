// Folds one case's event stream into what the canvas and panel show. Pure, so the recorded
// scenario and the live poll go through the same function.
import type { SourceLine,
  Amendment, Binding, ContractLine, ControllerAction, DataContract, Delivery, Dispute, Evidence, JournalEntry, Margin, Message, Payment,
  RuleUpdate, RunEvent, Step, Verdict,
} from "./contract";
import { captionFor, chipFor, type Case, type Ending } from "./scenario";
import type { PaymentStateChanged } from "../runs.generated";
import { formatCanvasMajor } from "../money";

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
  source?: SourceLine[]; // what the agent read at the source while investigating
}
export interface Card { id: string; node: string; text: string; tone: "ev" | "rule" | "claim" }
// locked: the funds are held, a calm state. alert: a dispute or a payment problem, the only time it turns amber.
export interface Coin { text: string; locked?: boolean; alert?: boolean; done?: boolean; returned?: boolean }
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
export interface FoldContext { lane: Case; ending: Ending; learned: boolean; contract: DataContract; live?: boolean; narrated?: boolean /* the stream carries its own caption events; no scenario captions */ }

const blankNode = (step: Step): NodeState => ({ step, status: "idle", attempt: 1, messages: [], asked: [], drafted: [], pending: {}, checks: {}, evidence: [], allowedBy: [] });
const LANE_KINDS = new Set(["investigate", "verdict", "amend", "grey", "decide"]);

// The recorded demo narrates the groundhog's visit to the database itself (source_checked). The live backend only
// reports the investigation as evidence events, so the same three lines are derived here: each cited cell ticks the
// next line and the last one waits for the finding. An evidence id carries the obligation it answers
// (job:dataset:geography:0), which names the contract line being read.
const sourceVisit = (lines: number): SourceLine[] => [
  { id: "src-pin", text: "Accepted sources · as pinned at acceptance", checked: false },
  { id: "src-lines", text: `${lines || "The"} contract lines · against the source`, checked: false },
  { id: "src-rows", text: "Delivered rows · against the source", checked: false },
];
function readAtSource(lines: SourceLine[], evidenceId: string): SourceLine[] {
  const obligation = evidenceId.split(":").slice(1, -1).pop();
  const next = lines.findIndex((l) => !l.checked && l.id !== "src-rows");
  return lines.map((l, i) => i !== next ? l : { ...l, checked: true, text: l.id === "src-lines" && obligation ? `${obligation[0].toUpperCase()}${obligation.slice(1)} line · against the source` : l.text });
}
const allRead = (lines: SourceLine[]): SourceLine[] => lines.map((l) => ({ ...l, checked: true }));

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
    const returned = states.every(s=>s==="voided");
    return {
      text:v.payments.map((p,i)=>`$${formatCanvasMajor(p.amount)} ${labels[states[i]]}`).join(" + "),
      done:!returned && states.every(s=>s==="captured" || s==="voided"),
      returned,
      locked:states.some(s=>!["captured","voided","awaiting_signature","blocked_parent"].includes(s)),
      // there is no dispute-closed event, but a capture or return only starts once it's resolved, so its amber ends there
      alert:(!!v.dispute && states.includes("funded")) || states.some(s=>["uncertain","failed","expired_not_returned","reorg_hold"].includes(s)),
    };
  }
  const parts = v.payments.map((p) => `$${formatCanvasMajor(p.amount)}`).join(" + ");
  if (v.payments.every((p) => p.id in v.captured)) return { text: `$${formatCanvasMajor(money(v))} captured`, done: true };
  if (v.payments.every((p) => p.rail === "mock")) return { text: `${parts} authorized`, locked: true, alert: !!v.dispute };
  return { text: `${parts} held`, locked: true, alert: !!v.dispute };
}

function settlementProgress(v: View, state: PaymentStateChanged["state"]) {
  const capture = v.nodes.captured;
  if (!capture) return;
  if (state === "void_pending" || state === "voided") {
    for (const key of ["review", "investigate"]) {
      const node = v.nodes[key];
      if (node) { node.status = "done"; node.waitingOn = undefined; node.chip = "Review ended"; }
    }
    const human = v.nodes.decide;
    if (human?.decision?.action === "approve") {
      human.status = "done"; human.waitingOn = undefined; human.chip = "Return approved";
    }
    capture.status = state === "voided" ? "done" : "running";
    capture.step = {...capture.step, title:state === "voided" ? "Funds returned" : "Return pending",
      detail:state === "voided" ? "Confirmed return of uncaptured funds" : "Return approved; waiting for payment confirmation"};
    capture.waitingOn = state === "voided" ? undefined : "Waiting for return confirmation";
    capture.chip = capture.waitingOn ?? "Returned";
    v.orb = {step:"captured",mode:state === "voided" ? "happy" : "wait"};
    v.caption = state === "voided" ? "The return is confirmed. Funds have been returned to the buyer." : "The return is approved. Waiting for confirmation; funds are not yet returned.";
  } else if (state === "capture_pending" || state === "captured") {
    const review = v.nodes.review;
    if (review) { review.status = "done"; review.waitingOn = undefined; review.chip = "Review complete"; }
    capture.status = state === "captured" ? "done" : "running";
    capture.step = {...capture.step,
      title: state === "captured" ? "Captured" : "Release pending",
      detail: state === "captured" ? "Confirmed settlement and recorded booking" : "Review complete; waiting for payment confirmation",
    };
    capture.waitingOn = state === "captured" ? undefined : "Waiting for payment confirmation";
    capture.chip = capture.waitingOn ?? "Confirmed";
    v.orb = {step: "captured", mode: state === "captured" ? "happy" : "wait"};
  } else if (capture.status !== "idle") {
    if (state === "funded") {
      capture.status = "idle";
      capture.step = {...capture.step, title: "Captured", detail: "Confirmed settlement and recorded booking"};
      capture.waitingOn = undefined;
      capture.chip = undefined;
      if (v.nodes.review) { v.nodes.review.status = "running"; v.nodes.review.chip = "Review required"; }
      v.orb = {step: "review", mode: "wait"};
    } else {
      capture.status = "waiting";
      capture.step = {...capture.step, title: "Payment review", detail: "Check the current payment status"};
      capture.waitingOn = "Payment is not confirmed; check its current status";
      capture.chip = capture.waitingOn;
      v.orb = {step: "captured", mode: "wait"};
    }
  }
}

/** Applies one event; mutates and returns the same view so callers can fold incrementally. */
export function apply(v: View, e: RunEvent, ctx: FoldContext): View {
  if (e.seq <= v.lastSeq) return v;
  v.lastSeq = e.seq;
  if (e.type === "delivery_ready" && e.delivery.reviewClosesAt) v.reviewWindow = windowLabel(Date.parse(e.delivery.reviewClosesAt) - Date.parse(e.at));
  const caption = ctx.live ? (e.type === "message" ? e.message.text : e.type === "state_changed" ? e.reason ?? "" : "") : ctx.narrated ? "" : captionFor(e, { lane: ctx.lane, ending: ctx.ending, learned: ctx.learned, captured: money(v), reviewWindow: v.reviewWindow });
  if (e.type === "steps_planned") {
    for (const s of e.steps) { v.nodes[s.id] ??= blankNode(s); v.nodes[s.id].step = s; if (!v.order.includes(s.id)) v.order.push(s.id); }
    return v;
  }
  if (e.type === "caption") { v.caption = e.text; return v; }
  if (e.type === "source_checked") { const n = v.nodes[e.step]; if (n) n.source = e.lines; return v; }
  if (e.type === "payment_authorized") { v.payments = [...v.payments.filter(p => p.id !== e.payment.id), e.payment]; v.coin = coinFor(v); return v; }
  if (e.type === "payment_captured") { v.captured[e.paymentId] = e.captureTx; v.coin = coinFor(v); return v; }
  if (e.type === "payment_state_changed") {
    v.payments = [...v.payments.filter(p => p.id !== e.payment.id), e.payment];
    v.paymentStates[e.payment.id] = e.state;
    v.coin = coinFor(v);
    if (ctx.live) settlementProgress(v, e.state);
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
    case "state_changed":
      v.binding = e.binding; n.waitingOn = e.reason ?? undefined;
      if (ctx.live && e.state === "human_review") {
        for (const key of ["review", "investigate", "decide"]) {
          const node = v.nodes[key];
          if (node) { node.status = "waiting"; node.waitingOn = "Human review required"; }
        }
        v.orb = {step:"decide",mode:"wait"};
      }
      if (ctx.live && e.paymentState) settlementProgress(v, e.paymentState);
      break;
    case "step_started":
      n.status = "running"; n.waitingOn = undefined; v.started += 1;
      if (attempt > 1 && n.step.kind === "produce" && v.lastLane) v.loops = [...v.loops, v.lastLane];
      if (LANE_KINDS.has(n.step.kind)) v.lastLane = e.step;
      v.orb = { step: e.step, mode: n.step.kind === "investigate" ? "inspect" : n.step.kind === "clarify" ? "look" : n.step.kind === "produce" ? "carry" : "float" };
      if (n.step.kind === "review" && attempt === 1 && v.nodes.produce) v.nodes.produce.status = "done";
      if (ctx.live && n.step.kind === "investigate") n.source = sourceVisit(v.contract.lines.length);
      break;
    case "step_waiting": n.status = "waiting"; n.waitingOn = e.waitingOn; if (n.step.kind === "decide") v.orb = { step: e.step, mode: "wait" }; break;
    case "step_completed":
      // A completed live assessment is not itself a failed operation or a repair.
      // Real failed delivery checks retain their own check_failed events.
      n.status = n.verdict?.kind === "grey" ? "grey" : !ctx.live && n.verdict?.decidedBy === "rules" && n.verdict.kind === "agree" ? "fail" : "done";
      n.waitingOn = undefined;
      if (n.step.kind === "captured") v.orb = { step: e.step, mode: "happy" };
      if (ctx.live && n.source) n.source = allRead(n.source);
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
      if (ctx.live && n.source) n.source = readAtSource(n.source, e.evidence.id);
      break;
    case "dispute_opened": v.dispute = e.dispute; v.coin = coinFor(v); break;
    case "verdict":
      n.verdict = e.verdict;
      if (ctx.live) {
        n.status = e.verdict.kind === "grey" ? "grey" : "done";
        const investigation = v.nodes.investigate;
        if (investigation) {
          investigation.status = e.verdict.kind === "grey" ? "waiting" : "done";
          investigation.waitingOn = e.verdict.kind === "grey" ? investigation.waitingOn ?? "Waiting for evidence or human review" : undefined;
          investigation.chip = investigation.waitingOn ?? "Assessment complete";
          if (investigation.source) investigation.source = allRead(investigation.source); // the finding is in: nothing left to read
        }
        v.orb = {step: e.step, mode: "wait"};
      }
      break;
    case "controller_decided": n.decision = { action: e.action, by: e.by, note: e.note }; break;
    case "amendment_signed": n.amendment = e.amendment; break;
    case "rule_updated": n.rule = e.rule; v.cards = [...v.cards, { id: e.rule.id, node: e.step, text: e.rule.label, tone: "rule" }]; break;
    case "books_posted": n.entries = e.entries; n.margin = e.margin ?? undefined; break;
  }
  n.chip = ctx.live ? (n.waitingOn ?? n.status) : chipFor(n.step, {
    status: n.status, attempt: n.attempt, checks: Object.values(n.checks).filter((c) => c.passed).length, lines: v.contract.lines.length, sources: n.evidence.length,
    verdictKind: n.verdict?.kind ?? laneVerdict(v)?.kind, verdictBy: n.verdict?.decidedBy, amendmentPrice: n.amendment?.price ?? laneAmendment(v)?.price,
    waitingOn: n.waitingOn, learned: ctx.learned, disputed: !!v.dispute, decided: n.decision?.action, ruled: !!n.rule, window: v.reviewWindow,
  });
  if (caption) v.caption = caption;
  if (ctx.live && e.type === "state_changed" && e.paymentState === "capture_pending") v.caption = "Review complete. Waiting for payment confirmation.";
  const paymentState = v.payments.length === 1 ? v.paymentStates[v.payments[0].id] : undefined;
  // Repeated human-review effects during reconciliation must not erase an approved return.
  if (ctx.live && (paymentState === "void_pending" || paymentState === "voided")) settlementProgress(v, paymentState);
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
