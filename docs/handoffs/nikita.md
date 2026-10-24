# Nikita — runtime and payments

Own the full payment boundary: shared DTOs, configuration/signers, pinned ABI, buyer signature
verification, dedicated operator execution, nonce/outbox durability, receipt/event/state
reconciliation, API/persistence/jobs, exact settlement gates and deployment integration. Keep
agent gateway/harness/permissions/observability ownership. No wallet task belongs to Jeff.

Phase 1 gives Lucas the frozen API contract, generated TypeScript, mock/fake responses and all
payment states. New schema-4 accepted terms preserve historical mock snapshots/responses.
Acceptance, authorization, submission and funding remain distinct. Current mock terminal
operations complete atomically; live asynchronous execution is the next independent slice.

Build the reusable Base adapter and thin terminal laboratory from [runbook](../PAYMENT_RUNBOOK.md).
Use explicit synthetic accepted terms and a fixture settlement decision, not an AI verdict.
Prove preflight → prepare/sign → funded → restart → capture, and separately fund → void, with
100000 atomic test USDC each only after separately authorized execution. This needs neither
Jeff's new prompts nor Lucas's UI. Integrate the same adapter with the offline catalog journey.

Keep current verification/evidence/consent/dispute/review/amount/expiry gates. Recheck before
submission; invalidate stale unsubmitted captures. Submitted captures cannot be cancelled by
new evidence. Parent replacement void must confirm before child funding/work. Ambiguity must
not become success or a fresh-nonce retry. No partial capture, fees or refunds in this MVP.

Done for the live milestone means matching payment-specific events/state, restart recovery,
unique terminal effects and redacted reports, not an interface stub. No real testnet result is
claimed now; see PAYMENT_SPIKE.md for remaining checks and source provenance.
