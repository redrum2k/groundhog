# Workstream 04 — backend integration and validation

Branch/worktree: `codex/backend-integration`, `order-to-cash-integration`.
Started clean at `ac385a1abf1ce66dfd1f792cac021cfa5286d7ae`; main remains at that commit.
All changes stayed in the assigned integration worktree. No reset/cherry-pick, other-worktree
mutation, push, PR merge, paid call, real chain RPC/broadcast, deployment, existing secret or
private database use. Temporary/synthetic stores only. The commit containing this handoff
contains the final integration corrections; its SHA is returned in the completion summary.

## Pinned source commits and history

No external completion summaries were attached. Each local branch had one final implementation
commit with its committed `docs/workstreams` completion/validation handoff. Inspected history,
commit contents/ownership and handoffs before merging these exact SHAs, not moving tips:

| Workstream | Completed SHA | Integration merge commit |
| --- | --- | --- |
| Runtime | `3a7b7543763ef645369913317dcdddbf68eec262` | `3693efa04e39a300a77a701b4486735c10088593` |
| Base transport | `a23f999e855964ff094acde137f35a2148895b7b` | `f72944a22f61d549813b7b6b3b21d05d47e69fa4` |
| Catalog settlement | `1483046b0eea5da553de169e87beac5bc57bd202` | `22f52dbf923140343aa024424ddcc6829fa25a2e` |

All three no-fast-forward merges completed without conflicts and remain ancestors of HEAD.
The combined baseline passed 427 backend tests before integration corrections. Jeff's semantic/
document implementations and Lucas's invoice UI were preserved; no UI or credential proxy added.

## Final interfaces and corrections

- `CatalogWorker(service).run_once() -> bool`: selects at most one draft/job attempt. Automatic
  compilation follows request/answer; fulfillment/evidence rechecks require current binding,
  authority and funded state. Source extraction/PDF/model work runs outside write transactions.
- `BasePaymentTransport(config, *, rpc=None)` implements the unchanged `PaymentTransport` and
  exposes `verified_usdc_domain() -> dict` plus read-only `preflight()`. Catalog preparation
  persists the verified domain/typed data; exact preparation replay needs no new RPC. No mock
  domain on Base failure. Transport owns encoding/signing/evidence; catalog owns money gates.
- `CatalogService(repository, artifact_root, clock=utc_now, *, compiler=None, assessor=None,
  auto_mock_funding=False, payment_mode="mock", payment_config=None, payment_transport=None)`
  is wired through `create_app`'s added keyword-only payment injection seam. Invoice construction
  stays independent and mock, including with PAYMENT_ADAPTER=base_sepolia in the environment.
- `payments.catalog_payment_setup()` initializes only in lifespan. Mock is default; selected
  Base constructs explicit config/transport and runs read-only preflight off the event loop.
  Invalid config fails redacted; missing signer/RPC/parties or failed preflight leaves Base
  unavailable and submission disabled. An available transport can still reconcile; restart
  after repairing startup configuration. Import/schema export has no RPC, signer-config or
  private .env loading. Startup health is capability, not proof of transaction success.
- `payments.work(limit=20)` accepts integers 0–20; the automatic lane uses 1. Submission requires
  effective startup readiness/opt-in and transport checks. Funding/terminal confirmation and
  booking share the catalog repository transaction; PAYMENT_JOURNAL_PATH belongs only to the lab.
- Fixed bounded-payment starvation found during self-review: a disabled reserved operation
  previously monopolized oldest-first selection, preventing another submitted receipt from
  reconciling. A failing regression demonstrated it. Deferred operations now update only their
  attempt timestamp under their lease, retaining state/nonce/bytes and yielding the next turn.
- Fixed runtime's reported compiler race: manual budget exhaustion advances revision, saves
  exact command replay and rejects an in-flight fourth result unless status is still compiling.
- Updated the README harness to explicitly prepare/authorize simulated funding and invoke
  CatalogWorker selection. It no longer auto-funds acceptance or directly dispatches each job.

Five independent thread lanes: catalog deadlines (1s), invoice deadlines (1s), catalog dispatch,
payment processing and invoice dispatch (each 0.25s after completion). One active call per lane;
slow/failing model/PDF/RPC work does not consume the deadline slots. Graceful/cancelled shutdown
retains ownership while active calls drain; hard restart uses persisted leases. Trusted manual
endpoints remain compatible. This is a bounded local demo, not a distributed queue platform.

## Contract and Lucas handoff

