import { NextResponse } from "next/server";
import type { BuyerMove } from "../../../../../../lib/run/broker/driver";
import { buyerMove } from "../../../../../../lib/run/broker/store";

// Summit's move, made by the presenter from the customer view. The driver is waiting for it;
// anything else gets a 409 that says what the order is waiting for.
export async function POST(request: Request, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const body = (await request.json().catch(() => ({}))) as { action?: unknown; text?: unknown };
  let move: BuyerMove;
  if (body.action === "approve" || body.action === "accept") move = { action: body.action };
  else if (body.action === "object" && typeof body.text === "string" && body.text.trim()) move = { action: "object", text: body.text.trim().slice(0, 600) };
  else return NextResponse.json({ detail: "action must be approve, accept, or object with text" }, { status: 422 });
  const result = buyerMove(id, move);
  if (result.status !== 200) return NextResponse.json({ detail: result.detail }, { status: result.status });
  return NextResponse.json({ ok: true });
}
