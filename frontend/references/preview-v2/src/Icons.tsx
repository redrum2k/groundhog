// Hand-drawn icon set for the agent's tools and pipeline steps.
// One system: 16×16 grid, 1.4 stroke, round caps and joins, no fills except small dots,
// drawn for this product's own objects (an order, a job log, an x402 payment, a GPU, a rate,
// an email, a ledger, a request, a reconciliation, a sign-off).
import type { SVGProps } from "react";

export type IconProps = { size?: number; strokeWidth?: number } & Omit<SVGProps<SVGSVGElement>, "strokeWidth">;
const base = (size = 16, sw = 1.4) => ({
  width: size, height: size, viewBox: "0 0 16 16", fill: "none", stroke: "currentColor",
  strokeWidth: sw, strokeLinecap: "round" as const, strokeLinejoin: "round" as const, "aria-hidden": true,
});

/** Order / agreement: a sheet with a folded corner and three field rows */
export const IcOrder = ({ size, strokeWidth, ...p }: IconProps) => (
  <svg {...base(size, strokeWidth)} {...p}>
    <path d="M4 1.75h5.25L12.5 5v8.25a1 1 0 0 1-1 1h-7.5a1 1 0 0 1-1-1V2.75a1 1 0 0 1 1-1Z" />
    <path d="M9 1.75V5.25h3.5" />
    <path d="M5.5 8h5M5.5 10.25h5M5.5 12.5h3" />
  </svg>
);

/** Job log: a prompt and output lines */
export const IcLog = ({ size, strokeWidth, ...p }: IconProps) => (
  <svg {...base(size, strokeWidth)} {...p}>
    <rect x="1.75" y="2.25" width="12.5" height="11.5" rx="1.25" />
    <path d="M4.25 6 6 7.5 4.25 9" />
    <path d="M7.75 9h4" />
    <path d="M4.25 11.25h7.5" opacity=".55" />
  </svg>
);

/** x402 payment: a coin with a transfer arrow through it */
export const IcPay = ({ size, strokeWidth, ...p }: IconProps) => (
  <svg {...base(size, strokeWidth)} {...p}>
    <circle cx="8" cy="8" r="6.25" />
    <path d="M5 8h6" />
    <path d="M9 6l2 2-2 2" />
  </svg>
);

/** GPU: a die with pins on every side */
export const IcGpu = ({ size, strokeWidth, ...p }: IconProps) => (
  <svg {...base(size, strokeWidth)} {...p}>
    <rect x="3.75" y="3.75" width="8.5" height="8.5" rx="1" />
    <rect x="6.25" y="6.25" width="3.5" height="3.5" rx=".5" />
    <path d="M6 1.5v2.25M10 1.5v2.25M6 12.25v2.25M10 12.25v2.25M1.5 6h2.25M1.5 10h2.25M12.25 6h2.25M12.25 10h2.25" />
  </svg>
);

/** Rate card: a price tag */
export const IcRate = ({ size, strokeWidth, ...p }: IconProps) => (
  <svg {...base(size, strokeWidth)} {...p}>
    <path d="M8.6 1.75h4.65a1 1 0 0 1 1 1V7.4a1 1 0 0 1-.3.7l-6.2 6.2a1 1 0 0 1-1.4 0L2 9.95a1 1 0 0 1 0-1.4L8.2 2.05a1 1 0 0 1 .4-.3Z" />
    <circle cx="11" cy="5" r="1" fill="currentColor" stroke="none" />
  </svg>
);

/** Email: an envelope */
export const IcMail = ({ size, strokeWidth, ...p }: IconProps) => (
  <svg {...base(size, strokeWidth)} {...p}>
    <rect x="1.75" y="3.25" width="12.5" height="9.5" rx="1.25" />
    <path d="m2.25 4 5.1 4.1a1 1 0 0 0 1.3 0L13.75 4" />
  </svg>
);

/** Ledger: a book with debit and credit columns */
export const IcLedger = ({ size, strokeWidth, ...p }: IconProps) => (
  <svg {...base(size, strokeWidth)} {...p}>
    <path d="M3 2.75a1 1 0 0 1 1-1h8.25v12.5H4a1 1 0 0 1-1-1Z" />
    <path d="M7.6 1.75v12.5" />
    <path d="M4.75 5h1.25M4.75 7.5h1.25M9.25 5h1.5M9.25 7.5h1.5M9.25 10h1.5" />
  </svg>
);

/** Customer request: an inbox tray with an incoming item */
export const IcRequest = ({ size, strokeWidth, ...p }: IconProps) => (
  <svg {...base(size, strokeWidth)} {...p}>
    <path d="M1.75 9.25 3.4 3.5a1 1 0 0 1 .96-.75h7.28a1 1 0 0 1 .96.75l1.65 5.75v3a1 1 0 0 1-1 1H2.75a1 1 0 0 1-1-1Z" />
    <path d="M1.75 9.25H5l1 1.75h4l1-1.75h3.25" />
  </svg>
);

/** Reconcile: three records lined up and ticked */
export const IcReconcile = ({ size, strokeWidth, ...p }: IconProps) => (
  <svg {...base(size, strokeWidth)} {...p}>
    <path d="M2 3.5h7M2 8h7M2 12.5h7" />
    <path d="m11 3.6.9.9 1.85-1.85M11 8.1l.9.9 1.85-1.85M11 12.6l.9.9 1.85-1.85" />
  </svg>
);

/** Sign-off: a shield with a person-mark tick */
export const IcSignoff = ({ size, strokeWidth, ...p }: IconProps) => (
  <svg {...base(size, strokeWidth)} {...p}>
    <path d="M8 1.75 13 3.6v4.15c0 3-2.15 5.35-5 6.5-2.85-1.15-5-3.5-5-6.5V3.6Z" />
    <path d="m5.75 8 1.6 1.6L10.5 6.5" />
  </svg>
);

/** Fallback tool */
export const IcTool = ({ size, strokeWidth, ...p }: IconProps) => (
  <svg {...base(size, strokeWidth)} {...p}>
    <path d="M10.25 2.1a3.25 3.25 0 0 0-3.9 4.3L2.2 10.55a1.2 1.2 0 0 0 1.7 1.7l4.15-4.15a3.25 3.25 0 0 0 4.3-3.9l-2 2-1.7-.4-.4-1.7Z" />
  </svg>
);
