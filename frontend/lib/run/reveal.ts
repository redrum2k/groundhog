"use client";
import { useEffect, useMemo, useRef, useState } from "react";
import type { RunEvent } from "./contract";

// The deterministic backend finishes an investigation in milliseconds and one poll. Folded as it arrives, the
// groundhog's visit to the database would open and close in a single render. So the live route holds the finding
// until the groundhog has walked over and read its three lines, the way the recorded feed drips a burst. Everything
// else shows as it arrives, and an investigation that started a while ago (a reload) shows its history at once.
export const VISIT = { walk: 2200, line: 500, finding: 700 } as const; // ms: the walk over, each line read, then the verdict
const FRESH = 30_000;
const LINES = 3;

interface Visit { key: string; read: number; done: boolean }
const key = (e: RunEvent) => `${e.seq}@${e.at}`; // the same seq comes around again on the next run

export function useRevealed(events: RunEvent[]): { events: RunEvent[]; read: number } {
  const [visit, setVisit] = useState<Visit>();
  const timers = useRef<ReturnType<typeof setTimeout>[]>([]);
  useEffect(() => () => timers.current.forEach(clearTimeout), []);
  // the investigation being read: the latest one that started just now
  let opening: RunEvent | undefined;
  for (const e of events) if (e.type === "step_started" && e.step === "investigate" && Math.abs(Date.now() - Date.parse(e.at)) < FRESH) opening = e;
  const openingKey = opening ? key(opening) : undefined;
  const current = visit?.key === openingKey ? visit : undefined;
  const held = opening && !current?.done ? opening.seq : Infinity; // verdicts after this seq wait
  let cursor = 0;
  for (const e of events) { if (e.type === "verdict" && e.seq > held) break; cursor = e.seq; }
  useEffect(() => {
    if (!openingKey || visit?.key === openingKey) return;
    timers.current.forEach(clearTimeout);
    setVisit({ key: openingKey, read: 0, done: false });
    timers.current = [
      ...Array.from({ length: LINES }, (_, i) => setTimeout(() => setVisit((v) => v && { ...v, read: i + 1 }), VISIT.walk + i * VISIT.line)),
      setTimeout(() => setVisit((v) => v && { ...v, done: true }), VISIT.walk + (LINES - 1) * VISIT.line + VISIT.finding),
    ];
  }, [openingKey, visit]);
  const shown = useMemo(() => events.filter((e) => e.seq <= cursor), [events, cursor]);
  return { events: shown, read: current?.read ?? 0 };
}
