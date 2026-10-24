// Live runs in this Next process: each one is a scripted order on Jeff's backend plus a cache of
// the canvas events translated from its stream so far.
import type { RunEvent } from "../contract";
import type { Case } from "../scenario";
import { brokerEvents, buyerMove as moveOn, decide as decideOn, drive, newRun, type BuyerGate, type BuyerMove, type Run } from "./driver";
import { BrokerError, deliveredRows, getDraft, getOrder } from "./client";
import { translate } from "./translate";
import type { BrokerCheck, DataRow } from "./types";

interface Live { run: Run; handle: string; translated: RunEvent[]; checksBySeq: Record<number, BrokerCheck[]>; rowsByVersion: Record<number, DataRow[]> }
// One registry for the whole process: in dev, each route handler is its own module instance
// after a recompile, so a module-level Map would split between POST and GET.
const registry = globalThis as unknown as { __brokerRuns?: Map<string, Live>; __brokerNext?: number };
const runs = (registry.__brokerRuns ??= new Map<string, Live>());
const nextHandle = () => `live-${(registry.__brokerNext = (registry.__brokerNext ?? 0) + 1)}`;

export async function startRun(c: Case): Promise<{ id: string; poll_after_ms: number }> {
  const run = await newRun(c);
  const handle = nextHandle();
  const live: Live = { run, handle, translated: [], checksBySeq: {}, rowsByVersion: {} };
  runs.set(handle, live);
  void drive(run, () => {});
  return { id: handle, poll_after_ms: 1000 };
}

// server_time: this bridge only runs on loopback beside the backend, so its clock is the deadlines' clock
export interface Poll { events: RunEvent[]; poll_after_ms: number; awaiting: BuyerGate | null; server_time: string; error?: string }
export async function eventsAfter(handle: string, after: number): Promise<Poll | { error: string; status: number }> {
  const live = runs.get(handle);
  if (!live) return { error: "Run not found", status: 404 };
  const { run } = live;
  if (!run.id) return run.error ? { error: run.error, status: 502 } : { events: [], poll_after_ms: 1000, awaiting: null, server_time: new Date().toISOString() };
  try {
    // The interview happens on the draft; the order record exists only from acceptance on
    const record = () => getOrder(run.tokens.customer, run.id).catch((err: unknown) => (err instanceof BrokerError && err.status === 404 ? getDraft(run.tokens.customer, run.id) : Promise.reject(err)));
    const [stream, order] = await Promise.all([brokerEvents(run.tokens.customer, run.id), record()]);
    if (order) {
      // Each poll sees the record as it is now; keep what the latest verification and delivery held
      const b = order.base_order?.order;
      const lastVerification = stream.filter((e) => e.type === "verification.completed").at(-1)?.sequence;
      if (lastVerification && b?.data_verification && !(lastVerification in live.checksBySeq)) live.checksBySeq[lastVerification] = b.data_verification.checks;
      const version = b?.binding?.delivery_version ?? 0;
      if (version && !(version in live.rowsByVersion)) live.rowsByVersion[version] = await deliveredRows(run.tokens.customer, run.id, order.delivery_artifact_ids ?? []);
      live.translated = translate({ events: stream, order, checksBySeq: live.checksBySeq, rowsByVersion: live.rowsByVersion }, run.case);
    }
    return { events: live.translated.filter((e) => e.seq > after), poll_after_ms: run.finished && run.error ? 4000 : 1000, awaiting: run.awaiting, server_time: new Date().toISOString(), ...(run.error ? { error: run.error } : {}) };
  } catch (err) {
    return { error: err instanceof Error ? err.message : String(err), status: 502 };
  }
}

export async function decide(handle: string, action: "approve" | "reject" | "ask" | "escalate", note: string) {
  const live = runs.get(handle);
  if (!live) return { status: 404, detail: "Run not found" };
  // The click can land while the scripted provider is still supplying the clarification; the
  // backend would then recheck stale sources and keep the hold. Wait for the parties first.
  await Promise.race([live.run.ready, new Promise<void>((r) => setTimeout(r, 25_000))]);
  return decideOn(live.run, action, note);
}

export function buyerMove(handle: string, m: BuyerMove) {
  const live = runs.get(handle);
  if (!live) return { status: 404, detail: "Run not found" };
  return moveOn(live.run, m);
}

export const runError = (handle: string) => runs.get(handle)?.run.error;
