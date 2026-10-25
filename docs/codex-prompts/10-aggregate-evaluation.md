# 10 — Aggregate evaluation runner and readable results

Implement the evaluation-tooling delegation agreed with Jeff. This is a separate
PR after the local/main integration; it is not payment recovery or another compiler
rewrite. Use a new `codex/aggregate-evaluation` branch/worktree from the resulting
reviewed main, preferably `../order-to-cash-aggregate-evaluation`. Inspect current
status/history/worktrees and record the exact starting SHA. If that task worktree
already exists, continue it without resetting or creating a competing checkout.

Read AGENTS.md and applicable nested instructions, especially evals/AGENTS.md;
HACK.md, docs/PAYMENT_SPIKE.md, docs/responsibilities.md, the Jeff/Nikita/Rehan
handoffs, workstream 06, tools/brokerage_acceptance.py and the existing eval layout.
Read the latest integration record. Preserve all teammates' edits.

## Agreed ownership and existing work

The user and Jeff have delegated **general aggregate evaluation infrastructure**
to Nikita. Record this narrow exception in evals/AGENTS.md and the responsibility/
handoff documents in this branch; an older statement assigning all evaluation
tooling to Jeff does not block this authorized task.

- **Nikita:** isolated case execution, requirement-level scoring, integration of
  independent byte/citation audits, JSON results and a readable comparative report.
- **Rehan:** independent expected outcomes, rationales and review; frozen evaluator
  expectations and development/held-out classification.
- **Jeff:** compiler R3/R4 preservation, conversational interpretation, explicit
  scope consent, Claude wiring, evidence enforcement and developer regressions.
  Do not edit his compiler, gateway, lifecycle enforcement or runtime contracts.
- **Lucas:** frontend. No UI changes belong to this evaluator PR.

Own a thin `tools/aggregate_eval.py` entry point, cohesive helpers in
`evals/aggregate/`, focused tests under `backend/tests/evals/`, minimal evaluator
docs/ownership updates, and `docs/workstreams/10-aggregate-evaluation.md`.
Keep `tools/brokerage_acceptance.py` working as the small existing smoke runner;
reuse its service flow rather than replacing it with the general evaluator.
Existing legacy `evals/run_v5.py` and its reports remain intact.

Jeff reported the following reuse candidates, now available on
`origin/feature/aggregate-intake-integration-20261024` at observed commit
`e774495192f903d0c1191590cf13cfc4a9439977`:

- `backend/primary_followup_eval.py` and `primary_certificate_probe.py`: six-case
  semantic diagnostic and development probe, not independent qualification.
- `tools/audit_primary_evidence.py`: independent CSV/JSON citation-cell inspection
  and saved-usage reconciliation. Reuse the verified pure audit logic.
- `PRIMARY_RESULTS.md` and `PRIMARY_HANDOFF.md`: one-off historical reports; keep
  their frozen results and provenance unchanged.
- Feature commits `d2b6ba1`, `5946378`, `ef8c99a` are available. His earlier reported
  local merge `0983c1b` was not available when this prompt was written. Do not assume
  his additional uncommitted conversational amendment was published or qualified.

Inspect actual fetched contents and provenance before using them. If these files
are already on reviewed main, reuse them there. Otherwise inspect the exact published
audit blob and make a narrow, attributed reuse/extraction of the required tooling;
do not merge/cherry-pick the entire runtime branch merely to obtain an audit helper.
Any copied/refactored helper must be included in this PR with focused compatibility
tests and its source SHA. Do not create a competing second cell auditor.

The current one-off audit has a Windows-specific private ledger path, hardcoded
case/model/rate assumptions, and supports present-cell references only. Never run
its `main()` against those paths or silently inherit those assumptions. Reuse pure
byte checks through explicit case/artifact inputs; support other reference kinds
only with tested semantics, otherwise report them as unsupported/unscored. Runtime
resolver success alone is not an independent citation audit. If a dependency cannot
be reused safely, report that dimension unavailable and preserve the results; do
not call the evaluation fully qualified until the required audit is available.

## Scope and case isolation

Use `aggregate-brokerage-v1`, actual CSV/JSON artifacts and the existing service
interfaces. Begin with accepted, explicit-scope fixtures so unfinished conversational
compiler behavior cannot contaminate output-verification metrics. Obtain accepted
state through the normal service acceptance/funding boundaries; no direct database
shortcut, synthetic PASS injection or payment-gate bypass. If a fixture compiler
is injected at the supported boundary, disclose it and do not score intake quality.

Use a fresh temporary database, artifact root, controlled clock and independent
runtime state per case. Mock funding must be explicit; no real RPC or live wallets.
Bound case execution, preserve failures/timeouts and continue unrelated cases.
Retain the exact accepted specification, source versions/hashes, output bytes,
requirement findings, bindings and relevant events for later audit. Preserve initial
failed deliveries/findings as well as corrected outcomes; successful repair must
not erase evidence of the original failure.

Keep evaluator-only fields out of runtime DTOs, prompts, evidence passages, manifests
and tools. Mutation labels, expected outcomes and grading rationales stay on the
evaluator side. Inject defective artifacts only through test-owned seams and give
the runtime only the resulting allowed evidence. Do not expose evals/expected to
an agent or add a production import of the evaluator. Include leakage tests with
canary expectation text and serialized runtime inputs.

