import { NextResponse } from "next/server";
import type { ControllerAction } from "../../../../../../lib/run/contract";
import { decide } from "../../../../../../lib/run/broker/store";

const ACTIONS = new Set<ControllerAction>(["approve", "reject", "ask", "escalate"]);
const NOTE: Record<ControllerAction, string> = {
  approve: "Resume: the evidence supports counting it.", reject: "Hold: the evidence does not settle it.",
  ask: "Ask the buyer for more.", escalate: "Send up.",
};

// The controller's click. It runs here, server side, with the controller session; the backend
// answers 409 when the task's binding has moved on.
export async function POST(request: Request, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const body = (await request.json().catch(() => ({}))) as { action?: unknown };
  if (typeof body.action !== "string" || !ACTIONS.has(body.action as ControllerAction)) return NextResponse.json({ detail: "unknown action" }, { status: 422 });
  const action = body.action as ControllerAction;
  const result = await decide(id, action, NOTE[action]);
  if (result.status !== 200) return NextResponse.json({ detail: result.detail }, { status: result.status });
  return NextResponse.json({ ok: true });
}
