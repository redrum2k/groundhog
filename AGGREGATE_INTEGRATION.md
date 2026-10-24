# Aggregate backend integration — qualification and Lucas handoff

Subsequent real-model qualification is now recorded in
[AGGREGATE_MODEL_QUALIFICATION.md](AGGREGATE_MODEL_QUALIFICATION.md). This document
preserves the earlier `849e98a` integration checkpoint, including its then-expired
window and absence of new paid calls. The later explicitly authorized window and
live evidence supersede those statements as current status; defaults remain OFF.

## Delivery scope

Branch: `feature/aggregate-intake-integration-20261024`.
PR: https://github.com/redrum2k/order-to-cash/pull/12 (targets `main`; do not self-merge).
Baseline: `31ad60b9a95b73e0c788752030edc0c0f195f441`, freshly fetched October 24.
During verification main advanced to `04756e131233d47739dfa6c3eb89b917f2b60284`.
Its frontend-only customer-focus changes and route-ownership guidance are integrated
by `37a8bf187e2029ddf48df1d38931f82da2952151`; backend bytes remain identical to
the intake implementation commit `706f41e6aae6e25a2ff34ceafaf505402470cfab`.
First published checkpoint: `e774495192f903d0c1191590cf13cfc4a9439977`;
179 focused backend tests, Ruff lint and formatting passed before publication.

The completed `ef8c99a` backend, exported `db3bafd`, and follow-up `f471718`
are preserved in ancestry, including earlier remote dispute work `db7aab8`.
Only backend changes, documentation, generated contracts and contract-generator
portability fixes enter relative to current main. Lucas's components, routes,
styles, scenarios, tests and dependencies are unchanged. Human reviewer naming,
`/runs`, `/live`, `/jobflow` and retained compatibility APIs remain intact.
Nikita's payment implementation and payment tests are unchanged.

The earlier dirty integration worktree and original feature branch remain intact.
This is not a V6 restart. No running service was restarted and no deadline, ledger,
private environment or historical evidence was reset. No push to main or deployment.

## Intake incident and implementation

The compiler at actual main `31ad60b` was executed against a temporary service:
`SF adults 25–34 interested in fitness, counts by ZIP.` -> clarification;
`gym membership` -> identical clarification; `gym membership` -> human review,
`Clarification budget exhausted.` This reproduces the reported failure.

Cause: main joined every conversation string and required both the `gym` and
`app` substrings before producing terms. A meaningful narrower answer could not
resolve the question. The completed R3/R4 compiler already fixed polarity and
question-bound corrections, but still lacked unavailable-product negotiation.
Those completed fixes are retained, not rewritten as a new architecture.

Now `gym membership` produces a different, explicit offer:
“The available product combines gym membership OR fitness-app use (standalone yoga
excluded). Separate gym-only, app-only and intersection-only counts are unavailable.
Do you accept this broader combined product? Please answer yes or no.”

`yes` bound to that offer produces ready draft terms; `no`, repeated `gym membership`
or `yes, but only gym members` safely leaves human review without a specification.
Ready is NOT quote acceptance or funding. Both questions consume the existing
two-question budget; the 300-second deadline is unchanged. Persisted
`RequestDraft.question_history` prevents identical repeated questions across restart.

Contradictory yoga polarity remains a category clarification. A question-bound yoga
correction cannot erase an earlier app exclusion. Offline union recognition requires
an explicit OR, rather than mere co-occurrence of `gym` and `app`.
Ambiguity/unsupported scope remains unresolved instead of silently expanding a contract.

### Actual compiler wiring

| Path | Behavior |
| --- | --- |
| `main.create_app`, paid flag absent/false | Existing `OfflineCompiler`; aggregate requests use `compile_dataset`, not storage/PDF prompts. |
| `main.create_app`, `ENABLE_PAID_MODELS=true` | Creates `ClaudeGateway` through the existing guarded client/budget configuration. The flag alone does not authorize a call. |
| `CatalogService.compile_request`, aggregate + Claude | Calls new `ClaudeGateway.interpret_dataset`, persists the structured proposal, then validates/builds the versioned dataset contract. |
| `ClaudeGateway.compile` | Retained storage-catalog path; explicitly rejects aggregate contexts. |
| Custom injected compiler/transport | Existing test seam; injected outputs are not real model qualification. |

