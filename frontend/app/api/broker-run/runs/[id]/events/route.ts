import { NextResponse } from "next/server";
import { eventsAfter } from "../../../../../../lib/run/broker/store";

export async function GET(request: Request, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const after = Number(new URL(request.url).searchParams.get("after") ?? 0);
  const result = await eventsAfter(id, Number.isFinite(after) ? after : 0);
  if ("status" in result) return NextResponse.json({ detail: result.error }, { status: result.status });
  return NextResponse.json(result, { headers: { "Cache-Control": "no-store" } });
}
