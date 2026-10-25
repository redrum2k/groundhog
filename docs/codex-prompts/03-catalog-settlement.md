# Conversation 3 — asynchronous catalog settlement integration

Complete the connection between catalog policy and durable asynchronous payment
execution. Implement and test it with injected fake transport independently of the
live Base adapter. Reuse the existing journal/executor; do not start a second ledger.

First inspect git status and branch/commit. Read AGENTS.md, applicable nested
instructions, HACK.md, CONTEXT.md, docs/PAYMENT_SPIKE.md, docs/PAYMENT_RUNBOOK.md,
docs/handoffs/nikita.md and docs/handoffs/lucas.md. Inspect orders/catalog.py,
runtime/catalog_policy.py, payments/catalog.py, payments/executor.py,
payments/journal.py, payment DTOs and their tests.

Work only in this worktree. If detached or on the selected base, create
`codex/catalog-settlement`; otherwise continue on that branch. Do not reset an
existing branch or edit another checkout. You are not alone in the repository:
preserve teammates' changes and coordinate through the existing interfaces.

## Ownership and shared boundaries

Own backend/app/orders/catalog.py, backend/app/payments/catalog.py,
backend/app/runtime/catalog_policy.py, necessary generic executor/journal fixes,
dedicated catalog/payment settlement tests and docs/workstreams/03-settlement.md.
Keep persistence additive. Prefer existing repository operations; record any shared
storage/API extension needed for integration instead of broadly refactoring them.

Conversation 1 owns main.py, catalog dispatch modules and gateway transport;
conversation 2 owns Base transport/configuration/protocol/runner; conversation 4 owns
adapter selection, final startup/API wiring and shared documentation. Do not edit
their files, public DTOs, generated artifacts, frontend or Jeff's semantics here.
Preserve the existing invoice /api/jobflow subsystem and historical records.

Keep PaymentTransport, SignedTransaction and ChainObservation stable. Add optional
payment_mode="mock", payment_config=None and payment_transport=None injection to
CatalogService without breaking current constructors. Retain the existing bounded
payments.work(limit=20) entry point. The live implementation will be
BasePaymentTransport(config, *, rpc=None) with verified_usdc_domain() -> dict;
code against injection and fake equivalents now, without importing a nonexistent
module. Conversation 4 will wire real configuration and transport.

## Implement

1. Separate accepted quote, signing preparation, authorization, submission and
   confirmed funding. Preserve exact accepted parties, amount, source/binding,
   payment hash, salt and deadlines. For Base mode, construct terms from explicitly
   injected configuration and prepare/signature-check against the verified token
   domain. Never use the mock domain or demo addresses as live fallbacks.
2. Keep existing mock behavior and exact historical command responses compatible.
   For asynchronous execution reserve operations atomically, then process using
   PaymentExecutor and its guard/changed/complete hooks. Do not close orders, create
   confirmed bookings or dispatch fulfillment merely on signature/submission.
3. Recheck current evidence/delivery binding, mandatory verification, authority,
   consent, disputes, review/acceptance, authorization expiry, exact amount and
   terminal exclusivity before capture submission. Invalidate stale unsubmitted
   intents without losing legitimate future settlement eligibility. Once submitted,
   reconcile that exact operation; late disputes go to human review and do not
   pretend to cancel a transaction already past the submission boundary.
4. Atomically apply confirmed payment evidence and catalog funding/booking changes.
   Prevent duplicate funding effects, deliveries and terminal bookings on retries
   or restart. Keep uncertain/reorg observations truthful; never quietly rewrite
   a recorded financial history or infer returned funds from expiry.
5. A substantive replacement waits for confirmed parent void before child funding
   and work. Failed/uncertain parent return keeps the child blocked. Ordinary
   additional work retains its separate accepted price/order/authorization.
6. Keep payment/order/delivery/case state and server available_actions consistent.
   Preserve existing endpoints, request/response shapes, 409 stale/idempotency
   behavior, redacted validation errors and the catalog review policy in HACK.md.
   Public contract changes require a concrete proposal for conversation 4 rather
   than an independent schema fork. A passing agent report is not payment permission.

## Acceptance evidence

Use synthetic accepted terms, fake transport and injected clocks. Test:
- Signature/submission do not start work; confirmed funding makes only one job eligible.
- Pending capture/void do not produce terminal bookings; confirmed evidence books once.
- Changed evidence/dispute before submission invalidates capture; a late dispute
  after submission leaves chain reconciliation intact and routes the case safely.
- Restart, exact replay, competing capture/void, expired authorization, missing or
  mismatched events/state, uncertain transactions and reorgs fail closed.
- Replacement children wait through pending/failed/uncertain parent void and unblock
  only after confirmed return; historical mock snapshots/responses remain unchanged.

Run uv sync --locked --project backend, relevant catalog/API/payment/legacy tests
and Ruff lint/format checks. Reuse existing tests; add cross-component cases that
exercise real persistence. Do not weaken policy to make fixtures pass. No paid model
calls, broadcasts or deployment; no existing .env/private databases or frontend work.

Self-review, commit only your changes locally and write
docs/workstreams/03-settlement.md with configuration/injection interfaces, transaction
boundaries, tests actually run, demonstrated state transitions and precise integration
requests. Return branch/final SHA and outstanding limits. Do not push or merge main.
