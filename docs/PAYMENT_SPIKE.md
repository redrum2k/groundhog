# Payment spike — unrun

Owner: Nikita. No actual CDP/Base experiment or settlement evidence exists yet.
The v0.2 workflow is mock-only. Follow HACK.md for the current accepted product policy.

## Questions to resolve

1. Which network, asset, contract and spender authorization represent the accepted
   base price and optional additional-processing fee? How is authorization opened at
   order acceptance and tied to the frozen snapshot?
2. Can the base payment be captured after a ten-minute review cutoff or an early
   evidence-backed agent verdict? What exact chain/provider evidence confirms it?
3. How do unresolved disputes hold capture at cutoff and transition to human review?
   A dispute after an already completed early capture needs a separate remedy; do not
   pretend that a captured payment is still held.
4. How are expiry/renewal handled independently from review deadlines, including during
   questions, free regeneration and human review?
5. How is the additional processing fee bounded by the accepted policy? If no fee was
   agreed, how does a separately accepted quote obtain the required payment authority?
6. How do durable operation IDs, idempotency keys, nonces and authoritative reconciliation
   handle lost responses, submitted/uncertain operations, restarts and reorgs?
7. What are release/refund semantics, who can authorize them after human review, and
   which fees exist? Do not equate a refund request with permission to release funds.

## Execution and evidence

Keep experiments under spikes/payments. This task authorizes no paid API calls,
transaction broadcasts or infrastructure deployments. Keep secrets in ignored local
configuration, never checked-in examples or frontend variables.

Before enabling a live adapter, record network/asset/contract/version, authorization
model, method semantics, exact commands, redacted receipts, costs, failure/expiry
cases, reconciliation and finality rules. Label simulation versus actual observations.
A transaction submission is not confirmed settlement. Reconcile uncertainty before
retrying. Current result: **not attempted**; only mock mode is enabled.
