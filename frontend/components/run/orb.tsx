"use client";
import { useId } from "react";
import type { OrbMode } from "../../lib/run/fold";
import { IcLens, IcScroll } from "./icons";

// The agent's mascot: a groundhog in a deerstalker and round glasses, sitting in its burrow at the
// step it's working on, always facing forward. Its mode is a state indicator (like a spinner):
// blink and sniff now and then while idle, carry a sheet back, look around while clarifying, sweep
// a magnifier while investigating, sniff and look around while waiting on a human, squint happily
// when the money lands. The class names stay the orb's so the canvas, guide and flyer styles still apply.
// While investigating, a badge over its hat says "?" as it searches and "!" once it has found evidence.
// Travel between places, in ms: it ducks all the way in and the burrow closes (dive), waits under until the run has
// been quiet that long (under: a burst of quick steps is one trip, it surfaces at the last one), then a burrow opens
// and it climbs out (rise). If a step starts while the burrow is only just opening, it shuts again (back). The burrow
// itself never moves. The CSS under .tunnel-* matches.
export const TUNNEL = { dive: 620, under: 1500, back: 200, rise: 900 } as const;

export default function Orb({ mode, found }: { mode: OrbMode; found?: boolean }) {
  const clip = `gh-clip-${useId().replace(/:/g, "")}`;
  return (
    <span className={`orb orb-${mode}`} aria-hidden>
      {mode === "inspect" && found !== undefined && <span key={found ? "found" : "searching"} className={`gh-badge${found ? " gh-found" : ""}`}>{found ? "!" : "?"}</span>}
      {mode === "carry" && <span className="orb-sheet"><IcScroll size={10} strokeWidth={1.8} /></span>}
      {mode === "inspect" && <span className="orb-lens"><IcLens size={17} strokeWidth={1.9} /></span>}
      <svg viewBox="0 0 28 28" width="34" height="34">
        <Burrow clip={clip} />
      </svg>
    </span>
  );
}

function Burrow({ clip }: { clip: string }) {
  return (
    <>
      <defs>
        {/* everything above the burrow's mouth, plus the mouth itself: below it the groundhog is underground */}
        <clipPath id={clip}>
          <rect x="-6" y="-14" width="40" height="38" />
          <ellipse cx="14" cy="24" rx="10.6" ry="2.4" />
        </clipPath>
      </defs>
      <ellipse className="gh-hole-rim" cx="14" cy="24" rx="12.6" ry="3.4" />
      <ellipse className="gh-hole" cx="14" cy="24" rx="10.6" ry="2.4" />
      <g clipPath={`url(#${clip})`}>
        <g className="gh-rise">
          <g className="gh-breathe">
          <g className="gh-tilt">
          <circle className="gh-fur" cx="7.2" cy="8.6" r="1.7" />
          <circle className="gh-fur" cx="20.8" cy="8.6" r="1.7" />
          <circle className="gh-ear" cx="7.2" cy="8.6" r="0.8" />
          <circle className="gh-ear" cx="20.8" cy="8.6" r="0.8" />
          <path className="gh-fur" d="M6.2 26V15.4C6.2 9.4 9.6 5.4 14 5.4S21.8 9.4 21.8 15.4V26Z" />
          <path className="gh-belly" d="M9.4 26V20.4C9.4 17.6 11.5 16 14 16S18.6 17.6 18.6 20.4V26Z" />
          <ellipse className="gh-muzzle" cx="14" cy="13.6" rx="3.4" ry="2.5" />
          <ellipse className="gh-nose" cx="14" cy="12.4" rx="1.15" ry="0.85" />
          <rect className="gh-tooth" x="13" y="14.5" width="0.95" height="1.6" rx="0.25" />
          <rect className="gh-tooth" x="14.05" y="14.5" width="0.95" height="1.6" rx="0.25" />
          <ellipse className="gh-paw" cx="11.4" cy="23.2" rx="1.5" ry="0.75" />
          <ellipse className="gh-paw" cx="16.6" cy="23.2" rx="1.5" ry="0.75" />
          <g className="orb-face">
            {/* the pupils glance inside the lenses; the glasses stay on the face */}
            <g className="gh-gaze">
              <g className="orb-eyes">
                <circle cx="11" cy="10.6" r="0.95" />
                <circle cx="17" cy="10.6" r="0.95" />
              </g>
            </g>
            <path className="orb-specs" d="M8.75 10.6a2.25 2.25 0 1 0 4.5 0a2.25 2.25 0 1 0-4.5 0ZM14.75 10.6a2.25 2.25 0 1 0 4.5 0a2.25 2.25 0 1 0-4.5 0ZM13.25 10.4h1.5" />
          </g>
          <g transform="translate(14 6.2) scale(0.56) translate(-14 -4.2) rotate(-6 14 6)">
            <path className="orb-hat" d="M4.6 6.4C4.2-4 23.8-4 23.4 6.4C18.6 7.6 9.4 7.6 4.6 6.4Z" />
            <path className="orb-hat-band" d="M4.75 4.9C9.4 6 18.6 6 23.25 4.9L23.4 6.4C18.6 7.6 9.4 7.6 4.6 6.4ZM5.2 5.6C3.4 5.9 1.6 6.9.6 8.4C2.8 8.4 4.6 8 6.2 7.2ZM22.8 5.6C24.6 5.9 26.4 6.9 27.4 8.4C25.2 8.4 23.4 8 21.8 7.2Z" />
            <path className="orb-hat-seam" d="M14-.9V5.6M9.4.6Q8.4 3 8.7 5.4M18.6.6Q19.6 3 19.3 5.4" />
          </g>
          </g>
          </g>
        </g>
      </g>
      {/* the burrow's front lip, drawn over the body so it reads as coming out of the hole */}
      <path className="gh-lip" d="M3.4 24A10.6 2.4 0 0 0 24.6 24" />
    </>
  );
}
