// Folds the event stream into what the canvas shows. Pure, so the recorded scenario and the live
// poll go through the same function.
import type {
  Amendment, Binding, ContractLine, ControllerAction, DataContract, Delivery, Dispute, Evidence, JournalEntry, Margin, Message, Payment,
  RuleUpdate, RunEvent, Source, Step, Track, Verdict, VerdictKind,
} from "./contract";

export type NodeStatus = "idle" | "running" | "waiting" | "done";
export interface Check { passed: boolean; reason?: string; fix?: string }
export interface NodeState {
  status: NodeStatus;
  waitingOn?: string;
  messages: Message[];
  drafted: ContractLine[]; // contract lines drafted in this step, in order
  checks: Record<string, Check>; // by contract line id
  checkOrder: string[];
  evidence: Evidence[];
  verdict?: Verdict;
  decision?: { action: ControllerAction; by: string; note: string };
  delivery?: Delivery;
  contract?: DataContract;
  amendment?: Amendment;
  rule?: RuleUpdate;
  ruleApplied?: { ruleId: string; outcome: VerdictKind };
  entries?: JournalEntry[];
  margin?: Margin;
  allowedBy: string[]; // every policy line that let this step act
}
export interface TrackState {
  steps: Step[];
  drafted: ContractLine[];
  dispute?: Dispute;
  contract?: DataContract;
  amendment?: Amendment;
  payments: Payment[];
  // Captures live on the lane, not the payment: each lane is a different ending for the same order
  captured: Record<string, string | null>; // payment id -> capture tx, null when mock
  evidenceVersion: number;
  deliveryVersion: number;
}
export interface RunState {
  tracks: Record<Track, TrackState>;
  nodes: Record<string, NodeState>;
  evidence: Record<string, Evidence>;
  active?: { track: Track; step: string };
  lastSeq: number;
}

export const nodeKey = (track: Track, step: string) => `${track}/${step}`;
const blankNode = (): NodeState => ({ status: "idle", messages: [], drafted: [], checks: {}, checkOrder: [], evidence: [], allowedBy: [] });
const blankTrack = (): TrackState => ({ steps: [], drafted: [], payments: [], captured: {}, evidenceVersion: 0, deliveryVersion: 0 });
export const emptyRun = (): RunState => ({
  tracks: { shared: blankTrack(), red: blankTrack(), green: blankTrack(), amber: blankTrack() }, nodes: {}, evidence: {}, lastSeq: 0,
});

/** Applies one event; mutates and returns the same state so callers can fold incrementally. */
export function apply(run: RunState, e: RunEvent): RunState {
  run.lastSeq = Math.max(run.lastSeq, e.seq);
  const t = run.tracks[e.track];
  if (e.type === "steps_planned") {
    t.steps.push(...e.steps);
    for (const s of e.steps) run.nodes[nodeKey(e.track, s.id)] ??= blankNode();
    return run;
  }
  if (e.type === "payment_authorized") { t.payments.push(e.payment); return run; }
  if (e.type === "payment_captured") { t.captured[e.paymentId] = e.captureTx; return run; }
  const n = (run.nodes[nodeKey(e.track, e.step)] ??= blankNode());
  if ("allowedBy" in e && !n.allowedBy.includes(e.allowedBy)) n.allowedBy.push(e.allowedBy);
  const check = (id: string, c: Check) => { if (!(id in n.checks)) n.checkOrder.push(id); n.checks[id] = c; };
  switch (e.type) {
    case "step_started": n.status = "running"; run.active = { track: e.track, step: e.step }; break;
    case "step_waiting": n.status = "waiting"; n.waitingOn = e.waitingOn; break;
    case "step_completed": n.status = "done"; n.waitingOn = undefined; break;
    case "message": n.status = n.status === "waiting" ? "running" : n.status; n.messages.push(e.message); break;
    case "contract_line_drafted": n.drafted.push(e.line); t.drafted.push(e.line); break;
    case "contract_approved": n.contract = t.contract = e.contract; break;
    case "delivery_ready": n.delivery = e.delivery; t.deliveryVersion = Math.max(t.deliveryVersion, e.delivery.version); break;
    case "check_passed": check(e.lineId, { passed: true }); break;
    case "check_failed": check(e.lineId, { passed: false, reason: e.reason }); break;
    case "check_fixed": check(e.lineId, { passed: true, reason: n.checks[e.lineId]?.reason, fix: e.fix }); break;
    case "evidence_found": n.evidence.push(e.evidence); run.evidence[e.evidence.id] = e.evidence; t.evidenceVersion += 1; break;
    case "dispute_opened": t.dispute = e.dispute; break;
    case "verdict": n.verdict = e.verdict; break;
    case "controller_decided": n.decision = { action: e.action, by: e.by, note: e.note }; break;
    case "amendment_approved": n.amendment = t.amendment = e.amendment; break;
    case "rule_updated": n.rule = e.rule; break;
    case "rule_applied": n.ruleApplied = { ruleId: e.ruleId, outcome: e.outcome }; break;
    case "books_posted": n.entries = e.entries; n.margin = e.margin; break;
  }
  return run;
}

export function project(events: RunEvent[]): RunState {
  return events.reduce(apply, emptyRun());
}

/** The contract lines a check on this track is measured against. */
export function linesFor(run: RunState, track: Track): ContractLine[] {
  const t = run.tracks[track];
  return (t.contract ?? t.amendment ?? run.tracks.shared.contract)?.lines ?? [];
}

/** Lines drafted so far on a track, falling back to the approved contract. */
export function draftedFor(run: RunState, track: Track): ContractLine[] {
  const t = run.tracks[track];
  return t.drafted.length ? t.drafted : run.tracks.shared.drafted.length ? run.tracks.shared.drafted : linesFor(run, track);
}

export function bindingFor(run: RunState, track: Track): Binding {
  const t = run.tracks[track], s = run.tracks.shared;
  return { deliveryVersion: Math.max(t.deliveryVersion, s.deliveryVersion), evidenceVersion: t.evidenceVersion + s.evidenceVersion };
}

export type CoinState = "authorized" | "locked" | "captured";
export interface Coin { amount: number; state: CoinState; mock: boolean; tx: string | null }

/** The money the orb carries on a track: the order's authorization plus any the lane added. */
export function coinFor(run: RunState, track: Track): Coin | null {
  const t = run.tracks[track];
  const payments = track === "shared" ? t.payments : [...run.tracks.shared.payments, ...t.payments];
  if (!payments.length) return null;
  const captured = payments.every((p) => p.id in t.captured);
  return {
    amount: payments.reduce((sum, p) => sum + p.amount, 0),
    state: captured ? "captured" : t.dispute ? "locked" : "authorized",
    mock: payments.some((p) => p.mock),
    tx: payments.map((p) => t.captured[p.id]).find(Boolean) ?? null,
  };
}

/** Where a citation lands: the node that holds the source, or nothing when it isn't on the canvas. */
export function locate(run: RunState, source: Source): { key: string; track: Track; step: string } | null {
  if (source.kind === "none") return null;
  const key = nodeKey(source.track, source.step);
  return run.nodes[key] ? { key, track: source.track, step: source.step } : null;
}

export const basescan = (tx: string) => `https://sepolia.basescan.org/tx/${tx}`;
