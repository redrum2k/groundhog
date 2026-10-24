// Server-side client for Jeff's broker API. Tokens come from the local demo session route and
// never reach the browser: the Next route handlers in app/api/broker-run call this.
import type { BrokerEvent, BrokerOrder, DataRow } from "./types";

export const BACKEND = (process.env.BACKEND_URL ?? "http://127.0.0.1:8000").replace(/\/$/, "");
export type Role = "customer" | "provider" | "investigator" | "controller";

export class BrokerError extends Error {
  constructor(public readonly status: number, public readonly detail: string) { super(detail); }
}

async function call<T>(path: string, token?: string, body?: unknown, method = body === undefined ? "GET" : "POST"): Promise<T> {
  const res = await fetch(`${BACKEND}${path}`, {
    method, cache: "no-store",
    headers: { ...(body !== undefined ? { "Content-Type": "application/json" } : {}), ...(token ? { Authorization: `Bearer ${token}` } : {}) },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!res.ok) {
    const detail = await res.json().then((j: { detail?: unknown }) => (typeof j.detail === "string" ? j.detail : JSON.stringify(j.detail))).catch(() => res.statusText);
    throw new BrokerError(res.status, detail);
  }
  return (await res.json()) as T;
}

export const session = (actor: Role) => call<{ token: string }>("/api/jobflow/sessions", undefined, { actor_id: actor }).then((s) => s.token);
export const createDraft = (token: string, body: Record<string, unknown>) => call<BrokerOrder & { questions: { id: string; field: string; answer_id: string | null }[]; unresolved_fields: string[]; acceptance_digest: string | null; order_id: string | null }>("/api/broker/drafts", token, body);
export const draftCommand = (token: string, id: string, body: Record<string, unknown>) => call<ReturnType<typeof createDraft> extends Promise<infer T> ? T : never>(`/api/broker/drafts/${id}/commands`, token, body);
export const uploadSource = (token: string, scope: "drafts" | "orders", id: string, body: Record<string, unknown>) => call<BrokerOrder>(`/api/broker/${scope}/${id}/sources`, token, body);
export const getOrder = (token: string, id: string) => call<BrokerOrder>(`/api/broker/orders/${id}`, token);
/** Before acceptance the entity is a draft; it carries the same messages and questions. */
export const getDraft = (token: string, id: string) => call<BrokerOrder>(`/api/broker/drafts/${id}`, token);
export const orderCommand = (token: string, id: string, body: Record<string, unknown>) => call<BrokerOrder>(`/api/broker/orders/${id}/commands`, token, body);
export const events = (token: string, id: string, after = 0) => call<BrokerEvent[]>(`/api/broker/entities/${id}/events?after=${after}`, token);

/** The delivered market-data rows, found by trying the delivery artifacts until one has rows. */
export async function deliveredRows(token: string, id: string, artifactIds: string[]): Promise<DataRow[]> {
  for (const a of artifactIds) {
    const res = await fetch(`${BACKEND}/api/broker/entities/${id}/artifacts/${a}`, { headers: { Authorization: `Bearer ${token}` }, cache: "no-store" });
    if (!res.ok) continue;
    const text = await res.text();
    if (!text.startsWith("{")) continue;
    try { const j = JSON.parse(text) as { rows?: DataRow[] }; if (Array.isArray(j.rows)) return j.rows; } catch { /* a PDF or sidecar */ }
  }
  return [];
}