`DatasetIntakeProposal` allows only registered product intent enums, a buyer quote,
one clarification and its field, and an explanation. Claude receives the actual
answers/prior questions and source pins, not evaluator answers. It can interpret
unfamiliar phrasing, identify ambiguity, propose a product and author a question.
Known contradictions veto readiness; interpreted changes require an explicit
canonical product offer. The server constructs `DatasetSpecification`, source
provenance, coverage, schema and suppression—not a model-generated replacement contract.

The proposal is stored in `catalog_records` as kind `dataset_intake`, ID
`<request_id>:<reserved_revision>`. Calls occur outside database transactions.
The existing revision/idempotency/deadline checks apply before committing results.
No source acquisition, arbitrary tools, executable generated code or money authority
is granted to Claude.

## Model qualification and expenditure

New intake: deterministic/service/HTTP and injected structured-transport tests only.
**No real Claude-generated intake question was observed in this integration.**
The existing authorization closed at **2026-10-24 12:25:38 America/Los_Angeles**,
before this task resumed. It was not extended. New paid requests: **0**, new cost: **$0**;
real intake latency/token usage are unmeasured, not zero-latency claims.

The shared cumulative ledger was inspected read-only: 29 prior requests, no active
reservations, **$1.053300 known cost**, **$1.425636 conservative committed cost**,
against the unchanged $45 ceiling. Counts are telemetry, not a request ceiling.
Failed/uncertain historical reservations remain charged conservatively.

All real SDK traffic still uses `BoundedClient`: durable conservative reservation,
concurrency <=2, absolute cutoff, actual usage/cache/thinking reconciliation,
rate-limit cooldown and repeated-failure/request-loop guards. Intake uses 4,096
maximum output tokens, 20-second timeout and zero SDK retries. Historical costs
and final-evaluation allocation are unchanged. No new client, ledger, purchase,
auto-recharge change or private-key disclosure.

Defaults remain OFF: `ENABLE_PAID_MODELS`, `ENABLE_DATASET_MODEL_ASSESSMENT`,
`ENABLE_BROKER_DISPUTE_ASSESSMENT`. `CLAUDE_MODEL` is authoritative; no
`OBJECTION_MODEL` configuration is introduced. Do not flip flags for the demo
based on fake-transport tests or an expired window.

Historical real primary-dispute evidence is preserved in `PRIMARY_RESULTS.md`:
six frozen cases plus a separately declared development probe, seven actual calls,
40,231 input and 5,593 output tokens (1,138 thinking included), $0.272784.
Original P3/P6 failures remain failures; P7 is not untouched held-out evidence.
Those calls qualify neither this new intake path nor arbitrary dispute competence.

## Disputes and financial boundaries

Primary `/runs` uses the completed guarded dataset assessment: durable single
dispatch per bound snapshot; exact frozen source/cell references; raw candidate
versus effective finding; model/rules/unresolved provenance; stale/deadline checks.
Supported source meaning alone is NOT provider-output defect. Missing authority
remains UNKNOWN; semantic judgment never grants capture, refund, correction or
contract-amendment permission. Existing deterministic payment gates remain separate.

## Exact integration seam for Lucas

Authoritative Pydantic: `backend/app/contracts/runs.py`, `catalog.py`,
`dataset.py`, `semantic.py`. Generated: `frontend/lib/runs.generated.ts`,
`catalog.generated.ts`, `broker.generated.ts`, `frontend/api.generated.ts`,
and `docs/openapi.json`. No handwritten frontend wire union is needed.

Intake continues through `POST /runs`, `GET /runs/{id}/events`, and
`POST /requests/{id}/answers` with `expected_revision`, `idempotency_key`,
`question_id`, `text`. Automatic worker compilation is unchanged; tests also
exercise authenticated `POST /internal/requests/{id}/compile`.
`message.asks` is an opaque field string (including `category_offer_base` and
`category_offer_yoga`); submit the exact pending question ID, not a guessed one.
Current frontend ownership explicitly places Nikita's aggregate intake at `/live`.
Lucas's demo canvas at `/` uses the broker bridge under `/api/broker-run`, with a
recorded fallback. Preserving both routes is not a claim that `/` now consumes the
primary aggregate-intake path. No frontend migration was performed in this PR.

