/** Focused integration examples. api.generated.ts / backend OpenAPI define complete contracts. */
import type { components } from "./api.generated";

type Schema = components["schemas"];
export type Binding = Schema["Binding"];
export type OrderCommand = Schema["OrderCommand"];
export type Money = Schema["Money"];
export type Result = "PASS" | "FAIL" | "UNKNOWN" | "CONFLICT";
export type Citation = Schema["Span"];
export type ReviewRow = Schema["ReviewRow"];
export type TargetedComplaint = Schema["Complaint"];
export type EvidenceUpload = Schema["UploadCommand"];
export type OrderView = Schema["OrderView"];
export type Quote = Schema["Quote"];
export type PaymentInfo = Schema["PaymentInfo"];
export type PaymentTerms = Schema["PaymentTerms"];
export type PaymentAccount = Schema["PaymentAccount"];
export type PaymentOperation = Schema["PaymentOperation"];
export type PaymentView = Schema["PaymentView"];
export type FundingPreparation = Schema["FundingPreparation"];
export type FundingAuthorization = Schema["FundingAuthorization"];

export function currentCommand(
  order: { revision: number; binding: Binding },
  idempotencyKey: string,
): OrderCommand {
  return {
    expected_revision: order.revision,
    expected_binding: order.binding,
    idempotency_key: idempotencyKey,
  };
}

export class ApiError extends Error {
  constructor(public readonly status: number, public readonly detail: unknown) {
    super(status === 409 ? "State changed. Refetch before another action." : `API request failed: ${status}`);
  }
}

async function requestJson<T>(url: string, body?: unknown): Promise<T> {
  const response = await fetch(url, body === undefined ? { cache: "no-store" } : {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const payload: unknown = await response.json();
  if (!response.ok) throw new ApiError(response.status, payload);
  return payload as T;
}

// Show specification, limitations, manifest and complete frozen payment terms before this call.
export function acceptQuote(api: string, quoteId: string, actor: string, key: string): Promise<OrderView> {
  return requestJson(`${api}/quote-acceptance`, {
    quote_id: quoteId,
    customer_actor: actor,
    idempotency_key: key,
  });
}

export function getOrder(api: string, orderId: string): Promise<OrderView> {
  return requestJson(`${api}/orders/${encodeURIComponent(orderId)}`);
}

export function getPayment(api: string, orderId: string): Promise<PaymentView> {
  return requestJson(`${api}/orders/${encodeURIComponent(orderId)}/payment`);
}

export function prepareFunding(
  api: string,
  orderId: string,
  command: OrderCommand,
): Promise<FundingPreparation> {
  return requestJson(`${api}/orders/${encodeURIComponent(orderId)}/funding-preparation`, command);
}

// Wallet UI signs preparation.typed_data exactly, after checking payer and chain against terms.
// Rejecting the wallet prompt leaves the payment unfunded. Never log the signature or typed
// authorization payload to analytics. Do not send operator keys or privileged tokens here.
export function submitFundingAuthorization(
  api: string,
  orderId: string,
  command: OrderCommand,
  preparation: FundingPreparation,
  signature: string,
): Promise<OrderView> {
  const body: FundingAuthorization = {
    ...command,
    funding_attempt_id: preparation.funding_attempt_id,
    payment_hash: preparation.terms.payment_hash,
    signature,
  };
  return requestJson(`${api}/orders/${encodeURIComponent(orderId)}/funding-authorizations`, body);
}

// Explicit offline path only. This does not invent a buyer signature or authorize token movement.
export function simulateFunding(
  api: string,
  orderId: string,
  command: OrderCommand,
  preparation: FundingPreparation,
): Promise<OrderView> {
  const body: FundingAuthorization = {
    ...command,
    funding_attempt_id: preparation.funding_attempt_id,
    payment_hash: preparation.terms.payment_hash,
    simulate: true,
  };
  return requestJson(`${api}/orders/${encodeURIComponent(orderId)}/funding-authorizations`, body);
}

// Preserve exact key/payload for a lost-response retry. Refetch on 409 and before issuing a
// different action; exact idempotent replay can return an older saved view. Numeric blockchain
// quantities are decimal strings; never round them through JavaScript Number. A signature,
// submission or HTTP 200 is not proof of confirmed funding or completed settlement.
// Provider/reviewer/payment-worker routes require a trusted server-side bridge. No privileged
// credential belongs in this module, a browser bundle or any NEXT_PUBLIC variable.
