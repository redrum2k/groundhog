# Conversation 4 — integrate and validate the backend handoff

Integrate the completed runtime, Base transport and catalog settlement branches.
Own final wiring, cross-component correctness and the updated backend/frontend
handoff. Implement remaining integration fixes and validate the actual combined
application; do not stop at a merge or a summary of other agents' reports.

First inspect git status, current branch/commit and git worktree list. Read AGENTS.md,
applicable nested instructions, HACK.md, CONTEXT.md, docs/PAYMENT_SPIKE.md,
docs/PAYMENT_RUNBOOK.md, docs/INTEGRATION_CHECKPOINT.md, docs/responsibilities.md,
docs/handoffs/nikita.md and docs/handoffs/lucas.md. Work only in your assigned
integration worktree. Create codex/backend-integration if detached/on the selected
base; otherwise continue there. Never reset or overwrite another worktree.

The expected completed local branches are:
- codex/catalog-runtime
- codex/base-transport
- codex/catalog-settlement

Use the exact final SHAs from their completion summaries. Inspect branch history
and commit contents to confirm ownership/completion, then merge the completed SHAs
into this integration branch, preserving history. If a summary is absent, inspect
the branch's docs/workstreams handoff and confirm that its work is committed; do
not guess a moving branch tip is complete. Ask only for genuinely missing branch
identity/completion information, and continue independent inspection meanwhile.
Do not cherry-pick duplicate commits already merged. Resolve conflicts by preserving
the behavior of both subsystems, not by blindly choosing one side.

You are not alone in this repository. Jeff and Lucas retain their implementation
ownership; preserve their work. Conversations 1–3 remain available for substantial
module-specific fixes. You own small integration corrections, shared wiring, API
compatibility checks, documentation and tests, not a new rewrite of their modules.

## Connect the implementation

1. Read docs/workstreams/01-runtime.md, 02-base.md and 03-settlement.md after merging.
   Reconcile exact interfaces and any reported gaps. Runtime owns
   CatalogWorker(service).run_once(); Base owns BasePaymentTransport implementing
   PaymentTransport plus verified_usdc_domain(); settlement owns CatalogService
   payment injection and bounded payments.work. Verify those interfaces from code.
2. Wire configuration/adapter selection in payments/__init__.py and main.py without
   changing invoice payment behavior. Mock remains the default. Base initialization
   and capabilities must distinguish implemented, configured, unavailable and enabled;
   a missing signer or failed preflight never falls back to fabricated mock success.
   No import/schema export may initiate RPC, load private .env files or broadcast.
3. Connect dispatch, deadline sweeps and payment processing with bounded concurrency
   and safe restart/shutdown. Slow model/PDF/RPC work must not starve review deadlines.
   Verify funding -> work and confirmed settlement -> bookings end to end.
4. Preserve the frozen root catalog API and the separate /api/jobflow API. Validate
   exact endpoint paths, request/response/error schemas, available_actions, current
   bindings, buyer signing/preparation/submission and polling state. Coordinate any
   unavoidable compatible extension across OpenAPI, generated TypeScript, fixtures
   and handoff examples; explain the reason. Do not change public shapes casually.
5. Supply a concrete backend integration recipe for Lucas: what runs automatically,
   which privileged operations still need a trusted server-side caller, credential
   roles, request examples and recovery behavior. Use existing protected endpoints;
   do not create an unauthenticated credential-forwarding proxy. Lucas owns his
   frontend/server bridge. Customer auth and public deployment are a separate scope.

## Validate the combined result

Use temporary databases, synthetic PDFs, injected model results/RPC and clocks:
- Request -> clarification -> quote -> acceptance -> explicit simulated funding ->
  automatic work -> evidence repair -> verified PDF -> review/acceptance -> one mock booking.
- An unresolved dispute/evidence case reaches human review without capture.
- Fake asynchronous funding/capture and independent funding/void, including restart,
  stale evidence, late disputes, uncertainty/reorg holds and replacement ordering.
- Auth boundaries, exact idempotent replay, stale 409s, signature redaction, actionable
  errors, all payment-state fixtures and both catalog/invoice API compatibility.

Run the full backend suite and Ruff checks from AGENTS.md. Exercise the repaired and
unresolved offline journeys in README.md. Check the actual runtime OpenAPI against
the export and generate/check catalog TypeScript with the repository's documented
tools. Note frontend/scripts/generate-contracts.mjs covers invoice jobflow types;
it is not the catalog OpenAPI generator. Run the existing frontend generation check,
typecheck, tests and build as compatibility checks without implementing UI. Respect
frontend/package.json's Node requirement; document environment failures separately
from code failures. Do not conceal failures by skipping existing assertions.

## Deliver

Update docs/IMPLEMENTATION_STATUS.md, relevant handoffs, PAYMENT_RUNBOOK/SPIKE and
README examples to match demonstrated behavior. Distinguish mock, fake-chain,
implemented-but-not-live-verified and observed live states. Keep historical policy
and immutable responses unchanged. Do not claim testnet receipts from offline tests.
No paid calls, transaction broadcasts, deployment or existing secrets/private DB use.

Self-review the combined diff and fix integration defects. Commit only task changes
on codex/backend-integration; leave main untouched and do not push or merge the PR
unless separately requested. Write docs/workstreams/04-integration.md with merged
SHAs, exact validation/results, final runtime/payment interfaces, remaining live
preflight/demo steps and any actual blocker. Return the final SHA, a PR-ready
description, Lucas's concise handoff link and an honest completion assessment.
