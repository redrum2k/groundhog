"use client";
import type { OrbMode } from "../../lib/run/fold";
import { IcScroll } from "./icons";

// The agent's mascot: a flat blue orb with two eyes. Its mode is a state indicator (like a
// spinner): float along, carry a sheet back, look around while investigating, blink slowly
// while waiting on Maya, squint happily when the money lands.
export default function Orb({ mode }: { mode: OrbMode }) {
  return (
    <span className={`orb orb-${mode}`} aria-hidden>
      {mode === "carry" && <span className="orb-sheet"><IcScroll size={10} strokeWidth={1.8} /></span>}
      <svg viewBox="0 0 28 28" width="34" height="34">
        <circle cx="14" cy="14" r="13" className="orb-body" />
        <g className="orb-eyes">
          <rect x="8.6" y="10" width="3.2" height="6.4" rx="1.6" />
          <rect x="16.2" y="10" width="3.2" height="6.4" rx="1.6" />
        </g>
      </svg>
    </span>
  );
}
