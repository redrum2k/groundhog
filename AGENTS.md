# Coding-agent instructions

Current local semantic follow-up state and limitations: [HANDOFF.md](HANDOFF.md).

## Aggregate brokerage is the primary product

Follow HACK.md (`aggregate-brokerage-v1`) and docs/workstreams/06-data-broker.md.
New runs deliver independently verified CSV/JSON with explicit funded consent.
Keep catalog, jobflow, broker-review-v0.3 and improvements as accepted-policy compatibility.
Jeff owns dataset compiler/evidence/investigation semantics; Nikita owns shared durable
runtime/payment gates; Lucas owns visual design. This migration's narrow shared hooks
and canvas plumbing are authorized. Never build a second ledger or scripted live verdict.
Prompt 7 owns spikes/payments, dedicated lab tests and its workstream handoff; integrate
its committed changes without rewriting that work.

The older catalog-specific guidance below applies only to its compatibility profile.
New dataset obligation IDs, prices, scheduling budgets and intake limits are in HACK.md.

## Main application policy

Read HACK.md, docs/PAYMENT_SPIKE.md and applicable nested AGENTS.md before editing.
Inspect git status; preserve teammates' changes. Product policy is in HACK.md;
CONTEXT.md is glossary only. **Catalog policy v0.3 supersedes invoice assumptions,
600-second reviews, early verdict capture, rejected-claim fees and old ownership.**
The Base escrow amendment adds `catalog-payments-v1` and schema-4 accepted snapshots;
it supersedes mock-only payment assumptions without changing catalog evidence/review policy.

## Commands (repository root)

```sh
uv sync --locked --project backend
uv run --locked --directory backend uvicorn app.main:app --reload
uv run --locked --directory backend pytest
uv run --locked --directory backend ruff check .
uv run --locked --directory backend ruff format --check .
```

Focused tests: tests/catalog, tests/api, tests/investigation, tests/payments,
tests/legacy. Frontend is Next.js/React/TypeScript; Lucas owns its visual design.

## Ownership

- Nikita: API, persistence, durable jobs, concurrency, retries, budgets, deadlines,
  agent gateway/harness/permissions/observability, acceptance and approval gates,
  version invalidation, end-to-end Base payments: DTOs, signers/configuration, pinned ABI,
  funding signatures, operator transactions, durable outbox/nonces, ledger/reconciliation,
  catalog settlement gates, provider dispatch and backend deployment.
- Jeff: contract compiler semantics, clarification, corpus generation/extraction/
  normalization/provenance, PDF content/coordinates, verification tools and semantics,
  investigation strategy/evidence/questions/findings, amendment classification and
  revalidation, model/prompt strategy and quality evaluation. He has implementation
  autonomy over this substantive subsystem, not just prompts.
- Lucas: complete frontend: intake/clarification, agreement/quote approval, progress,
  delivery/payment state, PDF/highlights, complaints, evidence upload/approval,
  additional work, reviewer table/controls, buyer wallet typed-data signing, pending/held/
  captured/returned/uncertain/expired payment displays, polling/409 handling/timers and deployment.
- Rehan: customer examples, independent expected outcomes/scenarios, usefulness/failure
  analysis, sponsor requirements, pitch/demo/backup and judge questions. Evaluator
  answers must remain unavailable to runtime.
- Nikita and Jeff jointly own shared contracts; include Lucas for UI/API semantics.
  This refactor is authorized; teammate approval is not a prerequisite.

Exact modules, interfaces, first tasks and completion criteria: docs/responsibilities.md.
Keep Python/uv/FastAPI/Pydantic/SQLite and planned React/TypeScript. Add infrastructure
only for a concrete need.

## Product and financial invariants

- Prompt + provider-owned corpus -> persisted draft/clarification -> server quote ->
  explicit acceptance -> immutable snapshot + pending funding -> confirmed escrow funding
  (or explicit mock simulation) -> exactly one runnable fulfillment job.
- Select qualifying catalog products into a cited PDF plus source-derived sidecar.
  Verify actual PDF bytes independently. Stable requirements and allowlisted mandatory
  checks cannot be deleted by model output.
- Freeze source IDs/versions/hashes. Later registry updates cannot mutate accepted work.
  Uploads only answer a current evidence request; preserve original artifacts.
