"use client";
import type { OrbMode } from "../../lib/run/fold";
import { IcLens, IcScroll } from "./icons";

// The agent's mascot: a flat blue groundhog (round ears, a big nose on its snout) dressed as a detective in a
// deerstalker and round glasses. Its mode is a state indicator (like a spinner): float along, carry a sheet back,
// look around while clarifying, sweep a magnifier while investigating, blink slowly while waiting
// on Maya, squint happily when the money lands.
export default function Orb({ mode }: { mode: OrbMode }) {
  return (
    <span className={`orb orb-${mode}`} aria-hidden>
      {mode === "carry" && <span className="orb-sheet"><IcScroll size={10} strokeWidth={1.8} /></span>}
      {mode === "inspect" && <span className="orb-lens"><IcLens size={17} strokeWidth={1.9} /></span>}
      <svg viewBox="0 0 28 28" width="34" height="34">
        <g className="orb-ears">
          <circle cx="5.5" cy="3.7" r="2.4" /><circle cx="5.5" cy="3.7" r="1.2" className="orb-ear-in" />
          <circle cx="22.5" cy="3.7" r="2.4" /><circle cx="22.5" cy="3.7" r="1.2" className="orb-ear-in" />
        </g>
        <circle cx="14" cy="14" r="13" className="orb-body" />
        <g className="orb-face">
          <ellipse cx="14" cy="20.2" rx="4.9" ry="4.1" className="orb-snout" />
          <path className="orb-mouth" d="M14 20.15v1.35M12.5 21.2q.75.85 1.5.35q.75.5 1.5-.35" />
          <ellipse cx="14" cy="18.9" rx="2.3" ry="1.45" className="orb-nose" />
          <circle cx="13.08" cy="18.39" r="0.42" className="orb-glint" />
          <g className="orb-eyes">
            <rect x="8.6" y="10" width="3.2" height="6.4" rx="1.6" />
            <rect x="16.2" y="10" width="3.2" height="6.4" rx="1.6" />
          </g>
          <path className="orb-specs" d="M5.85 13.2a3.85 3.85 0 1 0 7.7 0a3.85 3.85 0 1 0-7.7 0ZM14.45 13.2a3.85 3.85 0 1 0 7.7 0a3.85 3.85 0 1 0-7.7 0ZM5.85 12.4H4M22.15 12.4H24" />
        </g>
        <g transform="rotate(-6 14 6)">
          <path className="orb-hat" d="M4.6 6.4C4.2-4 23.8-4 23.4 6.4C18.6 7.6 9.4 7.6 4.6 6.4Z" />
          <path className="orb-hat-band" d="M4.75 4.9C9.4 6 18.6 6 23.25 4.9L23.4 6.4C18.6 7.6 9.4 7.6 4.6 6.4ZM5.2 5.6C3.4 5.9 1.6 6.9.6 8.4C2.8 8.4 4.6 8 6.2 7.2ZM22.8 5.6C24.6 5.9 26.4 6.9 27.4 8.4C25.2 8.4 23.4 8 21.8 7.2Z" />
          <path className="orb-hat-seam" d="M14-.9V5.6M9.4.6Q8.4 3 8.7 5.4M18.6.6Q19.6 3 19.3 5.4" />
        </g>
      </svg>
    </span>
  );
}
