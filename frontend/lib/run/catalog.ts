import type { CatalogEvent, CatalogEvents, Money, OrderCommand, OrderView } from "../run.generated";
import type { CNode, CanvasView } from "../../components/run/canvas";

export const CATALOG_API = "/api/catalog";
export const catalogNodes: CNode[] = [
  { id: "clarify", row: 0, col: 0, title: "Accept the specification", desc: "Explicit customer agreement" },
  { id: "paid", row: 0, col: 1, title: "Fund the order", desc: "Signature, submission, confirmation" },
  { id: "produce", row: 0, col: 2, title: "Produce & verify", desc: "Actual PDF and source checks" },
  { id: "review", row: 0, col: 3, title: "Review delivery", desc: "Accepted policy and server clock" },
  { id: "captured", row: 0, col: 4, title: "Settle", desc: "Independent payment authority" },
  { id: "evidence", row: 1, col: 0, title: "Acquire evidence", desc: "Source-bound repair request", lane: "amber" },
  { id: "human", row: 1, col: 1, title: "Owned human review", desc: "Missing facts and required authority", lane: "amber" },
  { id: "improve", row: 1, col: 2, title: "Improve future work", desc: "Model proposal, probe, approval", lane: "amber" },
];

export function exactMoney(money: Money) {
  const raw = BigInt(money.amount_minor).toString().padStart(money.decimals + 1, "0");
  return `${money.currency} ${money.decimals ? `${raw.slice(0, -money.decimals)}.${raw.slice(-money.decimals)}` : raw}`;
}

export function mergeCatalogEvents(previous: CatalogEvent[], fresh: CatalogEvent[]) {
  const bySeq = new Map(previous.map(e => [e.seq, e]));
  for (const event of fresh) {
    if (previous.length && event.run_id !== previous[0].run_id) throw new Error("Event belongs to another order");
    const prior = bySeq.get(event.seq);
    if (prior && prior.event_id !== event.event_id) throw new Error("Conflicting event cursor");
    bySeq.set(event.seq, event);
  }
  return [...bySeq.values()].sort((a, b) => a.seq - b.seq);
}

export function catalogCanvas(event?: CatalogEvent): CanvasView {
  const status: CanvasView["status"] = Object.fromEntries(catalogNodes.map(n => [n.id, "idle"]));
  const chip: CanvasView["chip"] = {};
  if (!event) return { status, chip, orb: { node: "clarify", mode: "look" }, coin: null, loops: [], cards: [] };
  const o = event.order, payment = event.payment?.payment, delivery = o.deliveries?.at(-1);
  status.clarify = "done"; chip.clarify = `Accepted · ${o.snapshot.quote.policy?.version ?? "pinned policy"}`;
  const funded = !!o.authorization.receipt;
  status.paid = funded ? "done" : "waiting";
  chip.paid = payment?.state ?? o.authorization.status;
  const runnableWork = o.jobs?.some(j => j.status === "queued" || j.status === "running");
  status.produce = o.delivery_state === "operational_failure" ? "fail" : delivery ? "done" : o.order_state === "processing" && runnableWork ? "running" : ["waiting_evidence", "human_review", "pending_approval"].includes(o.order_state ?? "") ? "waiting" : "idle";
  chip.produce = o.verification ? o.verification.passed ? "PASS" : o.verification.assessments.some(a => a.result === "FAIL") ? "FAIL" : "UNKNOWN / CONFLICT" : "Not verified";
  if (!o.verification && o.jobs?.some(j => j.kind === "correct" && (j.status === "queued" || j.status === "running")) && o.verification_history?.some(v => v.provider_defect)) {
    status.produce = "fail"; chip.produce = "Prior output FAIL · correction pending";
  }
  status.review = delivery ? o.customer_acceptance || payment?.state === "captured" ? "done" : "waiting" : "idle";
  chip.review = delivery ? `Delivery ${delivery.version}` : "No delivery";
  const terminal = payment?.state === "captured" || payment?.state === "voided";
  status.captured = terminal ? "done" : payment?.state === "failed" ? "fail" : funded ? "waiting" : "idle";
  chip.captured = payment?.state ?? "Not settled";
  status.evidence = o.order_state === "waiting_evidence" ? "waiting" : o.amendments?.some(a => a.applied_revision != null) ? "done" : "idle";
  status.human = o.order_state === "human_review" || o.order_state === "pending_approval" ? "waiting" : "idle";
  chip.human = o.order_state === "pending_approval" ? "Consent required" : "Held";
  chip.improve = event.procedure_version ?? "catalog-static-v1";
  const focus = terminal ? "captured" : status.human === "waiting" ? "human" : status.evidence === "waiting" ? "evidence" : delivery ? "review" : funded ? "produce" : "paid";
  return {
    status, chip, orb: { node: focus, mode: terminal ? "happy" : focus === "produce" ? "carry" : "wait" },
    coin: { text: `${exactMoney(o.snapshot.quote.amount)} · ${payment?.state ?? o.authorization.status}${event.payment?.simulated ? " · mock" : ""}`, locked: !terminal, done: terminal },
    loops: [],
    cards: (o.verification?.assessments ?? []).filter(a => a.result !== "PASS").slice(0, 3).map(a => ({ id: a.obligation_id, node: "evidence", text: `${a.result}: ${a.reason_code}`, tone: "ev" })),
  };
}

export function orderBinding(view: OrderView, key: string): OrderCommand {
  return { expected_revision: view.order.revision ?? 1, expected_binding: view.order.binding, idempotency_key: key };
}

export class CatalogError extends Error {
  constructor(public status: number, message: string) { super(message); }
}
export async function catalogRequest<T>(path: string, body?: unknown): Promise<T> {
  const response = await fetch(`${CATALOG_API}/${path}`, body === undefined ? { cache: "no-store" } : {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new CatalogError(response.status, error.detail ?? `Catalog request failed (${response.status})`);
  }
  return response.json() as Promise<T>;
}
export const pollCatalog = (id: string, cursor: number) => catalogRequest<CatalogEvents>(`runs/${encodeURIComponent(id)}/events?after=${cursor}`);
