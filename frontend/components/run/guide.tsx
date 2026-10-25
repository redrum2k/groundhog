"use client";
import { createContext, useContext, useLayoutEffect, useRef, useState, type ReactNode, type RefObject } from "react";
import type { OrbMode } from "../../lib/run/fold";
import Orb, { TUNNEL } from "./orb";

// The customer view's orb walks the buyer through the order: it waits beside Summit's open decision,
// inspects an objected delivery with its magnifier, and sits beside the interview while it asks.
// Each place it can be is a slot; the orb lives in one slot at a time and tunnels between them.

export type Stop = "home" | "transcript" | "decision" | "inspect";
const MODE: Record<Stop, OrbMode> = { home: "float", transcript: "look", decision: "wait", inspect: "float" };

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

const SETTLE = 60; // ms between looks at where the new slot is, while the view may still be scrolling to it

/** The groundhog doesn't fly: a copy ducks into its burrow where it stood (`f`), scrolling away with the page if the
 *  view is moving, and the burrow closes; meanwhile the real one waits under at its new slot and climbs out of a
 *  burrow there, once the beat is over and the view has stopped scrolling. Returns how to cancel it. */
function tunnelTo(el: HTMLElement, f: DOMRect) {
  const ghost = el.cloneNode(true) as HTMLElement;
  ghost.classList.add("orb-flyer");
  // anchored in the scrolling pane, not the viewport, so a smooth scroll carries it off like everything else
  const pane = el.closest<HTMLElement>(".customer") ?? document.body;
  const r = pane.getBoundingClientRect(); // a DOMRect's fields are getters, so no spreading it
  const at = pane === document.body ? { left: -window.scrollX, top: -window.scrollY, scrollLeft: 0, scrollTop: 0 } : { left: r.left, top: r.top, scrollLeft: pane.scrollLeft, scrollTop: pane.scrollTop };
  ghost.style.transform = `translate(${f.left - at.left + at.scrollLeft}px, ${f.top - at.top + at.scrollTop}px)`;
  el.classList.add("tunnel-under");
  pane.append(ghost);
  ghost.getBoundingClientRect(); // laid out standing first, so the dive is a transition and not a jump
  ghost.classList.add("tunnel-down");
  let t = 0, last = NaN;
  const surface = () => { ghost.remove(); el.classList.remove("tunnel-under"); };
  const settled = () => { // climbs out only once its slot has stopped moving
    const top = el.getBoundingClientRect().top;
    if (top === last) surface();
    else { last = top; t = window.setTimeout(settled, SETTLE); }
  };
  t = window.setTimeout(settled, TUNNEL.dive + TUNNEL.under);
  return () => { window.clearTimeout(t); surface(); };
}
export const still = () => window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;

/** Moves the orb to `want` once that slot is on the page (home until then), tunnelling there from where it stood.
 *  Within a stop its slot can move to a new element (beside the agent's newest message); it just stands there. */
export function useOrbFlight(root: RefObject<HTMLElement | null>, want: Stop): Stop {
  const [at, setAt] = useState<Stop>("home");
  const from = useRef<{ rect: DOMRect | null; stop: Stop } | null>(null);
  const seen = useRef<DOMRect | null>(null); // where it last stood: a slot can vanish with the orb in it
  useLayoutEffect(() => {
    const orb = root.current?.querySelector<HTMLElement>(".cust-orb");
    const next = root.current?.querySelector(`[data-orb-slot="${want}"]`) ? want : "home";
    if (orb) seen.current = orb.getBoundingClientRect();
    if (next !== at) { from.current = { rect: seen.current, stop: next }; setAt(next); }
  });
  useLayoutEffect(() => {
    const pending = from.current;
    if (!pending || pending.stop !== at) return;
    const el = root.current?.querySelector<HTMLElement>(".cust-orb"), f = pending.rect;
    from.current = null;
    if (!el || !f?.width || still()) return;
    return tunnelTo(el, f);
  }, [at, root]);
  return at;
}
