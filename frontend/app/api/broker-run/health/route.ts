import { NextResponse } from "next/server";
import { BACKEND } from "../../../../lib/run/broker/client";

// The retained demo requires local role identities, not only aggregate health.
// Probe read-only: never mint session credentials during health polling.
export async function GET() {
  try {
    const res = await fetch(`${BACKEND}/api/jobflow/actors`, { cache: "no-store", signal: AbortSignal.timeout(1500) });
    const actors: unknown = res.ok ? await res.json() : null;
    const ready = Array.isArray(actors) && ["customer", "provider", "investigator", "controller"].every(role => actors.some(actor => actor?.id === role && actor?.role === role));
    return ready ? NextResponse.json({ ok: true }) : NextResponse.json({ ok: false }, { status: 503 });
  } catch {
    return NextResponse.json({ ok: false }, { status: 503 });
  }
}
