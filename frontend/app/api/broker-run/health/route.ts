import { NextResponse } from "next/server";
import { BACKEND } from "../../../../lib/run/broker/client";

// Is the broker backend there? The run screen defaults to Live when it is.
export async function GET() {
  try {
    const res = await fetch(`${BACKEND}/health`, { cache: "no-store", signal: AbortSignal.timeout(1500) });
    return res.ok ? NextResponse.json({ ok: true }) : NextResponse.json({ ok: false }, { status: 503 });
  } catch {
    return NextResponse.json({ ok: false }, { status: 503 });
  }
}
