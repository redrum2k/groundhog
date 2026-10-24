// Recorded rehearsal only. The production backend feed is live.ts; this fixture API is scripted.
"use client";
// Where the canvas gets its events: a recorded scenario played on a timer, or a live run polled
// by seq. Both produce the same RunEvent list, folded by the same function.
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { Binding, ControllerAction, RunEvent } from "./contract";
import { project, type FoldContext, type View } from "./fold";
import { controllerContinuation, holdFor, stamp, type Draft, type Ending } from "./scenario";

export const STUB_API = "/api/run-stub";

export type Feed =
  | { kind: "still"; events: RunEvent[]; ctx: FoldContext } // the whole timeline at once, not playing
  | { kind: "recorded"; events: RunEvent[]; start: number; autoplay: boolean; ctx: FoldContext }
  | { kind: "fixture"; api: string; ending: Ending; before: RunEvent[]; ctx: FoldContext };

export type Status = "idle" | "playing" | "paused" | "waiting" | "done" | "error";
export interface Playback {
  view: View;
  status: Status;
  error?: string;
  live: boolean;
  played: number; // events applied so far
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
  const runId = useRef<string | null>(null);
  const lastSeq = useRef(0); // the live cursor; recorded events before it keep their own seqs
  const live = feed.kind === "fixture";

  // A new feed resets playback
  useEffect(() => {
    runId.current = null;
    setError(undefined);
    if (feed.kind === "still") { setEvents(feed.events); setCursor(feed.events.length); setStatus("done"); return; }
    if (feed.kind === "recorded") { setEvents(feed.events); setCursor(feed.start); setStatus(feed.autoplay ? "playing" : "idle"); return; }
    setEvents(feed.before); setCursor(feed.before.length); setStatus("playing");
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const poll = async () => {
      try {
        if (!runId.current) {
          const res = await fetch(`${feed.api}/runs`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ ending: feed.ending }) });
          if (!res.ok) throw new Error(`Could not start the live run (${res.status})`);
          runId.current = ((await res.json()) as { id: string }).id;
        }
        const res = await fetch(`${feed.api}/runs/${runId.current}/events?after=${lastSeq.current}`, { cache: "no-store" });
        if (!res.ok) throw new Error(`The run stopped answering (${res.status})`);
        const { events: fresh, poll_after_ms } = (await res.json()) as { events: RunEvent[]; poll_after_ms: number };
        if (cancelled) return;
        const next = fresh.filter((e) => e.seq > lastSeq.current);
        if (next.length) {
          lastSeq.current = next[next.length - 1].seq;
          setEvents((prev) => [...prev, ...next.map((e,i)=>({...e,seq:prev.length+i+1}))]);
          setCursor((c) => c + next.length);
        }
        timer = setTimeout(poll, poll_after_ms);
      } catch (err) {
        if (cancelled) return;
        setError(err instanceof Error ? err.message : String(err));
        setStatus("error");
      }
    };
    lastSeq.current = 0;
    void poll();
    return () => { cancelled = true; if (timer) clearTimeout(timer); };
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
    if (feed.kind !== "fixture" || events.length <= feed.before.length) return;
    const last = events[events.length - 1];
    setStatus((s) => (s === "error" ? s : last.type === "step_completed" && last.step === "captured" ? "done" : atControllerGate(events) ? "waiting" : "playing"));
  }, [feed, events]);

  const view = useMemo(() => project(events.slice(0, cursor), feed.ctx), [events, cursor, feed.ctx]);

  const decide = useCallback(async (action: ControllerAction, binding: Binding) => {
    if (feed.kind === "fixture") {
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

  const play = useCallback(() => setStatus((s) => (s === "idle" || s === "paused" ? "playing" : s)), []);
  const pause = useCallback(() => setStatus((s) => (s === "playing" && !live ? "paused" : s)), [live]);
  const skip = useCallback(() => { setCursor(events.length); setStatus(atControllerGate(events) ? "waiting" : "done"); }, [events]);

  return { view, status, error, live, played: cursor, decide, play, pause, skip };
}
