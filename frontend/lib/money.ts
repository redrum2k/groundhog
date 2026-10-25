/** Presentation only. Signing and settlement always use the original integer quantities. */
export function formatMinor(minor: number, decimals = 2): string {
  if (!Number.isSafeInteger(minor) || !Number.isInteger(decimals) || decimals < 0 || decimals > 18)
    throw new Error("Money requires safe integer minor units and an explicit scale");
  const sign = minor < 0 ? "-" : "";
  const digits = BigInt(Math.abs(minor)).toString().padStart(decimals + 1, "0");
  return sign + (decimals ? `${digits.slice(0, -decimals)}.${digits.slice(-decimals)}` : digits);
}

/** The historical canvas wire format carries display dollars, never spending authority. */
export function formatMajor(major: number): string {
  return formatMinor(Math.round(major * 100));
}

/** Keep legacy whole-dollar canvas labels, but never drop a fractional trailing cent. */
export function formatCanvasMajor(major: number): string {
  return formatMajor(major).replace(/\.00$/, "");
}
