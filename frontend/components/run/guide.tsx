"use client";
import { animate } from "motion/react";
import { createContext, useContext, useLayoutEffect, useRef, useState, type ReactNode, type RefObject } from "react";
import type { OrbMode } from "../../lib/run/fold";
import Orb from "./orb";

// The customer view's orb walks the buyer through the order: it waits beside Summit's open decision,
// inspects an objected delivery with its magnifier, and sits beside the interview while it asks.
// Each place it can be is a slot; the orb lives in one slot at a time and flies between them.

export type Stop = "home" | "transcript" | "decision" | "inspect";
const MODE: Record<Stop, OrbMode> = { home: "float", transcript: "look", decision: "wait", inspect: "float" };
const EASE_IN_OUT = [0.77, 0, 0.175, 1] as const; // --ease-in-out, the canvas orb's travel curve

const Guide = createContext<{ at: Stop; mood: Partial<Record<Stop, OrbMode>> } | null>(null); // mood: a stop's mode when the view knows better
export const GuideProvider = Guide.Provider;

/** Where the orb can stand; `orb` replaces the plain one there (the inspector). Outside the customer view it renders `fallback`. */
export function OrbSlot({ name, orb, fallback }: { name: Stop; orb?: ReactNode; fallback?: ReactNode }) {
  const guide = useContext(Guide);
  if (!guide) return <>{fallback}</>;
  return (
    <span className={`orb-slot slot-${name}`} data-orb-slot={name}>
      {guide.at === name ? orb ?? <span className="cust-orb"><Orb mode={guide.mood[name] ?? MODE[name]} /></span> : fallback}
    </span>
  );
}

/** A copy flies above the page from `f` to the real orb, re-aiming every frame: the sticky header, a clipping
 *  transcript box or a smooth scroll can't strand it. The real orb shows on landing. Returns how to cancel it. */
function flyTo(el: HTMLElement, f: DOMRect) {
  const flyer = el.cloneNode(true) as HTMLElement;
  flyer.classList.add("orb-flyer");
  el.style.visibility = "hidden";
  document.body.append(flyer);
  const place = (p: number) => {
    const t = el.getBoundingClientRect(), mix = (a: number, b: number) => a + (b - a) * p;
    flyer.style.transform = `translate(${mix(f.left, t.left)}px, ${mix(f.top, t.top)}px) scale(${mix(f.width, t.width) / flyer.offsetWidth})`;
  };
  const land = () => { flyer.remove(); el.style.visibility = ""; };
  place(0);
  const flight = animate(0, 1, { duration: 0.7, ease: EASE_IN_OUT, onUpdate: place, onComplete: land });
  return () => { flight.stop(); land(); };
}
export const still = () => window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;

/** Moves the orb to `want` once that slot is on the page (home until then) and flies it there from where it stood.
 *  Within a stop it glides too, when its slot moves to a new element (beside the agent's newest message). */
export function useOrbFlight(root: RefObject<HTMLElement | null>, want: Stop): Stop {
  const [at, setAt] = useState<Stop>("home");
  const from = useRef<{ rect: DOMRect | null; stop: Stop } | null>(null);
  const seen = useRef<DOMRect | null>(null); // where it last stood: a slot can vanish with the orb in it
  const stood = useRef<Element | null>(null); // the orb element that rect belongs to
  const gliding = useRef<(() => void) | null>(null);
  useLayoutEffect(() => {
    const orb = root.current?.querySelector<HTMLElement>(".cust-orb");
    const next = root.current?.querySelector(`[data-orb-slot="${want}"]`) ? want : "home";
    const was = seen.current, moved = !!orb && !!stood.current && orb !== stood.current && next === at && !from.current;
    if (orb) { seen.current = orb.getBoundingClientRect(); stood.current = orb; }
    if (next !== at) { from.current = { rect: seen.current, stop: next }; setAt(next); return; }
    if (moved && was?.width && !still()) { gliding.current?.(); gliding.current = flyTo(orb!, was); }
  });
  useLayoutEffect(() => () => gliding.current?.(), []);
  useLayoutEffect(() => {
    const pending = from.current;
    if (!pending || pending.stop !== at) return;
    const el = root.current?.querySelector<HTMLElement>(".cust-orb"), f = pending.rect;
    from.current = null;
    if (!el || !f?.width || still()) return;
    gliding.current?.();
    return flyTo(el, f);
  }, [at, root]);
  return at;
}
