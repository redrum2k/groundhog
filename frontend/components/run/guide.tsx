"use client";
import { animate } from "motion/react";
import { createContext, useContext, useLayoutEffect, useRef, useState, type ReactNode, type RefObject } from "react";
import type { OrbMode } from "../../lib/run/fold";
import Orb from "./orb";

// The customer view's orb walks the buyer through the order: it waits beside Acme's open decision,
// rides the magnifier over the delivered sheet while it checks, and sits beside the interview while
// it asks. Each place it can be is a slot; the orb lives in one slot at a time and flies between them.

export type Stop = "home" | "transcript" | "decision" | "sheet";
const MODE: Record<Stop, OrbMode> = { home: "float", transcript: "look", decision: "wait", sheet: "inspect" };
const EASE_IN_OUT = [0.77, 0, 0.175, 1] as const; // --ease-in-out, the canvas orb's travel curve

const Guide = createContext<{ at: Stop; mood: Partial<Record<Stop, OrbMode>> } | null>(null); // mood: a stop's mode when the view knows better
export const GuideProvider = Guide.Provider;

/** Where the orb can stand. Outside the customer view (no provider) it renders `fallback` instead. */
export function OrbSlot({ name, fallback }: { name: Stop; fallback?: ReactNode }) {
  const guide = useContext(Guide);
  if (!guide) return <>{fallback}</>;
  return (
    <span className={`orb-slot slot-${name}`} data-orb-slot={name}>
      {guide.at === name ? <span className="cust-orb"><Orb mode={guide.mood[name] ?? MODE[name]} /></span> : fallback}
    </span>
  );
}

/** Moves the orb to `want` once that slot is on the page (home until then) and flies it there from where it stood. */
export function useOrbFlight(root: RefObject<HTMLElement | null>, want: Stop): Stop {
  const [at, setAt] = useState<Stop>("home");
  const from = useRef<DOMRect | null>(null);
  const seen = useRef<DOMRect | null>(null); // where it last stood: a slot can vanish with the orb in it (the lens, once checking ends)
  useLayoutEffect(() => {
    const orb = root.current?.querySelector(".cust-orb");
    if (orb) seen.current = orb.getBoundingClientRect();
    const next = root.current?.querySelector(`[data-orb-slot="${want}"]`) ? want : "home";
    if (next === at) return;
    from.current = seen.current;
    setAt(next);
  });
  useLayoutEffect(() => {
    const el = root.current?.querySelector<HTMLElement>(".cust-orb"), f = from.current;
    from.current = null;
    if (!el || !f?.width || window.matchMedia?.("(prefers-reduced-motion: reduce)").matches) return;
    // A copy flies above the page and re-aims at the slot every frame: the sticky header, a clipping
    // transcript box, a smooth scroll or the sweeping lens can't strand it. The real orb shows on landing.
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
  }, [at, root]);
  return at;
}
