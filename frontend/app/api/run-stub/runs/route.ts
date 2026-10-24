import { NextResponse } from "next/server";
import { createRun } from "../../../../lib/run/stub-store";
import type { Ending } from "../../../../lib/run/scenario";

const ENDINGS = new Set<Ending>(["disagree", "agree", "controller"]);

// Stand-in for the backend: starts a live amber run. Replace the base URL in lib/run/source.ts
// with Nikita's endpoint when it lands; the canvas does not change.
export async function POST(request: Request) {
  const body = (await request.json().catch(() => ({}))) as { ending?: unknown };
  const ending = body.ending;
  if (typeof ending !== "string" || !ENDINGS.has(ending as Ending)) return NextResponse.json({ detail: "unknown ending" }, { status: 422 });
  const run = createRun(ending as Ending);
  return NextResponse.json({ id: run.id, poll_after_ms: 1000 });
}
