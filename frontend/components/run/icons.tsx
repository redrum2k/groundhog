// Hand-drawn icon set for the run. One system: 16×16 grid, 1.4 stroke, round caps and joins,
// no fills except small dots, drawn for this product's own objects.
import type { SVGProps } from "react";

export type IconProps = { size?: number; strokeWidth?: number } & Omit<SVGProps<SVGSVGElement>, "strokeWidth">;
const base = (size = 16, sw = 1.4) => ({
  width: size, height: size, viewBox: "0 0 16 16", fill: "none", stroke: "currentColor",
  strokeWidth: sw, strokeLinecap: "round" as const, strokeLinejoin: "round" as const, "aria-hidden": true,
});
const icon = (d: string) => ({ size, strokeWidth, ...p }: IconProps) => <svg {...base(size, strokeWidth)} {...p}><path d={d} /></svg>;

/** Customer request: an inbox tray with an incoming item */
export const IcRequest = icon("M1.75 9.25 3.4 3.5a1 1 0 0 1 .96-.75h7.28a1 1 0 0 1 .96.75l1.65 5.75v3a1 1 0 0 1-1 1H2.75a1 1 0 0 1-1-1ZM1.75 9.25H5l1 1.75h4l1-1.75h3.25");
/** Interview: two overlapping speech bubbles */
export const IcChat = icon("M2.75 2.75h6.5a1 1 0 0 1 1 1v4a1 1 0 0 1-1 1H5.25l-2.5 2v-2a1 1 0 0 1-1-1v-4a1 1 0 0 1 1-1ZM10.25 6.25h3a1 1 0 0 1 1 1v4a1 1 0 0 1-1 1v2l-2.5-2h-3a1 1 0 0 1-1-1v-2.5");
/** Data contract: a sheet with a folded corner and three lines */
export const IcContract = icon("M4 1.75h5.25L12.5 5v8.25a1 1 0 0 1-1 1h-7.5a1 1 0 0 1-1-1V2.75a1 1 0 0 1 1-1ZM9 1.75V5.25h3.5M5.5 8h5M5.5 10.25h5M5.5 12.5h3");
/** Dataset: a table with a header row and a key column */
export const IcSheet = icon("M3 2.25h10a1.25 1.25 0 0 1 1.25 1.25v9A1.25 1.25 0 0 1 13 13.75H3a1.25 1.25 0 0 1-1.25-1.25v-9A1.25 1.25 0 0 1 3 2.25ZM1.75 5.75h12.5M1.75 9.75h12.5M6 5.75v8");
/** Check: contract lines, each ticked */
export const IcChecklist = icon("M2 3.5h7M2 8h7M2 12.5h7m2-8.9.9.9 1.85-1.85M11 8.1l.9.9 1.85-1.85M11 12.6l.9.9 1.85-1.85");
/** Delivery: a sealed package */
export const IcDeliver = icon("M2.25 4.75 8 1.75l5.75 3v6.5L8 14.25l-5.75-3ZM2.25 4.75 8 7.75l5.75-3M8 7.75v6.5");
/** Review window: a clock */
export const IcClock = icon("M8 1.75a6.25 6.25 0 1 1 0 12.5 6.25 6.25 0 0 1 0-12.5ZM8 4.75V8l2.25 1.5");
/** Dispute: a speech bubble with an exclamation mark */
export const IcDispute = icon("M3 2.25h10a1.25 1.25 0 0 1 1.25 1.25V10A1.25 1.25 0 0 1 13 11.25H7l-3.25 2.5v-2.5H3A1.25 1.25 0 0 1 1.75 10V3.5A1.25 1.25 0 0 1 3 2.25ZM8 4.75V7.5M8 9.4v.1");
/** Verdict: a balance scale */
export const IcScale = icon("M8 2.25v11.5M4.75 13.75h6.5M3 4.25h10M3 4.25 1.25 8.25a1.9 1.9 0 0 0 3.5 0ZM13 4.25l-1.75 4a1.9 1.9 0 0 0 3.5 0Z");
/** Investigate: a magnifier */
export const IcSearch = icon("M7 2.5a4.5 4.5 0 1 1 0 9 4.5 4.5 0 0 1 0-9Zm3.4 7.9 3.35 3.35");
/** Amendment: a price tag */
export const IcPrice = icon("M8.6 1.75h4.65a1 1 0 0 1 1 1V7.4a1 1 0 0 1-.3.7l-6.2 6.2a1 1 0 0 1-1.4 0L2 9.95a1 1 0 0 1 0-1.4L8.2 2.05a1 1 0 0 1 .4-.3ZM11 4.9v.2");
/** Sign-off: a shield with a tick */
export const IcSignoff = icon("M8 1.75 13 3.6v4.15c0 3-2.15 5.35-5 6.5-2.85-1.15-5-3.5-5-6.5V3.6Zm-2.25 6.25 1.6 1.6L10.5 6.5");
/** Learned: a bookmark with a tick */
export const IcLearned = icon("M4 1.75h8a1 1 0 0 1 1 1v11.5L8 11l-5 3.25V2.75a1 1 0 0 1 1-1Zm1.75 4.5 1.6 1.6 3-3");
/** Ledger: a book with debit and credit columns */
export const IcLedger = icon("M3 2.75a1 1 0 0 1 1-1h8.25v12.5H4a1 1 0 0 1-1-1ZM7.6 1.75v12.5M4.75 5h1.25M4.75 7.5h1.25M9.25 5h1.5M9.25 7.5h1.5M9.25 10h1.5");
/** Locked money: a padlock */
export const IcLock = icon("M4.5 7h7a1.25 1.25 0 0 1 1.25 1.25v4.5A1.25 1.25 0 0 1 11.5 14h-7a1.25 1.25 0 0 1-1.25-1.25v-4.5A1.25 1.25 0 0 1 4.5 7ZM5.5 7V5a2.5 2.5 0 0 1 5 0v2");
/** Tick */
export const IcCheck = icon("m3.25 8.5 3 3 6.5-7");
/** Play */
export const IcPlay = ({ size, strokeWidth, ...p }: IconProps) => <svg {...base(size, strokeWidth)} {...p}><path d="M4.5 2.75v10.5L13 8Z" fill="currentColor" /></svg>;
/** Chevron down */
export const IcChevron = icon("m3.5 6 4.5 4.5L12.5 6");
/** Arrow to a source */
export const IcGoto = icon("M2.5 8h10M9 4.5 12.5 8 9 11.5");
/** A list, for the checklist header */
export const IcList = icon("M2.25 4h1.5M6 4h7.75M2.25 8h1.5M6 8h7.75M2.25 12h1.5M6 12h7.75");
