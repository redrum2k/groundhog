import { NextResponse } from "next/server";
import type { Binding, ControllerAction } from "../../../../../../lib/run/contract";
import { decide } from "../../../../../../lib/run/stub-store";

const ACTIONS = new Set<ControllerAction>(["approve", "reject", "ask", "escalate"]);

export async function POST(request: Request, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const body = (await request.json().catch(() => ({}))) as { action?: unknown; binding?: Partial<Binding> };
  const { action, binding } = body;
  if (typeof action !== "string" || !ACTIONS.has(action as ControllerAction)) return NextResponse.json({ detail: "unknown action" }, { status: 422 });
  if (typeof binding?.deliveryVersion !== "number" || typeof binding?.evidenceVersion !== "number") return NextResponse.json({ detail: "binding required" }, { status: 422 });
  const result = decide(id, action as ControllerAction, { deliveryVersion: binding.deliveryVersion, evidenceVersion: binding.evidenceVersion });
  if (!result.ok) return NextResponse.json({ detail: result.detail }, { status: result.status });
  return NextResponse.json({ ok: true });
}
