# Offline aggregate evaluation

Run from the repository root with locked backend dependencies:

```sh
uv sync --locked --project backend
uv run --locked --directory backend python ../tools/aggregate_eval.py --help
uv run --locked --directory backend python ../tools/aggregate_eval.py list
uv run --locked --directory backend python ../tools/aggregate_eval.py validate
uv run --locked --directory backend python ../tools/aggregate_eval.py run --output /private/tmp/aggregate-evaluation
uv run --locked --directory backend python ../tools/aggregate_eval.py run --case D01 --case D02 --output /private/tmp/aggregate-evaluation
uv run --locked --directory backend python ../tools/aggregate_eval.py run --cases cases.json --expectations reviewed.json --case D01 --case-seconds 20 --max-steps 30 --seed 0 --output /private/tmp/aggregate-evaluation
uv run --locked --directory backend python ../tools/aggregate_eval.py run --unscored --output /private/tmp/aggregate-unscored
```

All paths supplied to the script are relative to its working directory (`backend`
with these uv commands); absolute paths avoid ambiguity. List/validate create no
runtime work. The CLI never prompts. Every invocation creates a fresh run directory.
There is no paid lane or RPC configuration. Ambient provider opt-ins/credentials
are discarded; explicit offline clients and network/provider tripwires remain on.

| Exit | Meaning |
| --- | --- |
| 0 | Completed diagnostic evaluation with no expectation mismatches; not a qualification claim |
| 1 | Evaluable quality mismatch; reports written |
| 2 | Invalid inputs, duplicate/missing/mismatched IDs or invalid bounds; no runtime work |
| 3 | Incomplete, missing labels/audits, timeout, step limit, operational failure or tampered frozen input; available evidence and reports retained |

Correctly blocking a deliberately defective artifact is success when the frozen
expectation calls for blocking. Missing independent gold allows an engineering
report, never independent accuracy. `--unscored` preserves every scheduled row and
exits 3. Operational incompleteness takes precedence over quality mismatch.

## Inputs, execution and evidence

`schema.py` defines strict `aggregate-cases-v1`, `aggregate-expectations-v1` and
`aggregate-scoring-v1`. The bundled JSON files are complete examples. Case IDs,
checkpoint IDs and all eight requirement IDs must match exactly, with no duplicates
or extra fields. A full expectation file matches the full case file; `--case`
selects matching subsets from both. Each label includes its rationale. Review status
(`engineering` or `rehan_reviewed`), reviewer and review rationale are separate from
the case's `development`/`held_out` classification. A supplied review record is an
evaluator assertion, not authentication or automatic proof of independent review.

The v1 fixture recipes cover conforming output, first-attempt missing ZIP/correction,
unsupported yoga complaint, separately accepted/funded Oakland work, missing publisher
authority and a conflicting edition. Adding new execution recipes requires a fixture
version and tests; arbitrary code or provider names cannot be supplied through JSON.
The explicit fixture compiler uses the supported constructor boundary and freezes
gym/app scope. Intake quality is unscored. Source variants are registered before
compilation/quote/acceptance. Only the output-defect fixture patches production, in
its own subprocess; it changes actual bytes, never a finding or payment gate.

Every case has its own SQLite DB, artifact root, controlled UTC clock and process.
The only two related orders share a case intentionally: the base order and separately
accepted additional-scope child. Acceptance and explicit mock authorization precede
confirmed mock funding and normal `run_one` work. Settlement is the existing service's
60-second review-expiry path. There is no evaluator ledger or financial override.
The parent kills/reaps cases at the wall limit (default 20 seconds, max 120); explicit
steps/page walks are capped at 30 by default. It retains partial evidence and runs
unrelated cases. The seed is frozen; runtime UUIDs remain nondeterministic.

Before execution, `private/frozen-plan.json` stores and hashes selected cases,
expectations, scoring configuration, code revision, dirty paths and source hashes.
The parent verifies the pinned hash before every case and after the run; code changes
during execution invalidate completeness. Each private case directory retains the
accepted specification and frozen source versions/hashes, actual artifact bytes,
service inputs, pre-commit verification attempts, checkpoint orders and complete
paginated events. Initial failed findings and artifacts survive correction. Historical
findings invalidated by correction are labeled with their original binding, separately
from the current order binding. No raw model response is created or retained.

`results.json` (`aggregate-results-v1`) and standalone `report.md` use the same
normalized result. Only independently valid, suppression-safe CSV/JSON copies appear
under public `artifacts/`; exact unsafe original bytes stay under `private/` in the
mode-0700 run directory. Do not publish that private directory. Reports omit cited
cell values and parser exception text, and redact credentials/URLs. Run output is
local evidence, not committed generated data. Keep outputs outside the repository
or under an already ignored `artifacts/` path.

## Audit and scoring

`audit.py` extracts Jeff's pure `exact_cell` logic from
`ef8c99afb9cf5f3b6928f505242f2d622fce2c3e:tools/audit_primary_evidence.py`, Git blob
`51acbf86a90ff8f1cc3e7397db3fd7776ad2fc68` (identical at observed `e774495` and fetched
`849e98a`). It never executes that module's private-path main, reads its ledger or
inherits its model/rates/case assumptions. Focused vectors preserve present-cell
semantics. Tested extensions handle CSV nulls, unpublished-attempt delivery versions,
missing top-level keys and absent ZIPs proven by the accepted coverage pin. Other
reference kinds and JSON without source identity remain unsupported/unscored.

Audits reopen actual bytes, check SHA-256/source identity/version, unique rows and
cell equality. They distinguish missing keys from present nulls. A separate artifact
comparison in the same module checks CSV/manifest/schema/coverage/source agreement.
It never invokes the runtime resolver or trusts a runtime PASS. Citation structural
validity is distinct from Rehan's substantive expectation review.

Unit: **accepted requirement × scheduled checkpoint**. D01–D06 schedule 80 correlated
requirement observations across 10 checkpoints, not 80 independent cases. Every case
and every accepted requirement appears, including missing/failed observations.
Engineering and independently reviewed results are separated within development and
held-out partitions. Complaint findings are shown separately: their PASS means support
for the complaint, whereas a requirement PASS means the requirement is satisfied.

| Metric | Numerator | Denominator |
| --- | --- | --- |
| Agreement | Effective label equals frozen label and citations audit valid | All labeled scheduled requirement observations |
| False PASS | Effective PASS with a non-PASS label | All labeled non-PASS observations |
| Missed contradiction | Expected CONFLICT but effective result differs or is absent | All expected CONFLICT observations |
| Appropriate UNKNOWN / CONFLICT | Matching label with valid citation audit | All corresponding expected labels |
| Excessive abstention | Effective UNKNOWN/CONFLICT when expected PASS/FAIL | All expected determinate observations |
| Raw model errors / errors caught by enforcement | Unavailable on this deterministic baseline | N/A: no observed raw model candidates |

Missing findings/audits/labels never count as matches; scheduled totals and unscored
counts stay visible. Zero denominators are N/A. Artifact, action, booking count and
financial-state comparisons also affect the case outcome. These financial states
retain service vocabulary: `funded` is held, `voided` is returned; `funding_pending`,
`capture_pending`, `void_pending`, `uncertain` and `expired_not_returned` remain distinct.
Actual mock bookings are retained, with no live transaction IDs or invented fees.
Provider usage, cost and rates are unavailable, not zero.
