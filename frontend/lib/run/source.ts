"use client";
// Where the canvas gets its events: a recorded scenario played on a timer, or a live run polled
// by seq. Both produce the same RunEvent list, folded by the same function.
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { Binding, ControllerAction, RunEvent } from "./contract";
import { project, type FoldContext, type View } from "./fold";
import { controllerContinuation, holdFor, stamp, type Draft } from "./scenario";

export const LIVE_API = "/api/broker-run";
const DRIP = 110; // ms between events the canvas takes from one poll's burst

export type Feed =
  | { kind: "still"; events: RunEvent[]; ctx: FoldContext } // the whole timeline at once, not playing
  | { kind: "recorded"; events: RunEvent[]; start: number; autoplay: boolean; ctx: FoldContext }
  | { kind: "live"; api: string; body: Record<string, unknown>; before: RunEvent[]; ctx: FoldContext };

export type Status = "idle" | "playing" | "paused" | "waiting" | "done" | "error";
export type BuyerGate = "approve" | "review";
export type BuyerMove = { action: "approve" } | { action: "accept" } | { action: "object"; text: string };
export interface Playback {
  view: View;
  status: Status;
  error?: string;
  live: boolean;
  played: number; // events applied so far
  awaiting: BuyerGate | null; // a live run paused for Summit's move
  /** Summit's move, made by the presenter; null on success, else the server's reason. */
  buyer: (m: BuyerMove) => Promise<string | null>;
  /** The controller's click: appends the recorded continuation, or posts to the live run. */
  decide: (action: ControllerAction, binding: Binding) => Promise<string | null>;
  play: () => void;
  pause: () => void;
  skip: () => void;
}

/** The scenario stops here until a controller clicks; what follows depends on the click. */
const atControllerGate = (events: RunEvent[]) => { const l = events[events.length - 1]; return l?.type === "step_waiting" && l.step === "decide"; };

