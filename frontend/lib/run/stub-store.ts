// In-memory stand-in for the backend's run log, used by the /api/run-stub routes until Nikita's
// events endpoint lands. It releases the amber lane's recorded events on a clock and holds at
// the controller step until a decision is posted, so the canvas exercises the real seam.
import type { Binding, ControllerAction, RunEvent } from "./contract";
import { amberEnding, amberOpen, controllerContinuation, holdFor, stamp, type Draft, type Ending } from "./scenario";

interface Run { id: string; ending: Ending; events: RunEvent[]; releaseAt: number[]; waitingForController: boolean }
const runs = new Map<Run["id"], Run>();
let nextId = 1;

function schedule(run: Run, drafts: Draft[], from: number) {
  const events = stamp("amber", drafts, run.events.length);
  let at = from;
  for (const e of events) { run.events.push(e); run.releaseAt.push(at); at += holdFor(e); }
}

export function createRun(ending: Ending): Run {
  const run: Run = { id: `stub-${nextId++}`, ending, events: [], releaseAt: [], waitingForController: ending === "maya" };
  schedule(run, [...amberOpen(ending, false), ...amberEnding(ending, false)], Date.now());
  runs.set(run.id, run);
  return run;
}

export function eventsAfter(id: string, seq: number): RunEvent[] | null {
  const run = runs.get(id);
  if (!run) return null;
  const now = Date.now();
  return run.events.filter((e, i) => e.seq > seq && run.releaseAt[i] <= now);
}

export type DecisionResult = { ok: true } | { ok: false; status: 404 | 409; detail: string };
export function decide(id: string, action: ControllerAction, binding: Binding): DecisionResult {
  const run = runs.get(id);
  if (!run) return { ok: false, status: 404, detail: "Run not found" };
  if (!run.waitingForController) return { ok: false, status: 409, detail: "The controller step is not waiting for a decision" };
  if (run.releaseAt.some((t) => t > Date.now())) return { ok: false, status: 409, detail: "The run is still moving; refetch and try again" };
  const current = currentBinding(run);
  if (binding.deliveryVersion !== current.deliveryVersion || binding.evidenceVersion !== current.evidenceVersion) return { ok: false, status: 409, detail: "Evidence or delivery changed since this was shown; review again" };
  run.waitingForController = action === "ask" || action === "escalate";
  schedule(run, controllerContinuation(action, current), Date.now());
  return { ok: true };
}

/** The versions a decision must be bound to: the delivery under review plus evidence found on this lane. */
function currentBinding(run: Run): Binding {
  return { deliveryVersion: 1, evidenceVersion: run.events.filter((e) => e.type === "evidence_found").length };
}
