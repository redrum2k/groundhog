import type { OrderView } from "../catalog.generated";
import type { CanvasBinding, FundingPreparation, Quote, RunPage } from "../runs.generated";
import { jsonRequest } from "./live";
import { signFunding, type BuyerWallet } from "./wallet";

export type CheckoutStage = "Accepting agreement…" | "Preparing payment…" | "Confirm in MetaMask" | "Submitting payment…";

export async function checkout({runId, quote, binding, wallet, signal, progress}: {
  runId: string;
  quote: Quote;
  binding?: CanvasBinding | null;
  wallet?: BuyerWallet;
  signal: AbortSignal;
  progress: (stage: CheckoutStage) => void;
}) {
  const terms = quote.payment_terms;
  if (!terms) throw new Error("Request a current quote before paying.");
  const simulate = terms.mode === "mock";
  if (!simulate && !wallet) throw new Error("Connect your Buyer account in Wallet settings before paying.");
  // Stable keys let a lost response replay the same operation, including after reload.
  const send = async <T,>(path: string, body: Record<string, unknown>, key: string) => {
    signal.throwIfAborted();
    const result = await jsonRequest<T>(path, {...body, idempotency_key: key}, key, signal);
    signal.throwIfAborted();
    return result;
  };
  let orderId = binding?.orderId;
  let revision = binding?.revision;
  let expected = binding ? {snapshot_id: binding.snapshotId, delivery_version: binding.deliveryVersion, evidence_revision: binding.evidenceVersion} : undefined;
  if (!binding) {
    progress("Accepting agreement…");
    const accepted = await send<OrderView>("/quote-acceptance", {quote_id: quote.quote_id, customer_actor: "Summit Fitness"}, `checkout:accept:${quote.quote_id}`);
    if (!accepted.available_actions.includes("prepare_funding")) throw new Error("Agreement accepted. Funding is not available yet; check the current payment status.");
    orderId = accepted.order.snapshot.order_id;
    revision = accepted.order.revision ?? 1;
    expected = accepted.order.binding;
  }
  if (!orderId || revision == null || !expected?.snapshot_id) throw new Error("The accepted agreement is unavailable. Refresh before paying.");
  // Acceptance/preparation replays can contain old state. Inspect current authority
  // before asking for another signature after an uncertain response or reload.
  const latest = await jsonRequest<RunPage>(`/runs/${encodeURIComponent(runId)}/events?after=0&limit=100`, undefined, undefined, signal);
  signal.throwIfAborted();
  if (latest.binding?.orderId !== orderId || latest.quote?.quote_id !== quote.quote_id) throw new Error("The agreement changed. Refresh before paying.");
  if (latest.payment && latest.payment.payment.state !== "awaiting_signature") return;
  if (!latest.caught_up || !latest.available_actions.some(action => action.action === "prepare_funding" && action.enabled)) throw new Error("Agreement accepted. Funding is not available yet; check the current payment status.");
  if (latest.binding.revision !== revision) throw new Error("The order changed. Review it before paying.");
  const command = {expected_revision: revision, expected_binding: expected};
  progress("Preparing payment…");
  const prepared = await send<FundingPreparation>(`/orders/${orderId}/funding-preparation`, command, `checkout:prepare:${orderId}:${revision}`);
  if (prepared.order_id !== orderId || prepared.terms.payment_hash !== terms.payment_hash || prepared.terms.mode !== terms.mode || prepared.terms.amount_atomic !== terms.amount_atomic) throw new Error("Payment terms changed. Review the agreement before paying.");
  let signature: string | undefined;
  if (!simulate) {
    signal.throwIfAborted();
    progress("Confirm in MetaMask");
    signature = await signFunding(wallet, prepared);
  }
  // A wallet popup cannot be cancelled by fetch's AbortSignal; recheck before submission.
  signal.throwIfAborted();
  progress("Submitting payment…");
  await send<OrderView>(`/orders/${orderId}/funding-authorizations`, {
    ...command,
    funding_attempt_id: prepared.funding_attempt_id,
    payment_hash: prepared.terms.payment_hash,
    simulate,
    ...(signature ? {signature} : {}),
  }, `checkout:fund:${prepared.funding_attempt_id}`);
}
