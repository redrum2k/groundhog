import { NextResponse } from "next/server";
import type { Case } from "../../../../lib/run/scenario";
import { startRun } from "../../../../lib/run/broker/store";

const CASES = new Set<Case>(["shared", "red", "green", "amber"]);

// Starts a live order on the broker backend with scripted parties. The session tokens stay in
// this process; the browser only ever sees the translated event stream.
export async function POST(request: Request) {
  const body = (await request.json().catch(() => ({}))) as { case?: unknown };
  if (typeof body.case !== "string" || !CASES.has(body.case as Case)) return NextResponse.json({ detail: "unknown case" }, { status: 422 });
  try {
    return NextResponse.json(await startRun(body.case as Case));
  } catch (err) {
    return NextResponse.json({ detail: `Could not reach the backend: ${err instanceof Error ? err.message : String(err)}` }, { status: 502 });
  }
}
