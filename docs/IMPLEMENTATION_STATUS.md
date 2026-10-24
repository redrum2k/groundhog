# Implementation status — catalog v0.3 / payment Phase 1

Updated October 23, 2026. This supersedes invoice v0.2 behavior and ownership. The original catalog refactor began at 111 passing tests and reached a verified **130-test
baseline** before this payment amendment. The amendment preserves the actively modified
working tree; no teammate edits were reset.

## Implemented foundation

| Area | Delivered behavior |
| --- | --- |
| Precontract | Persisted requests, targeted clarification, deadlines/budgets, typed Terms, stable requirement IDs, readable summary and actual-source limitations. |
| Compiler/gateway | Injectable ContractCompiler and SemanticAssessor, offline substitutes, optional Claude Messages structured-output adapter, timeout/token/input limits, refusal/malformed-output handling and stale-result rejection. |
| Quote/acceptance | Server price rule, immutable revision/manifest/policy/expiry binding, schema-4 immutable payment terms, separate acceptance/funding and one runnable job only after funding, exact persisted retries and changed-payload rejection. |
| Sources | Provider-owned immutable registry versions/hashes/edition/authority records and content-addressed artifact storage. Four synthetic supplier PDFs, 48 products. |
| Documents | Real ReportLab PDFs; pdfplumber extraction, Decimal normalization/comparisons, source-derived structured sidecars, exact text spans and line highlights. |
| Verification | Allowlisted per-record and global checks, actual output PDF verification independent of its sidecar, PASS/FAIL/UNKNOWN/CONFLICT and dependency-based material blockers. |
| Evidence repair | Pre/post-delivery request-bound bounded PDF uploads, immutable amendments, identity/edition/consistency/authority checks, repair/substantive/unresolved classification, consent gates and invalidation. |
| Substantive change | Explicit provider offer + customer acceptance -> linked child order with new snapshot/manifest/authorization/job; parent-release dependency preserving history; current mock release is atomic. |
| Durable work | Persisted jobs/leases/attempts/errors, authorization gate before dispatch, expired lease recovery and stale result rejection. Model/document work outside long DB transactions. |
| Disputes/correction | Targeted product/field/requirement complaints, distinct scope change, two question rounds, no unsupported-complaint fee, one durable free correction and repeated-failure escalation. |
| Review/capture | 60-second delivery and dispute windows; unchanged deadlines on answers; current complete verification, clear authority/dispute gates, acceptance/cutoff, valid exact authorization and no prior capture required. |
| Human review | Relevant evidence table with source/delivery citations, remedy/financial/authority context; separate reviewer token; reason/evidence/binding/idempotency-backed decisions and negotiated-exception records. |
| Compatibility | Additive catalog/payment tables, schema-4 accepted terms, readable historical mock snapshots and exact historical order/idempotent response retention. No historical policy/ledger rewrite. |
| Integration | Updated root/nested instructions, ownership/API/architecture/payment guidance, exported OpenAPI, React/TypeScript contract examples, executable offline journeys. |

## Phase 1 payment/frontend contract handoff

Implemented offline: `catalog-payments-v1` DTOs, exact integer/decimal-string token amounts,
explicit USD:USDC conversion, frozen PaymentInfo/hash/nonce/parties/deadlines, schema-4 snapshots
with historical schema-3 mock compatibility, separate funding preparation/authorization/payment
views, EOA signature verification and explicit mock simulation, durable mock operations,
generated complete OpenAPI/TypeScript contracts and focused frontend helpers. The mock signing
domain cannot authorize live USDC. Validation errors redact input/signatures.

All 12 payment account states have Pydantic-validated runnable JSON fixtures. Exact protocol
hashes/nonces validate too. `tools/frontend_mock.py` serves the frozen payment endpoint without
external services. Main-app mock capture/release completes atomically; pending terminal/reorg
states are frontend fixtures for future asynchronous execution, not observed transactions.

Offline protocol helpers and minimal ABI/source provenance are pinned to Base Commerce Payments
v1.1.0 commit b748fdd7a830a655a19a530edcf2a94b9dc7d25f. They are not an RPC integration. Live
preflight, operator transaction signing/broadcast, authoritative chain reconciliation and the
standalone payment runner remain the next independent Nikita milestone. `/health` reports this
capability as planned. **No real testnet receipt exists.** See PAYMENT_RUNBOOK.md for current
commands and explicitly planned runner commands. Lucas can implement now from handoffs/lucas.md.

## Phase 1 validation and publication