The message event remains:
`{seq, at, track, step, attempt, type:"message", message:{id, from, text, asks, attach}}`.
`step_waiting` carries `waitingOn`. Draft terms emit `contract_line_drafted`;
only actual quote acceptance emits `contract_approved`. Polling never creates consent.
`RequestDraft.question_history: Clarification[]` is additive/default-empty.

Actual offline backend event example:
`docs/handoffs/aggregate-intake-events.example.json` (explicitly not a live Claude run).
Existing real primary semantic event/citation example:
`docs/handoffs/primary-semantic-events.example.json`.

The `verdict` event retains `kind: agree|disagree|grey`, `reason`,
`decidedBy: rules|controller|contract|model|unresolved`, `evidenceIds`, and optional
`finding`. `finding` has `kind: supported|contradicted|unclear`, `reason`,
`evidence_ids`, `decided_by: model|rules|unresolved`, current `binding`, original
`assessed_binding`, accepted-specification SHA-256, `attempt_id`, raw `candidate`,
effective `Assessment`, and `validation: DISPATCHED|VALIDATED|ADVISORY|INVALID|FAILED|STALE`.
Resolve evidence through `GET /runs/{id}/evidence/{id}`; retain current bindings
for reviewer actions. PASS supports the claim, FAIL contradicts it;
UNKNOWN/CONFLICT remain unresolved. A supported finding can legitimately stay grey.

## Verification and integration incidents

Final stable-tree backend run: **783 passed / 11 failed / 0 skipped / 0 errors**
(794 tests, 351.724 seconds), `release-706f41e.xml`. All 34 new intake tests,
19 unchanged R3/R4 tests, 38 primary semantic tests and 12 existing improvement
tests pass in that run. There are **no new failures** versus the original 13-failure
baseline; the remaining 11 are the documented Windows portability failures below.
This is a tested integration branch, not a claim of a wholly green suite or live
model qualification. No code changes are made after that frozen backend run.
Evidence lives under `backend/artifacts/integration-20261024/` (ignored, not private
runtime state). Earlier results and exported archives were not overwritten.
The frozen backend/lockfile implementation digest is
`836fc87ac6089e00d2b9e028cb823682ed0578b730c8fe4c7458ba392efbff17`.

- Baseline published checkpoint: 179 focused tests pass; Ruff check/format pass.
- Intake release subset: 53 tests pass (34 new intake cases plus 19 unchanged R3/R4 cases).
- Frontend: 109 tests pass; strict typecheck and production build pass, preserving
  `/`, `/live`, `/jobflow`, buyer/reviewer and health routes. All generated contracts checked.
- Windows checkout CRLF caused generator byte drift. Scoped LF attributes and newline
  normalization fix it; hidden child-process handling is preserved.
- Current main's 422 phrase differed under Python 3.12 `HTTPStatus`. `main.py`
  explicitly retains main's “Unprocessable Content” schema description across Python versions.
- Offline acceptance initially failed saving a Unicode event under Windows cp1252.
  Preserve that failed output; run the existing tool with `python -X utf8` rather
  than alter Nikita's evaluation scaffold or pretend the first attempt passed.
  The UTF-8 recovery passed all four scenarios (conforming capture exactly once,
  one injected missing-ZIP correction, separate Oakland funding, unsupported yoga
  complaint/no fee). Report: `acceptance-utf8/broker-c4o0txe0/report.json` under the
  integration evidence directory. This is offline mock evidence, not a live payment.
- Development tests exposed four yoga-conflict regressions, then a model paraphrase
  being overruled by a generic yoga-ambiguity rule. These were corrected before release;
  regression cases preserve conflict versus explicit offered-consent distinctions.
- A pre-release full run (`full-final.xml`: 779 pass / 12 fail, 791 collected) began
  before the last edits. Its improvement-cycle test correctly refused approval because
  the implementation digest changed between probe and approval. This was an execution
  sequencing error, not a reason to weaken the guard. Preserve that evidence; the
  release run uses frozen backend `706f41e` and includes the three later consent tests.

