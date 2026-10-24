# PR #12 — three P1 correctness fixes

Historical evidence for the first three findings. The subsequent accepted-scope
and durable-dispatch fixes, latest integration and tests are documented in
[BROKER_RECOVERY_REMEDIATION.md](BROKER_RECOVERY_REMEDIATION.md).

Scope: the user's October 24 focused remediation request, not another paid model
experiment. PR remains unmerged. No paid calls, broadcasts, deployment, shared procedure
activation or frontend/payment implementation changes are part of this work.

## Provenance and reproduction

Fetched the existing PR head `e5ab269822767ac6d935f9caffab39e4b417a6cf` and new main
`947140eb4f040058b81a43438bb5bf138f1febf7`. Integration `19bcf8e` imports Nikita's
aggregate evaluator unchanged; the only conflict was handoff text, retaining both
histories. The three affected runtime implementations were unchanged by main.

All three Greptile findings are **valid**. The before-fix run retained **22 failing
and 2 passing tests** in `backend/artifacts/greptile-p1-20261024/before.xml`.
Reproduction tests were committed at `44de0fe` before the application fixes. The
compile-replay helper's original key was corrected in that test commit; the
recorded original defect failures occur before replay and remain unchanged.

Tested application commit: **`43cb18c94d2987f123ad48b791aa761e68fa7969`**.
The final change contains four production files and three regression-test files.
Later report/PR updates must not be represented as fresh model qualification.

## Findings, corrections and regressions

### 1. Material cohort ambiguity could be discarded

