"use client";
// Where the canvas gets its events: a recorded scenario played on a timer, or a live run polled
// by seq. Both produce the same RunEvent list, folded by the same function.
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { Binding, ControllerAction, RunEvent } from "./contract";
import { project, type RunState } from "./fold";
import { controllerContinuation, holdFor, stamp, type Draft } from "./scenario";

export const STUB_API = "/api/run-stub";

export type Feed =
  | { kind: "still"; events: RunEvent[] } // the whole timeline at once, not playing
  | { kind: "recorded"; events: RunEvent[]; start: number }
  | { kind: "live"; api: string; ending: "disagree" | "agree" | "controller"; before: RunEvent[] };

export type Status = "idle" | "playing" | "waiting" | "done" | "error";
export interface Playback {
  run: RunState;
  status: Status;
  error?: string;
  live: boolean;
  /** The controller's click: appends the recorded continuation, or posts to the live run. */
  decide: (action: ControllerAction, binding: Binding) => Promise<string | null>;
  skip: () => void;
}

/** The scenario stops here until a controller clicks; what follows depends on the click. */
const atControllerGate = (events: RunEvent[]) => { const l = events[events.length - 1]; return l?.type === "step_waiting" && l.step === "controller"; };

export function usePlayback(source: Feed): Playback {
  const [events, setEvents] = useState<RunEvent[]>([]);
  const [cursor, setCursor] = useState(0);
  const [status, setStatus] = useState<Status>("idle");
  const [error, setError] = useState<string>();
  const runId = useRef<string | null>(null);
  const lastSeq = useRef(0); // the live cursor; recorded events before it keep their own seqs
  const live = source.kind === "live";

  // A new source resets playback
  useEffect(() => {
    runId.current = null;
    setError(undefined);
    if (source.kind === "still") { setEvents(source.events); setCursor(source.events.length); setStatus("done"); return; }
    if (source.kind === "recorded") { setEvents(source.events); setCursor(source.start); setStatus("playing"); return; }
    setEvents(source.before); setCursor(source.before.length); setStatus("playing");
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const poll = async () => {
      try {
        if (!runId.current) {
          const res = await fetch(`${source.api}/runs`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ ending: source.ending }) });
          if (!res.ok) throw new Error(`Could not start the live run (${res.status})`);
          runId.current = ((await res.json()) as { id: string }).id;
        }
        const after = lastSeq.current;
        const res = await fetch(`${source.api}/runs/${runId.current}/events?after=${after}`, { cache: "no-store" });
        if (!res.ok) throw new Error(`The run stopped answering (${res.status})`);
        const { events: fresh, poll_after_ms } = (await res.json()) as { events: RunEvent[]; poll_after_ms: number };
        if (cancelled) return;
        if (fresh.length) {
          const next = fresh.filter((e) => e.seq > lastSeq.current);
          lastSeq.current = next.length ? next[next.length - 1].seq : lastSeq.current;
          setEvents((prev) => [...prev, ...next]);
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
  }, [source]);

  // Recorded playback: advance on a timer, pause where the scenario waits on the controller
  useEffect(() => {
    if (source.kind !== "recorded" || status !== "playing") return;
    if (cursor >= events.length) { setStatus(atControllerGate(events) ? "waiting" : "done"); return; }
    const id = setTimeout(() => setCursor(cursor + 1), cursor > source.start ? holdFor(events[cursor - 1]) : 0);
    return () => clearTimeout(id);
  }, [source, status, cursor, events]);

  // Live: the stream is done when its last event closes the books or a learned step
  useEffect(() => {
    if (source.kind !== "live" || status !== "playing" || events.length <= source.before.length) return;
    const last = events[events.length - 1];
    if (last?.type === "step_completed" && (last.step === "books" || last.step === "learned")) setStatus("done");
    else if (atControllerGate(events)) setStatus("waiting");
  }, [source, status, events]);

  const run = useMemo(() => project(events.slice(0, cursor)), [events, cursor]);

  const decide = useCallback(async (action: ControllerAction, binding: Binding) => {
    if (source.kind === "live") {
      const res = await fetch(`${source.api}/runs/${runId.current}/decisions`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ action, binding }) });
      if (!res.ok) { const { detail } = (await res.json().catch(() => ({ detail: `Request failed (${res.status})` }))) as { detail: string }; return detail; }
      setStatus("playing");
      return null;
    }
    // Recorded: drop the scripted continuation and append the one for this action
    setEvents((prev) => {
      const kept = prev.slice(0, cursor);
      const drafts: Draft[] = controllerContinuation(action, binding);
      return [...kept, ...stamp("amber", drafts, kept.length)];
    });
    setStatus("playing");
    return null;
  }, [source, cursor]);

  const skip = useCallback(() => { setCursor(events.length); setStatus("done"); }, [events.length]);

  return { run, status, error, live, decide, skip };
}
