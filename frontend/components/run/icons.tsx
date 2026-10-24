// Hand-drawn icon set for the run. One system: 16×16 grid, 1.4 stroke, round caps and joins,
// no fills except small dots.
import type { SVGProps } from "react";

export type IconProps = { size?: number; strokeWidth?: number } & Omit<SVGProps<SVGSVGElement>, "strokeWidth">;
const base = (size = 16, sw = 1.4) => ({
  width: size, height: size, viewBox: "0 0 16 16", fill: "none", stroke: "currentColor",
  strokeWidth: sw, strokeLinecap: "round" as const, strokeLinejoin: "round" as const, "aria-hidden": true,
});
const icon = (d: string) => ({ size, strokeWidth, ...p }: IconProps) => <svg {...base(size, strokeWidth)} {...p}><path d={d} /></svg>;

/** Tick */
export const IcCheck = icon("m3.25 8.5 3 3 6.5-7");
/** Close */
export const IcX = icon("M3.5 3.5l9 9M12.5 3.5l-9 9");
/** Chevron down */
export const IcChevron = icon("m3.5 6 4.5 4.5L12.5 6");
/** Chevron right */
export const IcChevronRight = icon("m6 3.5 4.5 4.5L6 12.5");
/** Locked money: a padlock */
export const IcLock = icon("M4.5 7h7a1.25 1.25 0 0 1 1.25 1.25v4.5A1.25 1.25 0 0 1 11.5 14h-7a1.25 1.25 0 0 1-1.25-1.25v-4.5A1.25 1.25 0 0 1 4.5 7ZM5.5 7V5a2.5 2.5 0 0 1 5 0v2");
/** A sheet the orb carries */
export const IcScroll = icon("M4 1.75h5.25L12.5 5v8.25a1 1 0 0 1-1 1h-7.5a1 1 0 0 1-1-1V2.75a1 1 0 0 1 1-1ZM9 1.75V5.25h3.5M5.5 8h5M5.5 10.25h5");
/** A list, for the checklist header */
export const IcList = icon("M2.25 4h1.5M6 4h7.75M2.25 8h1.5M6 8h7.75M2.25 12h1.5M6 12h7.75");
/** Replay: an arrow curling back */
export const IcReplay = icon("M2.75 8a5.25 5.25 0 1 0 1.55-3.72M2.75 2.5v2.75H5.5");
/** Play */
export const IcPlay = ({ size, strokeWidth, ...p }: IconProps) => <svg {...base(size, strokeWidth)} {...p}><path d="M4.5 2.75v10.5L13 8Z" /></svg>;
/** Pause */
export const IcPause = icon("M5 3v10M11 3v10");
/** The workspace mark: four tiles */
export const IcLogo = ({ size = 14 }: { size?: number }) => (
  <svg viewBox="0 0 16 16" width={size} height={size} aria-hidden>
    <rect x="2" y="2" width="5" height="5" rx="1" fill="currentColor" /><rect x="9" y="2" width="5" height="5" rx="1" fill="currentColor" opacity=".45" />
    <rect x="2" y="9" width="5" height="5" rx="1" fill="currentColor" opacity=".45" /><rect x="9" y="9" width="5" height="5" rx="1" fill="currentColor" />
  </svg>
);