## Expectations, scoring and evidence

Use a strict, versioned case/expectation format. Freeze and hash the selected cases,
expectations and scoring configuration before execution. Record code revision,
dirty-tree status, fixture/audit versions, run mode and relevant deterministic seed.
Never derive an expected result from the candidate's answer. Rehan's independent
review status and rationale are distinct from engineering expectations.

Development fixtures may exercise the tooling immediately, but label them as such.
Do not invent Rehan approvals, independent gold, held-out qualification or aggregate
accuracy when reviewed expectations are missing. Keep development and held-out
results separate; reject missing, duplicate or mismatched case/requirement IDs in
scored runs. Preserve a frozen run and create a new report rather than overwriting it.

For every accepted requirement, report these layers separately:

1. Raw semantic/model findings when actually available; otherwise explicit absence
   or deterministic-only provenance. Never manufacture a model result.
2. Effective findings and runtime enforcement: publish, block, request evidence,
   correct, escalate or settle. Record which attempt/version each result concerns.
3. Independent expected result and evaluator comparison, including artifact/citation
   checks. A successfully resolved citation is not proof that the cited text entails
   the claim; distinguish structural validity from substantive expectation review.
4. Financial disposition and actual mock booking evidence. Held, pending, captured,
   returned, expired and uncertain states are distinct; no fee/cost/receipt is invented.

Define metric units and denominators explicitly. Include false PASS, missed
contradiction, appropriate UNKNOWN/CONFLICT and excessive abstention on cases where
reviewed evidence supports a determinate answer. Distinguish a requirement PASS
from a complaint finding that supports the complaint; those have different meanings.
Separate raw-model errors from errors caught by enforcement. Missing audit results,
missing expectations, blocked runs and exceptions are never silently counted as
correct or dropped from the scheduled-case total. Zero-denominator metrics are N/A.

Reopen actual artifacts and validate hashes/versions before auditing cells. Preserve
suppressed null values and meaningful missing/absent-key evidence. Do not leak an
exact suppressed count into the readable report, even in a deliberately defective
engineering fixture. Keep unsafe original bytes private as test evidence.

Use representative development cases covering conforming output, detected output
defect/correction, unsupported factual complaint, separately accepted additional
scope, insufficient evidence and contradictory evidence. Add meaningful audit/scoring
regressions for tampered bytes, stale references and falsely passing observations.
Do not force the runtime to return the expected answer. Record a known runtime gap
as a result or dependency, not a reason to edit Jeff's semantics in this PR.

## Runner and reports

Default to offline execution with paid models and testnet broadcasting disabled.
Support explicit case selection, output directory and expectation input; give useful
`--help` examples and a validate/list path that creates no runtime work. Avoid prompts
for interactive input. Use fresh run directories and bounded case time/step limits.

Produce schema-versioned JSON plus a standalone readable Markdown report from the
same normalized results. The report needs a summary with denominators, a row for
every scheduled case, a requirement matrix, raw/effective/expected comparisons,
financial state, valid artifact references, failures and missing dependencies.
Readers should be able to see why a case failed without opening SQLite or raw logs.
Include run-level incompleteness and per-case operational errors, not just a pass rate.

Document distinct exit outcomes for completed evaluation, quality mismatches,
invalid inputs and incomplete/operational failure. A deliberately defective case
that the runtime correctly blocks can be a successful evaluation. Write the report
before returning a nonzero result for evaluable failures. Missing gold permits a
development report but never a qualification-success claim. Redact secrets and
credential URLs; raw model responses, if retained at all, remain private and bounded.

Paid execution may be a separately guarded optional lane only if an existing reviewed
service interface supports it. Do not add Claude/provider wiring or read private
environment files for this task. No paid call is authorized. Test the default's
network/provider guards and any optional gate with fake clients. Use observed or
explicitly recorded usage/rate evidence; absent usage/cost is unavailable, not zero.
Do not reuse old one-off model rates as current pricing without provenance.

## Validation and PR handoff

Test case isolation, bounded failure handling, stable report rendering, expectation
freeze/tamper handling, missing labels, metric denominators and all three result
layers. Test independent auditing against actual synthetic bytes, including invalid
hashes/versions/cells and legitimate unsupported reference kinds. Confirm no gold
reaches runtime inputs and no default execution can call a paid provider or RPC.

Run the new focused tests, existing aggregate/dataset/API regressions, the unchanged
brokerage acceptance smoke, full backend pytest, Ruff lint/format for backend and
all task-owned tooling, `git diff --check`, and generated-contract freshness with
Node 24. Public DTO/frontend changes are outside scope. Record existing compiler
failures accurately; never weaken assertions or restore xfail markers to hide a fix
or regression. Re-run actual commands against the final branch, not historical output.

Update the workstream handoff with exact base/reused SHAs, commands, example outputs,
scoring definitions, limitations and remaining Rehan/Jeff dependencies. Update the
proposed PR text at `docs/pr-drafts/10-aggregate-evaluation.md` to describe what was
actually implemented and tested. No fabricated passing results or live evidence.

Commit task-owned changes locally and return the SHA, validation and report paths.
No push/main merge/PR publication, runtime redesign, payment recovery, frontend
changes, private state access, real RPC, broadcasts, paid calls or deployment.
