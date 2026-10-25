# Conversation 2 — reusable Base transport and payment laboratory

Implement the reusable Base Sepolia transport and thin terminal payment laboratory
for Nikita's payment milestone. Complete offline implementation and validation now;
live execution remains separately authorized. Do not stop at interface stubs.

First inspect git status and branch/commit. Read AGENTS.md and applicable nested
instructions, HACK.md, CONTEXT.md, docs/PAYMENT_SPIKE.md, docs/PAYMENT_RUNBOOK.md,
docs/handoffs/nikita.md, backend/app/payments/abi/README.md and the pinned ABI/source.
Inspect existing protocol helpers, configuration, journal, executor and fake tests
before writing replacements. Prefer official pinned protocol sources when verifying
technical behavior; do not silently migrate the selected protocol/deployment.

Work only in this assigned worktree. If detached or on the selected base, create
`codex/base-transport`; otherwise continue on that branch. Do not reset an existing
branch or change another worktree. You are not alone in the codebase: preserve
others' changes and adapt to the agreed interfaces.

## Ownership and interfaces

Own backend/app/payments/base.py and transport-specific helper modules,
payments/base_config.py, necessary pinned ABI/protocol corrections with evidence,
spikes/payments/, dedicated transport/CLI tests and docs/workstreams/02-base.md.
Use installed dependencies first. If a dependency is genuinely required, own the
minimal backend/pyproject.toml and backend/uv.lock change and document why.

Conversation 3 owns payments/executor.py, payments/journal.py, payments/catalog.py
and catalog order/settlement transitions. Treat the existing PaymentTransport,
SignedTransaction and ChainObservation interfaces as the shared boundary. Record
needed changes for that owner; do not independently fork its journal/executor.
Conversation 1 owns runtime startup. Conversation 4 owns final adapter selection,
application wiring, shared docs and public-contract verification. Do not modify
main.py, payments/__init__.py, public DTOs/endpoints or frontend files here.

Provide BasePaymentTransport(config, *, rpc=None) in app/payments/base.py, implementing
the existing PaymentTransport protocol. Allow injected RPC for offline tests. Also
expose verified_usdc_domain() -> dict, which verifies the actual configured token's
EIP-712 domain against its RPC-observed domain separator and fails closed. This is
the domain provider consumed by catalog funding preparation; it must never return
the mock domain for a live payment. Any extra APIs should be documented in your handoff.

## Implement

1. Read-only preflight: chain ID, configured addresses, deployed code/compatibility,
   collector-to-escrow relationship, token decimals/domain, parties and required
   balances. Missing configuration must produce useful redacted errors. Importing
   modules must not load credentials, contact RPC or start workers.
2. Exact transaction construction/signing for the pinned Commerce Payments version,
   using the accepted immutable PaymentInfo and existing hash/nonce helpers. Funding
   uses buyer ERC-3009 authorization; full capture uses the exact amount and zero fee;
   full void/reclaim follow the pinned protocol. Buyer signing in the CLI is isolated
   from server/operator signing. No server-generated buyer signature for catalog users.
3. Implement pending_nonce, prepare_transaction, broadcast and reconcile as expected
   by PaymentExecutor. The executor/journal own durable bytes/hash, leases and nonce
   reservations; transport must not hide retries, invent new nonces, or book money.
   Validate payment-specific events/state and canonical block evidence. Inconclusive,
   conflicting or orphaned evidence must remain pending/uncertain/held as appropriate.
4. Build spikes/payments/run.py as a thin reusable-adapter client with preflight,
   prepare, fund, status, capture, void, reconcile and reclaim. Each takes a durable
   --payment-id. Defaults are inspection/dry-run; no signing/broadcast side effects
   on help/status/dry-run. Submission requires explicit --broadcast-testnet plus
   ENABLE_TESTNET_BROADCAST=true. Persist/reuse original fixture terms and never
   regenerate a payment/salt after timeout or restart. Use distinct synthetic
   100000-atomic test-USDC cases; they are not USD 15 catalog order payments.
5. Supply offline RPC doubles and runnable local examples with useful exit statuses
   and redacted output. Document recovery precisely: a missing receipt is not failure.
   Either support explicit identical-byte recovery safely through the durable executor
   boundary or leave ambiguity unresolved; do not add automatic fresh-transaction retry.

## Acceptance evidence

Prove encodings/signatures against the pinned ABI and deterministic vectors, domain
mismatch rejection, wrong chain/configuration rejection, no default broadcast,
exact funding/capture/void reconciliation, failed/pending/uncertain/orphaned receipts,
restart/idempotency through the existing executor, and redaction. Exercise all CLI
commands offline, including help, missing configuration and dry-run paths. Preserve
existing protocol/payment tests; add meaningful transport tests, not only mocks
that repeat your implementation's assumptions.

Run uv sync --locked --project backend, focused payment/CLI tests and Ruff checks.
No live transaction, token purchase, deployment or paid model call is authorized.
Do not inspect existing .env files, use existing wallet credentials or contact live
RPC as part of tests. Use explicit synthetic test keys and injected RPC. Distinguish
offline implementation from observed live success in every report.

Self-review and commit only your changes locally. Write docs/workstreams/02-base.md
with interfaces, injection/setup, commands, tests actually run, recovery limits,
remaining live-proof steps and requests for conversation 3/4. Return branch and
final commit SHA. Do not push, merge main or claim a real testnet receipt exists.