export function usePlayback(feed: Feed): Playback {
  const [events, setEvents] = useState<RunEvent[]>([]);
  const [cursor, setCursor] = useState(0);
  const [status, setStatus] = useState<Status>("idle");
  const [error, setError] = useState<string>();
  const [awaiting, setAwaiting] = useState<BuyerGate | null>(null);
  const runId = useRef<string | null>(null);
  const lastSeq = useRef(0); // the live cursor; recorded events before it keep their own seqs
  const live = feed.kind === "live";

  // A new feed resets playback
  useEffect(() => {
    runId.current = null;
    setError(undefined);
    setAwaiting(null);
    if (feed.kind === "still") { setEvents(feed.events); setCursor(feed.events.length); setStatus("done"); return; }
    if (feed.kind === "recorded") { setEvents(feed.events); setCursor(feed.start); setStatus(feed.autoplay ? "playing" : "idle"); return; }
    setEvents(feed.before); setCursor(feed.before.length); setStatus("playing");
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    // A poll brings a burst (a question and its answer, a batch of checks); the canvas takes them one at a time,
    // so the chat scrolls continuously and the checklist ticks line by line. Summit's gate waits for the last one.
    const queue: RunEvent[] = [];
    let gate: BuyerGate | null = null;
    let drip: ReturnType<typeof setTimeout> | undefined;
    const release = () => {
      const e = queue.shift();
      if (cancelled || !e) return;
      setEvents((prev) => [...prev, { ...e, seq: prev.length + 1 }]);
      setCursor((c) => c + 1);
      if (queue.length) drip = setTimeout(release, DRIP);
      else setAwaiting(gate);
    };
    const poll = async () => {
      try {
        if (!runId.current) {
          const res = await fetch(`${feed.api}/runs`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(feed.body) });
          if (!res.ok) throw new Error(`Could not start the live run (${res.status})`);
          runId.current = ((await res.json()) as { id: string }).id;
        }
        const res = await fetch(`${feed.api}/runs/${runId.current}/events?after=${lastSeq.current}`, { cache: "no-store" });
        if (!res.ok) throw new Error(`The run stopped answering (${res.status})`);
        const { events: fresh, poll_after_ms, awaiting, error: failure } = (await res.json()) as { events: RunEvent[]; poll_after_ms: number; awaiting?: BuyerGate | null; error?: string };
        if (cancelled) return;
        gate = awaiting ?? null;
        if (failure) { setError(`The scripted parties stopped: ${failure}`); setStatus("error"); return; }
        const next = fresh.filter((e) => e.seq > lastSeq.current);
        if (next.length) {
          lastSeq.current = next[next.length - 1].seq;
          const idle = queue.length === 0;
          queue.push(...next);
          if (idle) release();
        } else if (!queue.length) setAwaiting(gate);
        timer = setTimeout(poll, poll_after_ms);
      } catch (err) {
        if (cancelled) return;
        setError(err instanceof Error ? err.message : String(err));
        setStatus("error");
      }
    };
    lastSeq.current = 0;
    void poll();
    return () => { cancelled = true; if (timer) clearTimeout(timer); if (drip) clearTimeout(drip); };
  }, [feed]);

  // Recorded playback: advance on a timer, stop where the scenario waits on the controller
  useEffect(() => {
    if (feed.kind !== "recorded" || status !== "playing") return;
    if (cursor >= events.length) { setStatus(atControllerGate(events) ? "waiting" : "done"); return; }
    const id = setTimeout(() => setCursor(cursor + 1), cursor > feed.start ? holdFor(events[cursor - 1]) : 400);
    return () => clearTimeout(id);
  }, [feed, status, cursor, events]);

  // Live: status follows the events alone. A decision sets "playing" before its continuation
  // arrives, and re-reading the gate here would flip it straight back to "waiting".
  useEffect(() => {
    if (feed.kind !== "live" || events.length <= feed.before.length) return;
    const last = events[events.length - 1];
    setStatus((s) => (s === "error" ? s : last.type === "step_completed" && last.step === "captured" ? "done" : atControllerGate(events) ? "waiting" : "playing"));
  }, [feed, events]);

  const view = useMemo(() => project(events.slice(0, cursor), feed.ctx), [events, cursor, feed.ctx]);

  const decide = useCallback(async (action: ControllerAction, binding: Binding) => {
    if (feed.kind === "live") {
      const res = await fetch(`${feed.api}/runs/${runId.current}/decisions`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ action, binding }) });
      if (!res.ok) { const { detail } = (await res.json().catch(() => ({ detail: `Request failed (${res.status})` }))) as { detail: string }; return detail; }
      setStatus("playing");
      return null;
    }
    // Recorded: append the continuation for this action
    setEvents((prev) => {
      const kept = prev.slice(0, cursor);
      const drafts: Draft[] = controllerContinuation(action, binding);
      return [...kept, ...stamp("amber", drafts, kept.length)];
    });
    setStatus("playing");
    return null;
  }, [feed, cursor]);

  const buyer = useCallback(async (m: BuyerMove) => {
    if (feed.kind !== "live" || !runId.current) return "No live run to act on";
    const res = await fetch(`${feed.api}/runs/${runId.current}/buyer`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(m) });
    if (!res.ok) { const { detail } = (await res.json().catch(() => ({ detail: `Request failed (${res.status})` }))) as { detail: string }; return detail; }
    setAwaiting(null);
    return null;
  }, [feed]);

  const play = useCallback(() => setStatus((s) => (s === "idle" || s === "paused" ? "playing" : s)), []);
  const pause = useCallback(() => setStatus((s) => (s === "playing" && !live ? "paused" : s)), [live]);
  const skip = useCallback(() => { setCursor(events.length); setStatus(atControllerGate(events) ? "waiting" : "done"); }, [events]);

  return { view, status, error, live, played: cursor, awaiting, buyer, decide, play, pause, skip };
}