Catalog remains API 0.4.0 / catalog-api-v1 / catalog-payments-v1: **26 paths, 66 schemas**.
Invoice remains separately mounted with **10 paths** at `/api/jobflow` and its own OpenAPI.
Routes, request/response/error fields and enums are unchanged. The single schema/export change
is the existing health live_adapter default, planned → disabled, because Base is implemented
but unselected by default. Generated TypeScript differs only in that default's documentation.
Historical planned remains a valid enum; fixtures and immutable saved responses were not rewritten.

Existing health values: disabled = implementation unselected; unavailable = selected but missing
prerequisites/failed startup preflight; ready = configured signer/parties and successful startup
preflight. live_settlement_enabled additionally requires explicit broadcast opt-in. Neither flag
claims live verification. Per-payment frozen terms and observations control display and authority.

[Lucas's backend integration recipe](../handoffs/lucas.md) includes automatic work, exact root
paths, current binding/available_actions, signing/preparation/submission, polling, exact replay,
stale 409s, and protected server-side calls. INTERNAL_API_TOKEN uses X-Internal-Token for provider
work/offers/approvals/retry; REVIEWER_API_TOKEN uses X-Reviewer-Token for cited review decisions.
They must differ and stay server-side. Lucas owns the authenticated server bridge. No browser
capture/void route or unauthenticated credential-forwarding proxy is introduced.

## Validation actually run

All tests use temporary databases, synthetic PDFs, injected models/RPC/clocks. The actual
BasePaymentTransport is exercised through the complete FastAPI lifespan and HTTP routes,
including signing with public synthetic test scalars; no real chain connection exists.

| Check | Result |
| --- | --- |
| `uv sync --locked --project backend` | Passed. |
| `uv run --locked --directory backend pytest` | **442 passed in 57.00s**, one upstream deprecation warning. Earlier merged baseline: 427 passed; pass before final invoice-env regression: 441 passed in 56.08s. |
| `uv run --locked --directory backend ruff check .` | Passed. |
| `uv run --locked --directory backend ruff format --check .` | Passed, 107 Python files. |
| Focused integration + settlement + journal run | 59 passed in 14.22s before the final invoice-env regression; that extra regression also passed independently. |
| Repaired README offline journey | Closed; exactly one mock capture; independently verified shortlist PDF; no human-review rows. |
| Unresolved README offline journey | human_review; nine relevant evidence rows; no bookings/capture. |
| `backend/.venv/bin/python spikes/payments/examples.py` | 27 separate CLI subprocess commands passed: independent capture, void and expiry/reclaim. |
| Ruff lint/format for `spikes/payments` and `tools/offline_journey.py` | Passed, six files. |
| Actual temporary Uvicorn `/openapi.json` | Exactly equal to docs/openapi.json; 26 paths / 66 schemas. `/health` mock/disabled; separate invoice schema has 10 paths. Server stopped. |
| Actual temporary fixture server | All 12 payment states returned valid simulated data, no explorer links; server stopped. |
| Catalog OpenAPI export and pinned openapi-typescript 7.10.1 generation / `--check` | Passed. Runtime/schema and generated types match. |
| Strict TypeScript 5.9.3 check of catalog helpers/generated types | Passed. |
| Frontend `npm ci` / `npm run generate:check` | Passed with Node 24.14.1 / npm 11.11.0. Invoice generator remains distinct from catalog OpenAPI generation. |
| Frontend `npm run typecheck` / `npm test` / `npm run build` | Passed; all 29 tests in six files; Next production build successful. |
| `git diff --check`, ancestry and main SHA checks | Passed; all three exact workstream SHAs retained, main unchanged. |

Additional exact repository-root validation commands (frontend npm scripts ran from frontend
with Node 24.14.1 first on PATH and ~/.local/bin available for uv):

```sh
uv run --locked --directory backend python ../tools/offline_journey.py --scenario repaired --output /private/tmp/backend-integration-repaired-final
uv run --locked --directory backend python ../tools/offline_journey.py --scenario unresolved --output /private/tmp/backend-integration-unresolved-final
uv run --locked --directory backend python ../tools/export_openapi.py --output ../docs/openapi.json
npx --yes openapi-typescript@7.10.1 docs/openapi.json --output frontend/api.generated.ts --default-non-nullable false
npx --yes openapi-typescript@7.10.1 docs/openapi.json --output frontend/api.generated.ts --default-non-nullable false --check
frontend/node_modules/.bin/tsc --noEmit --strict --skipLibCheck --target es2022 --moduleResolution bundler --module esnext frontend/contracts.ts frontend/api.generated.ts
backend/.venv/bin/ruff check --config backend/pyproject.toml tools/offline_journey.py spikes/payments
backend/.venv/bin/ruff format --check --config backend/pyproject.toml tools/offline_journey.py spikes/payments
```

New application tests cover request → automatic clarification → quote → acceptance → explicit
simulated funding → automatic work → requested evidence repair → verified PDF → review timeout →
one mock capture. The unresolved path reaches human review with no capture. Actual transport
with delayed synthetic receipts additionally proves no work at submission, persisted restart,
one funding job, independent capture and reviewer-authorized void, no premature booking and no
second send. Auth rejection, exact saved HTTP replay, unavailable config/preflight, no import/
schema side effects, compiler exhaustion and disabled-submission polling are directly tested.

The merged settlement suite separately exercises stale evidence before submission, late disputes
after submission, atomic booking rollback, uncertainty/reorg/receipt-loss holds, one terminal
winner, replacement ordering (including failed/uncertain/late parent return and parent reorg),
independent additional work, replay/signature redaction and byte-for-byte historical mock records.
Merged runtime tests prove slow/failing model/payment isolation, deadline sweeps, consent gates,
lease/restart concurrency, stale result rejection and safe normal/cancelled shutdown. All existing
auth, error, fixture, legacy and catalog/invoice assertions ran; none was skipped or weakened.

Environment failures were kept separate: default Node 20.19.5 is below package.json's >=22.12.0;
checks used installed Node 24.14.1. Restricted npm DNS caused ENOTFOUND/exit-handler errors;
explicitly approved retry installed locked dependencies. A truncated PATH initially hid uv;
restoring ~/.local/bin fixed it. uv cache access and localhost socket binding needed approved
sandbox escalation. Final checks pass; no dependency/version downgrade or assertion skip.
The backend emits one upstream websockets.legacy deprecation warning. Initial harness Binding /
PaymentBinding mismatch and test-fixture field assumptions were corrected before final validation.

## Remaining live preflight/demo steps and completion

Offline integration and backend/frontend contract handoff are complete; no remaining offline
blocker. **Observed live RPC results/testnet transactions: none.** Mock, injected-chain and actual
live evidence are distinct throughout the runbook/status/handoff. No paid calls, broadcasts or
deployment were requested or performed. No PR was pushed or merged.

Separately authorize fresh disposable operator/payer/provider setup. Verify chain 84532, actual
pinned deployment/code/linkage, token domain/decimals, EOA parties, test ETH/USDC, token-store
custody, historical EIP-1898 reads and RPC latency. Observe two independent 100000-atomic-USDC
payments: fund → restart → full capture and fund → full void, matching canonical events/state/
balance deltas and provider non-authority; then exercise ambiguity/reclaim recovery. These lab
amounts are not funding for a USD 15 catalog order. Only observed transactions receive real links.

Known recovery limits remain explicit: no rebroadcast, replacement/fee-bump or new-nonce escape;
a crash between durable submitted and actual send can remain pending. Orphaned receipts require
manual recovery and cannot silently erase bookings. Per-RPC timeout is 15s/no retries; multi-read
preflight can exceed the 120s payment lease and is fenced, not renewed. Verify latency before a
live demo. Graceful shutdown drains threads; a stuck injected/native call cannot be forcibly
cancelled safely. No refund execution or catalog reclaim route. Production authentication,
tenancy, deployment, catalog UI/wallet bridge and independent semantic/sponsor evaluation remain
separate scope. See [runbook](../PAYMENT_RUNBOOK.md) and [spike](../PAYMENT_SPIKE.md).

## PR-ready description

Title: Integrate automatic catalog runtime and gated Base settlement

Merge the completed runtime, Base transport and settlement commits with history preserved.
Wire explicit lifespan-only Base selection and fail-closed capabilities while retaining default
mock and isolated invoice behavior. Fix stale compiler completion and payment polling starvation;
update the offline journeys and Lucas's automatic-work/server-bridge handoff. Preserve public
routes/DTOs and historical responses; refresh only health's implemented-adapter default in the
OpenAPI/TypeScript exports.

Validation: full backend suite and Ruff, combined HTTP/lifespan mock and synthetic-RPC journeys,
repaired/unresolved README runs, 27 lab subprocess commands, actual runtime OpenAPI/12 fixtures,
catalog type freshness/compilation and existing frontend generation/typecheck/29 tests/build.
No live chain proof, paid calls, deployment, push or production authentication claim.
