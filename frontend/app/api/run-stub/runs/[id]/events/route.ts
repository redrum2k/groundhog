import { NextResponse } from "next/server";
import { eventsAfter } from "../../../../../../lib/run/stub-store";

export async function GET(request: Request, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const after = Number(new URL(request.url).searchParams.get("after") ?? 0);
  const events = eventsAfter(id, Number.isFinite(after) ? after : 0);
  if (!events) return NextResponse.json({ detail: "Run not found" }, { status: 404 });
  return NextResponse.json({ events, poll_after_ms: 1000 }, { headers: { "Cache-Control": "no-store" } });
}
