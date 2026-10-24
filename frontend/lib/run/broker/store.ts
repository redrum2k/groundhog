// Live runs in this Next process: each one is a scripted order on Jeff's backend plus a cache of
// the canvas events translated from its stream so far.
import type { RunEvent } from "../contract";
import type { Case } from "../scenario";
import { brokerEvents, decide as decideOn, drive, newRun, type Run } from "./driver";
import { BrokerError, deliveredRows, getDraft, getOrder } from "./client";
import { translate } from "./translate";

interface Live { run: Run; handle: string; translated: RunEvent[]; rows: import("./types").DataRow[]; rowsFor: string }
// One registry for the whole process: in dev, each route handler is its own module instance
// after a recompile, so a module-level Map would split between POST and GET.
const registry = globalThis as unknown as { __brokerRuns?: Map<string, Live>; __brokerNext?: number };
const runs = (registry.__brokerRuns ??= new Map<string, Live>());
const nextHandle = () => `live-${(registry.__brokerNext = (registry.__brokerNext ?? 0) + 1)}`;

export async function startRun(c: Case): Promise<{ id: string; poll_after_ms: number }> {
  const run = await newRun(c);
  const handle = nextHandle();
  const live: Live = { run, handle, translated: [], rows: [], rowsFor: "" };
  runs.set(handle, live);
  void drive(run, () => {});
  return { id: handle, poll_after_ms: 1000 };
}

export async function eventsAfter(handle: string, after: number): Promise<{ events: RunEvent[]; poll_after_ms: number } | { error: string; status: number }> {
  const live = runs.get(handle);
  if (!live) return { error: "Run not found", status: 404 };
  const { run } = live;
  if (!run.id) return run.error ? { error: run.error, status: 502 } : { events: [], poll_after_ms: 1000 };
  try {
    // The interview happens on the draft; the order record exists only from acceptance on
    const record = () => getOrder(run.tokens.customer, run.id).catch((err: unknown) => (err instanceof BrokerError && err.status === 404 ? getDraft(run.tokens.customer, run.id) : Promise.reject(err)));
    const [stream, order] = await Promise.all([brokerEvents(run.tokens.customer, run.id), record()]);
    if (order) {
      const artifacts = order.delivery_artifact_ids ?? [];
      const ids = artifacts.join(",");
      if (ids && ids !== live.rowsFor) { live.rows = await deliveredRows(run.tokens.customer, run.id, artifacts); live.rowsFor = ids; }
      live.translated = translate({ events: stream, order, rows: live.rows }, run.case);
    }
    return { events: live.translated.filter((e) => e.seq > after), poll_after_ms: run.finished && run.error ? 4000 : 1000 };
  } catch (err) {
    return { error: err instanceof Error ? err.message : String(err), status: 502 };
  }
}

export async function decide(handle: string, action: "approve" | "reject" | "ask" | "escalate", note: string) {
  const live = runs.get(handle);
  if (!live) return { status: 404, detail: "Run not found" };
  return decideOn(live.run, action, note);
}

export const runError = (handle: string) => runs.get(handle)?.run.error;