- **180 tests pass**, including wallet typed-data/signature round trips, funding gates,
  durable replay, expiration, journal rollback, mock capture/void, all-state HTTP fixtures,
  historical read-only behavior and catalog regressions. Ruff lint and formatting pass.
- OpenAPI matches the runtime: **26 paths, 66 schemas**, API 0.4.0 / `catalog-api-v1`.
  Generated TypeScript passes its freshness check and strict TypeScript 5.9.3 compilation.
- The runnable localhost mock server returned valid responses for all 12 payment states;
  the temporary server was stopped after verification.
- Publication branch: `nikita/catalog-payment-handoff`, based on `06112e2`. Remote main
  gained Jeff's integrated jobflow commit `39538c0` during this work. This handoff is kept
  separate to preserve that concurrent implementation; reconciling the two branches is
  a subsequent integration task. No frontend UI was implemented in this branch.

## Catalog baseline validation (before this amendment)

- **130 tests passed at the pre-amendment baseline**: current catalog/API/runtime/gateway/payment behavior plus historical DTO
  decoding. Superseded invoice fee/timeout tests were replaced, not treated as current policy.
- Ruff lint and format checks pass. The locked uv environment includes the new PDF dependencies.
- The pre-amendment OpenAPI exported 22 paths (including health) with catalog models, 60-second policy fields,
  distinct privileged routes and no client-manufactured order snapshot creation endpoint.
  At that baseline the export matched the running localhost Uvicorn schema; /health and /openapi.json
  returned HTTP 200, and the temporary server was stopped.
- The v0.3 wheel builds and was inspected: no evaluator keys, corpus tooling, test fixtures,
  local databases or environment files are packaged.
- Repaired journey: clarification -> accepted quote -> pre-delivery source issue -> evidence
  request -> registered repair -> independently verified PDF -> one mock capture at cutoff.
- Unregistered-authority and conflicting-date journeys: human review, nine relevant evidence
  rows each, no capture. These are engineering scenarios, not independent gold evaluation.
- Rendered and visually inspected the four original source PDFs and all three delivery pages.
  No clipping/overlap; product groups stay together, synthetic/mock disclosure is visible.

Commands and configuration are in README.md. No paid model calls, broadcasts, infrastructure
changes or deployments were performed. Generated PDFs/databases/reports remain ignored.

## Mocks, limitations and remaining decisions

- Customer identity strings are demo audit labels. Customer authentication, tenant isolation,
  production worker isolation, upload malware/resource sandboxing and deployment are future work.
- The parser supports the documented synthetic catalog layout with extractable text; arbitrary
  supplier layouts, scans/OCR and real crop/rotation examples need Jeff/Lucas integration.
- Supplier authority is a synthetic trusted provider registry. Real supplier registration and
  authorized-representative attestation workflows are not implemented. A logo is never authority.
- Offline compiler/semantic implementations are deliberately bounded. Claude is implemented
  behind explicit opt-in, validated with injected responses, but not live-tested or quality-evaluated.
  Semantic/tool disagreement escalates rather than being treated as independent ground truth.
- Runtime model work is injectable; durable jobs are dispatched explicitly through the worker
  API or offline harness. There is no automatic paid provider scheduler or frontend implementation.
- Compilation interrupted between reservation and result retains its budget/reservation; a
  worker refetches and uses a new retry key within the existing deadline/call budget.
- Financial execution remains mock in Phase 1. Base Sepolia/test USDC/Commerce Payments and a
  dedicated platform operator are decided. Live RPC/transaction integration and testnet evidence
  are not complete; production finality/refunds remain outside scope. No x402 or verification fee.
- Rehan's independent gold labels/usefulness evaluation and actual Hyphenate/Coinbase/Microsoft
  sponsor requirements are outstanding. Jev is optional and absent. A RegressionRuleProposal
  contract is an offline extension point, not autonomous production self-improvement.

## First teammate tasks

Nikita: finish the independent reusable Base adapter/terminal laboratory after the frontend
contract handoff, then integrate the same adapter with the offline catalog journey. Jeff: extend semantic/document intelligence and evaluate independent-from-producer checks.
Lucas: build complete request/approve/inspect/respond and buyer-wallet UI against the frozen
API/types/mock responses, including every pending/uncertain/expired display. Rehan: independently label
clean, defective, repaired, substantively amended and unresolved cases and prepare the demo/sponsor
checklist. Exact module ownership/interfaces/completion criteria: responsibilities.md.

Deadline: **Sunday, October 25, 2026, 9 a.m. America/Los_Angeles**.