[Original review](https://github.com/redrum2k/order-to-cash/pull/12#discussion_r4368403627).
The parser recognized SF but not Seattle. Model category ambiguity blocked terms,
but a model proposal marked `ambiguous` / `cohort` did not participate in
`cohort_ok`, so the original example returned SF-only ready terms.

`app/agents/dataset.py` now makes that signal block readiness, even if the model
omits its question text. The server renders the exact supported age/city/ZIP offer.
An opaque `cohort_scope_offer` question ID persists the unresolved scope gate;
the public field remains `cohort`, with no DTO change. This matters because merely
asking a question would still let an incomplete answer or offline restart reuse the
same partial parse. Only an affirmative answer to the exact persisted offer clears
this gate. Conditional answers, repeated multi-city requests and refusal remain
unresolved; they never silently become SF-only terms. Existing R3/R4 explicit
corrections under their original question types remain intact.

`tests/dataset/test_cohort_ambiguity.py` covers the reported example, unrecognized
age-scope text, omitted model question text, acceptance/refusal/conditional answers,
restart with the offline compiler, quote and wrong-question bypass attempts,
compile/answer replay, persistent ambiguity, two-question limits and deadline
expiry. This fixes handling of identified ambiguity; it does not claim a complete
geography recognizer or unrestricted natural-language understanding offline.

### 2. Successful proposals could lose their model provenance

[Original review](https://github.com/redrum2k/order-to-cash/pull/12#discussion_r4368403631).
Dispatch preferred `CLAUDE_MODEL`, but response handling indexed the absent legacy
`ANTHROPIC_MODEL`; the cycle failed after a successful response. Conflicting values
instead persisted the wrong proposer identifier.

`app/improvement/service.py` resolves the established `selected_model()` once and
uses the identical value for dispatch and usage/proposal provenance. `CLAUDE_MODEL`
remains authoritative; legacy decoding fallback is unchanged. Missing configuration
is rejected before opening a client. Typed validation, job records, idempotency,
failure handling and explicit proposal approval/activation boundaries remain intact.

`tests/broker/test_improvement_model_identity.py` injects a model client and checks
CLAUDE-only and conflicting configurations, including environment changes during
the await. Successful proposals persist with exact model/tokens, survive restart
and replay without a new call, and do not activate a procedure. Existing malformed
proposal and budget tests also pass; these are test-double results, not live calls.

### 3. A SQLite lock wait could outlast model-call authorization

[Original review](https://github.com/redrum2k/order-to-cash/pull/12#discussion_r4368403633).
The old cutoff check preceded `BEGIN IMMEDIATE`. A waiting process could resume
after expiry, insert a reservation, and invoke the SDK. The timeout helper further
converted expiry into a positive 1 ms timeout, and the injected synchronous parse
path lacked a final window check entirely.

`app/agents/budget.py` now shares one start/cutoff check and rechecks it under the
SQLite write lock immediately before inserting a reservation. Both clients in
`app/agents/bounded_client.py` revalidate after request/schema preparation and bound
method selection, immediately before SDK invocation. Expiry fails closed rather
than manufacturing a nominal timeout; both raw-response and injected parse paths
are covered. Explicit shorter timeouts remain bounded by the remaining window.

Known non-dispatch creates an `ABORTED_BEFORE_DISPATCH` audit state with zero actual
cost, retaining the reservation amount, request hash, window and completion time.
It releases active concurrency without deleting history. After SDK invocation,
unknown usage still retains the full conservative cost; a later abort cannot erase
an already completed/uncertain record. A lock-wait rejection creates no reservation.
No ceiling, final reserve, allocation, prior window or historical expenditure was
reset. The original shared $45 maximum and concurrency <=2 remain enforced.

`tests/investigation/test_model_cutoff_races.py` uses a real SQLite write lock,
Events and an injected clock—no timing sleeps—to force expiry during the lock wait
and between reservation and dispatch. Sync parse, raw sync and async fake SDKs all
receive **zero calls** in expired cases. Controls cover open/future windows, exact
cutoff, timeout bounds, audit state and conservative post-dispatch failure handling.

Limit: the final check cannot atomically bind wall-clock time to an external
network send. OS scheduling pauses or SDK-internal work can occur after the check;
the timeout is a client bound, not a hard real-time guarantee. Process interruption
before reconciliation can retain an active/full conservative reservation, requiring
recovery rather than assuming a free or unsent request.

## Validation

- Initial focused suite: **100 passed**.
- Expanded adversarial regressions: **32 passed**.
- Relevant `tests/dataset tests/investigation tests/broker`: **411 passed**.
- Backend/tooling Ruff lint and format: **209 files passed**.
- Generated-contract freshness: passed, no generated-file changes.
- Frontend: **109 tests passed**, TypeScript passed. No route/component changes.
- Full backend at `43cb18c`: **925 passed / 16 failed / 0 skipped / 0 errors**,
  941 tests in 352.739 seconds (JUnit). All 32 new regressions pass in this run.

The [portable evidence summary](docs/evidence/greptile-p1-20261024.json) preserves
each XML digest, the original failure messages, exact baseline comparisons and
the separate diagnostic-control result. **All 13 failures from the last integrated
Windows/payment baseline (`3a15bd8`) persist**, with no changed failure identities.
The other three failures are from main's newly imported, unmodified evaluator:

- `test_leakage_stable_report_additive_runs_and_no_gold_claim`: UTF-8 Markdown is
  compared with a locale-default `read_text()` under Windows.
- `test_real_child_timeout_then_unrelated_case_continues`: the subsequent worker
  cannot complete under its stripped Windows startup environment.
- `test_step_limit_preserves_partial_state_and_reports`: the worker reports
  `OSError` rather than reaching the expected `StepLimit` boundary.

All three pass in a **separate diagnostic control**, with Python `-X utf8` for the
test parent and an in-memory subprocess wrapper adding only nonsecret `SystemRoot`
plus `CREATE_NO_WINDOW` to evaluator workers. The controls do not change source,
assertions, real deadlines, secrets, model enablement or payment settings. They
establish Windows portability follow-ups for Nikita; they are **not** a repaired
full-suite result. No evaluator or payment source/tests were edited. The normal
Windows suite remains red, and this is not deployment/payment qualification.

Commands use `uv run --locked --directory backend`; full pytest runs with paid
models/testnet broadcasts disabled and mock payments. XML evidence is additive
under `backend/artifacts/greptile-p1-20261024/`. No old qualification cohort was
rerun or relabeled, and no original failure was skipped or weakened.

The existing cumulative model ledger is byte-identical before/after verification:
SHA-256 `000cfe72360895d2ae1c0fec6ed6023499d31bcbcb265ea699930f4a23b7fad5`.
No private environment file was loaded or edited. Authorization windows and
historical spend remain unchanged; zero additional real Claude calls occurred.

## Boundaries and review

Lucas's components/routes, including `run-app.tsx`, and Nikita's payment/runtime/lab
paths are unchanged against both the prior PR head and imported current main.
The aggregate evaluator is imported byte-for-byte from main, not modified to fit
the compiler. Accepted contracts and financial authority remain outside model output.
Historical [Claude qualification](AGGREGATE_MODEL_QUALIFICATION.md) retains its
frozen versions, raw evidence and limitations. This pass provides injected/no-network
correctness evidence only. All model feature defaults remain OFF.

The fixes are ready for another independent review after final validation. No
approval is inferred from local tests, and PR #12 must remain unmerged until the
critical findings are independently reviewed.