Historical comparison: `ef8c99a` had 747 passed / 13 failed (760 total).
Eleven were Windows portability failures (nine subprocess environment cases,
one POSIX permission assertion, one `.venv/bin/python` assumption). Two unchanged
Base transport tests intermittently observe persisted `submitted` before the fake
broadcast list is populated. No payment tests are skipped, weakened or rewritten.

| Previously reported test(s) | Final integration result | Interpretation |
| --- | --- | --- |
| `tests/payments/test_payment_lab.py::test_help_has_examples_and_no_rpc_or_journal[None, preflight, prepare, fund, status, capture, void, reconcile, reclaim]` (nine parameter cases) | All nine FAIL | Stripped subprocess environment omits Windows SystemRoot; WinError 10106 initializing `_overlapped`. |
| `tests/payments/test_payment_lab.py::test_prepare_persists_once_never_changes_salt_parties_or_deadline` | FAIL | POSIX `0600` assertion is not equivalent to Windows permissions. |
| `tests/runtime/test_backend_integration.py::test_import_and_schema_export_do_not_initialize_payments` | FAIL | Hard-coded `.venv/bin/python` does not exist on Windows. |
| `tests/runtime/test_backend_integration.py::test_http_automatic_repair_and_settlement_with_restart[repaired-base_sepolia]` | PASS this run | Prior observation race did not reproduce; not claimed fixed. |
| Same test `[unresolved-base_sepolia]` | PASS this run | Prior observation race did not reproduce; not claimed fixed. |

The earlier in-flight development guard failure is absent on the frozen release
tree: all 12 `tests/broker/test_improvement.py` cases pass. Its failed evidence is
retained rather than rewritten. Latest-main frontend integration was separately
rechecked: **109 tests pass**, typecheck/build/generated-contract checks pass.
Ruff check/format pass across 172 files including the unchanged acceptance tool.
Seven intake events and seven historical semantic example events validate against
the current `RunEvent` schema. Git comparison confirms latest-main UI/payment-owned
paths are unchanged, and completed semantic/budget core files match `ef8c99a`.

## Optional improvement extension — not activated

The preserved compatibility implementation already has incident recording, model
proposals, isolated probes, independent approval, prospective version pinning and
rollback (`backend/app/improvement/service.py`, `IMPROVEMENT_DESIGN.md`). Its allowed
edits remain require-field, replace-question and bind-existing-validator; it is NOT
an aggregate procedure-composition engine and is not silently connected to `/runs`.

No new model-generated procedure was proposed, tested or activated here. Producing
the requested genuine model demonstration would require a valid paid window and
a reviewed aggregate adapter/capability surface with independent comparison cases.
The optional extension is deferred rather than hold the working backend PR hostage.
No gain in clarification rounds from self-improvement is claimed.

Do not duplicate the proposed Nikita aggregate evaluator/Rehan independent expectations
lane: this branch adds developer regressions and a concrete event example, not a new
general evaluation runner or hidden-label corpus. `tools/brokerage_acceptance.py`
is unchanged. Independent expected answers remain outside runtime.

## Reproduce locally, without paid access or payment broadcast

```powershell
$env:ENABLE_PAID_MODELS='false'
$env:ENABLE_DATASET_MODEL_ASSESSMENT='false'
$env:ENABLE_BROKER_DISPUTE_ASSESSMENT='false'
$env:PAYMENT_ADAPTER='mock'
uv sync --locked --project backend
uv run --locked --directory backend pytest tests/dataset tests/broker/test_dispute_assessment.py tests/runtime/test_catalog_gateway.py
uv run --locked --directory backend pytest
uv run --locked --directory backend ruff check .
uv run --locked --directory backend ruff format --check .
uv run --locked --directory backend python -X utf8 ../tools/brokerage_acceptance.py --output artifacts/acceptance
cd frontend
npm ci --ignore-scripts
npm run generate:check
npm run typecheck
npm test
npm run build
```

Use a fresh temporary application DB/artifact directory for a demo; never point these
tests at an existing order/payment journal. No existing server restart is required
to inspect this branch. A deployment or paid-window extension is not part of this PR.