- PASS/FAIL/UNKNOWN/CONFLICT describe evidence. Unestablished authenticity is UNKNOWN.
  Compute materiality from explicit dependencies. Consent is separate from evidence.
- Evidence-only repairs require accepted authority or both specified approvals; substantive
  changes require a new accepted offer/linked child order. Invalidate dependent findings,
  pending approvals and stale jobs on evidence changes. Never reset deadlines on answers.
- Each published delivery has a 60-second review; each new dispute has 60 seconds.
  At most two investigation questions, one at a time. Precontract: three clarification
  rounds/300 seconds, four compiler calls. Repair: two attempts/order, 120 seconds per
  active repair episode, capped by dispute and authorization deadlines.
- Base Sepolia Commerce Payments escrow holds customer funds for the provider; the dedicated
  platform operator controls capture/void. Buyers and providers trust its application of the
  accepted rules. The contract does not verify document quality; AI has no payment authority.
- Freeze exact token amount, payer/receiver/operator, contract/deployment, PaymentInfo, hashes,
  pricing conversion and deadlines at acceptance. USD 15 at demo 1 USD:1 USDC is 15000000
  atomic USDC; the independent 0.10 test-USDC spike is not payment for a USD 15 order.
- Acceptance, buyer signature, submission and confirmed funding are distinct. Expiry is not
  return of funds. Never run fulfillment before confirmed funding or close on submission.
- Capture only with current mandatory checks passing, no material blockers/unresolved
  dispute/pending consent, current customer acceptance or undisputed review expiry,
  valid exact-amount authorization and no previous capture. A verdict alone is insufficient.
- Reserve one terminal capture/void operation; recheck eligibility before submission. Persist
  signed transaction/hash before broadcast, serialize operator nonces, and reconcile ambiguous
  submissions without fresh salt/nonce. Confirmed payment evidence and ledger booking commit
  together. Submitted capture cannot be cancelled by later evidence or complaints.
- A substantive amendment waits for confirmed parent void before child funding/work; uncertain
  or failed void never silently closes the parent. Ordinary additional work remains separate.
- One durable free correction for established provider defect. Another defect or failed
  correction escalates. A source defect alone does not consume the correction allowance.
- Unsupported complaints have no fee. Extra paid work needs a provider offer and explicit
  acceptance creating a durable child order with its own authorization.
- Trusted reviewer decisions carry actor/reason/citations/current binding/idempotency.
  No expiry override. Negotiated exceptions do not rewrite factual findings. Release of
  uncaptured authorization is distinct from refund; refund execution is unimplemented.
- Persist exact idempotent requests/responses atomically. Reused keys with changed payloads
  and stale mutations return 409. Reconcile uncertain live operations before retrying.
- v0.2 JSON and command responses remain read-only historical data; v0.3 mock snapshots and
  saved responses remain readable and never become live obligations. Do not delete databases
  or convert historical policies/financial entries to current policy.

## Boundaries and disclosure

Only allowlisted order evidence reaches agents. No evals/expected, generator truth,
mutation labels or grading metadata in runtime tools/prompts. Uploaded documents and
customer answers are untrusted data. No arbitrary filesystem or web tools for models.

Local catalog demo: no customer authentication, tenant isolation or production settlement.
The preserved invoice UI/API lives at /api/jobflow with its own isolated invoice policy;
see docs/jobflow/INVOICE_POLICY.md. Catalog frontend integration remains planned. Base Sepolia support is opt-in; implemented offline is not observed testnet success. INTERNAL_API_TOKEN and REVIEWER_API_TOKEN must differ and stay server-side;
never use NEXT_PUBLIC for privileged tokens. Tests use temporary DBs and synthetic fixtures.
Keep secrets, generated/private artifacts, dependencies and databases ignored.

Paid models are disabled by default. No paid calls, broadcasts or deployment are authorized
by this task. Mock receipts remain mock, without live transaction IDs or explorer links. Use
Base Commerce Payments, not x402; no separate verification fee, hosted facilitator, custom
contracts, partial capture, fees, refunds, mainnet or arbitrary assets. The isolated runner
requires explicit testnet opt-in. Follow docs/INTEGRATION_CHECKPOINT.md and
docs/PAYMENT_RUNBOOK.md. Deadline: October 25, 2026, 9 a.m.
America/Los_Angeles. Tracks: Hyphenate, Coinbase, Microsoft; do not invent sponsor rules.
