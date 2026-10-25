// Hand-drawn icon set for the run. One system: 16×16 grid, 1.4 stroke, round caps and joins,
// no fills except small dots.
import type { SVGProps } from "react";

export type IconProps = { size?: number; strokeWidth?: number } & Omit<SVGProps<SVGSVGElement>, "strokeWidth">;
const base = (size = 16, sw = 1.4) => ({
  width: size, height: size, viewBox: "0 0 16 16", fill: "none", stroke: "currentColor",
  strokeWidth: sw, strokeLinecap: "round" as const, strokeLinejoin: "round" as const, "aria-hidden": true,
});
const icon = (d: string) => ({ size, strokeWidth, ...p }: IconProps) => <svg {...base(size, strokeWidth)} {...p}><path d={d} /></svg>;

/** The customer's mark: a summit line */
export const IcSummit = icon("M1.5 12.5 6 5l3 4.5 2-3 3.5 6");

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
/** A magnifier, held while the agent inspects evidence */
export const IcLens = ({ size, strokeWidth, ...p }: IconProps) => <svg {...base(size, strokeWidth)} {...p}><circle cx="7" cy="7" r="4.5" /><path d="m10.25 10.25 3.25 3.25" /></svg>;
/** A list, for the checklist header */
export const IcList = icon("M2.25 4h1.5M6 4h7.75M2.25 8h1.5M6 8h7.75M2.25 12h1.5M6 12h7.75");
/** Replay: an arrow curling back */
export const IcReplay = icon("M2.75 8a5.25 5.25 0 1 0 1.55-3.72M2.75 2.5v2.75H5.5");
/** Play */
export const IcPlay = ({ size, strokeWidth, ...p }: IconProps) => <svg {...base(size, strokeWidth)} {...p}><path d="M4.5 2.75v10.5L13 8Z" /></svg>;
/** Pause */
export const IcPause = icon("M5 3v10M11 3v10");
/** A wallet: the customer's money, flat like the rest of the set */
export const IcWallet = icon("M2.25 4.5A1.25 1.25 0 0 1 3.5 3.25h8.25a1 1 0 0 1 1 1v1M2.25 4.5v7.25a1.25 1.25 0 0 0 1.25 1.25h9.25a1 1 0 0 0 1-1V6.25a1 1 0 0 0-1-1H3.5a1.25 1.25 0 0 1-1.25-.75ZM10 9.5h.01");
/** A small gold coin for the money pill */
export const IcCoin = ({ size = 12 }: { size?: number }) => (
  <svg viewBox="0 0 16 16" width={size} height={size} aria-hidden>
    <circle cx="8" cy="8" r="7" fill="#f3c74b" stroke="#b8892a" strokeWidth="1.2" />
    <rect x="6.4" y="4" width="3.2" height="8" rx="1.6" fill="#b8892a" />
  </svg>
);
/** The Groundhog mark: the detective groundhog between two tiles. */
export const IcLogo = ({ size = 24, ...p }: { size?: number } & SVGProps<SVGSVGElement>) => (
  <svg viewBox="0 0 36 24" width={size * 1.5} height={size} aria-hidden {...p}>
    <path fill="#111111" d="M2.5 0H12.5A2.5 2.5 0 0 1 15 2.5V4.05A8.5 8.5 0 0 0 15 19.95V21.5A2.5 2.5 0 0 1 12.5 24H2.5A2.5 2.5 0 0 1 0 21.5V2.5A2.5 2.5 0 0 1 2.5 0Z" />
    <path fill="#c4c4c4" d="M23.5 0H33.5A2.5 2.5 0 0 1 36 2.5V21.5A2.5 2.5 0 0 1 33.5 24H23.5A2.5 2.5 0 0 1 21 21.5V19.95A8.5 8.5 0 0 0 21 4.05V2.5A2.5 2.5 0 0 1 23.5 0Z" />
    {/* the groundhog's face between the tiles */}
    <circle cx="12.9" cy="7.6" r="1.6" fill="#4a8af4" />
    <circle cx="23.1" cy="7.6" r="1.6" fill="#4a8af4" />
    <path fill="#4a8af4" d="M11.6 19V12.6C11.6 8.6 14.4 6 18 6S24.4 8.6 24.4 12.6V19Z" />
    <ellipse cx="18" cy="14.2" rx="3" ry="2.2" fill="#cfe0fd" />
    <ellipse cx="18" cy="13.1" rx="1" ry="0.75" fill="#14306e" />
    <circle cx="15.6" cy="11.2" r="0.85" fill="#0f1d3d" />
    <circle cx="20.4" cy="11.2" r="0.85" fill="#0f1d3d" />
    <path fill="#8c6239" d="M13 8.2C12.9 3.8 23.1 3.8 23 8.2C20.2 8.9 15.8 8.9 13 8.2Z" />
  </svg>
);
