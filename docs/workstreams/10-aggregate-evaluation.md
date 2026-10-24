# 10 — Aggregate evaluation runner and readable results

Owner: Nikita, under the user/Jeff delegation of general aggregate evaluation
infrastructure. Rehan owns independent expectations, rationale/review and splits;
Jeff retains compiler R3/R4, interpretation, scope consent, Claude wiring, evidence
enforcement and developer regressions. Lucas retains the frontend. The narrow
exception is recorded in `evals/AGENTS.md`, responsibilities and all three handoffs.

## Starting point and inspected provenance

Existing worktree: `../order-to-cash-aggregate-evaluation`, branch
`codex/aggregate-evaluation`. Starting status was clean; no reset, stash, competing
checkout or teammate edit was needed. Exact starting HEAD, main and cached origin/main:
**`331a614b3fa484200ce06b4eca58822580c5f696`**. Inspected status, branch/history and all
worktrees before editing. The reviewed integration is documented in
`docs/reviews/frontend-payment-integration.md`, implementation merge
`4a24c9f91962c2924770614e38b6e6edee905a94`, with final documentation at `331a614`.
Root/nested instructions, HACK, PAYMENT_SPIKE, responsibilities, Jeff/Nikita/Rehan
handoffs, workstream 06, acceptance smoke and legacy eval layout were read.

Fetched only `origin/feature/aggregate-intake-integration-20261024` for inspection;
observed tip **`849e98a791551546ee29fda67392041301bf1a43`**. Inspected the exact
published `primary_followup_eval.py`, `primary_certificate_probe.py`,
`PRIMARY_RESULTS.md`, `PRIMARY_HANDOFF.md` and `tools/audit_primary_evidence.py` at
the prompt's **`e774495192f903d0c1191590cf13cfc4a9439977`**. No historical result was
rerun, regraded or copied as new evidence. The local `0983c1b` is not an input.
The newly published `706f41e` conversational amendment remains unreviewed here.

Only the pure present-cell algorithm was extracted from
**`ef8c99afb9cf5f3b6928f505242f2d622fce2c3e`**, file `tools/audit_primary_evidence.py`,
Git blob **`51acbf86a90ff8f1cc3e7397db3fd7776ad2fc68`**. Tree inspection confirmed the
same blob at `e774495` and fetched `849e98a`. `evals/aggregate/audit.py` attributes the
source and contains the single adapted cell auditor, with focused compatibility
vectors. Its input is explicit artifact metadata/bytes and attempt versions. The
Windows private ledger path, entry point, case/model assumptions and rates were not
executed or inherited. No merge/cherry-pick of the runtime branch was performed.

## Delivered behavior

`tools/aggregate_eval.py` is a thin noninteractive entry point. `evals/aggregate/`
contains strict case/expectation/scoring models, six development recipes, private
subprocess execution, independent byte audits, normalized scoring and Markdown
rendering. See its [format/CLI/scoring guide](../../evals/aggregate/README.md).
No production import, public DTO, frontend, gateway, compiler, payment or lifecycle
file changes. `tools/brokerage_acceptance.py` and `evals/run_v5.py` remain unchanged.
The evaluator reuses the smoke's command/acceptance/clock helpers and service flow.

Each case receives a fresh private DB/artifact root, deterministic clock and seed,
explicit fixture compiler, OfflineAssessor and mock payment configuration. Normal
quote acceptance, explicit simulated authorization, confirmed mock funding and
durable fulfillment remain necessary. Source defects are registered before acceptance;
only the correction recipe changes producer bytes at its test-owned seam. No finding
is injected. The parent imposes a hard subprocess deadline and the child caps steps.
Operational errors/timeouts preserve evidence and do not stop unrelated cases.
No paid lane exists; stripped environment, explicit clients and provider/socket
guards prevent ambient opt-ins from enabling network work.

Every run freezes and hashes cases, expectations, scoring configuration, code revision,
dirty status and implementation files. Separate input hashes and the pinned total
plan hash are checked before cases and after execution. Runs are additive. Private
evidence retains exact accepted terms, source pins, original bytes, runtime inputs,
pre-commit attempts, checkpoint orders/bindings, bookings and paginated events.
Correction's rejected attempt is labeled historical after current checks are invalidated;
it is not erased or represented as current settlement authority.

The auditor reopens hashes/versions and checks present cells, nulls, meaningful missing
top-level keys and absent rows supported by the frozen coverage registry. Unsupported
kinds are unscored. CSV/manifest/source comparison includes strict public-manifest
shape so an extra private suppressed value cannot hitchhike into a report download.
Unsafe original bytes stay private. Report citations omit values; parser errors are
value-free; URLs/credentials are redacted. No runtime resolver serves as audit proof.

Results retain distinct raw-model absence/deterministic provenance, effective findings
and enforcement, expectation comparisons, and financial state/bookings. Structural
citations are separate from substantive review. Complaint PASS supports a complaint;
it does not mean the delivery passes. Missing usage/cost is null/N/A. No rate, fee,
receipt, live transaction or financial disposition is invented.

## Scoring and observed development outcomes

Unit: accepted requirement × scheduled checkpoint. Six cases schedule 10 checkpoints
and **80 correlated requirement observations**, not 80 independent samples. All eight
accepted requirement IDs are mandatory at every checkpoint. Inputs reject duplicates,
missing labels and mismatched IDs/splits. Separate development/held-out and
engineering/Rehan-reviewed groups prevent pooled accuracy claims. Zero denominator
is N/A; missing observations/audits/labels remain in scheduled totals, never matches.

Agreement counts matching effective labels with valid citations over all labeled
scheduled observations. False PASS uses non-PASS labels as denominator; missed
contradiction uses CONFLICT labels; appropriate UNKNOWN/CONFLICT uses each matching
label population; excessive abstention uses determinate PASS/FAIL labels. Raw-model
errors and errors caught by enforcement are unavailable on this baseline. State,
artifact-result, complaint and booking-count comparisons also affect case outcomes.

| Case | Development expectation and observed outcome |
| --- | --- |
| D01 conforming | Valid CSV/JSON, then review-expiry capture; exactly one actual $120 mock booking, null transaction ID |
| D02 output fault | Missing ZIP independently detected, unpublished failed bytes/findings retained, one correction, valid final delivery; held funds |
| D03 unsupported factual complaint | Deterministic complaint FAIL/refutation, delivery requirements PASS; held funds, no fee or booking |
| D04 additional scope | Parent retained, separately accepted $60 Oakland child with its own explicit funding and delivery |
| D05 insufficient publisher evidence | Provenance UNKNOWN and evidence requested, held funds; **R-ARTIFACT PASS vs engineering UNKNOWN** without delivered bytes |
| D06 conflicting edition | Provenance CONFLICT and evidence requested, held funds; **R-ARTIFACT PASS vs engineering UNKNOWN** without delivered bytes |

The two output-agreement mismatches are recorded owner dependencies, not semantic
patches. They may need stage-specific interpretation by Jeff and independent review
by Rehan. No expectation was derived from a candidate answer. The engineering rule
requires output agreement to remain unestablished before any output exists. Runtime
correctly blocks work/settlement in those source-deficient cases.

Observed diagnostic: 6/6 operationally completed; four matching cases, two mismatching
cases, zero incomplete; 78/80 requirement agreement; false PASS 2/6, missed contradiction
0/1, appropriate UNKNOWN 1/3, appropriate CONFLICT 1/1, excessive abstention 0/76.
These are development diagnostics only. Rehan-reviewed and held-out denominators are
zero; independent qualification and aggregate accuracy are **not claimed**. Full suite
exit is intentionally **1**, after writing results. Correct blocking/correction is a
successful evaluation case. Missing labels/audits or operational failure instead exit
3; invalid inputs exit 2; complete matching diagnostics exit 0.

## Validation and reproducible commands

The final command results and committed implementation identity are recorded below
after verification. All commands use synthetic temporary state; no private .env,
private ledger, live RPC, paid model, wallet, broadcast or deployment is involved.

```sh
uv sync --locked --project backend
backend/.venv/bin/python tools/aggregate_eval.py validate
backend/.venv/bin/python tools/aggregate_eval.py run --output /private/tmp/aggregate-evaluation-final
backend/.venv/bin/python tools/brokerage_acceptance.py --output /private/tmp/aggregate-acceptance-final
# backend cwd, locked venv installed by uv sync:
.venv/bin/python -m pytest tests/evals --tb=short --show-capture=no
.venv/bin/python -m pytest tests/dataset tests/api tests/broker --tb=short --show-capture=no
ENABLE_PAID_MODELS=false ENABLE_TESTNET_BROADCAST=false PAYMENT_ADAPTER=mock \
  .venv/bin/python -m pytest --tb=short --show-capture=no
.venv/bin/ruff check . ../tools ../evals/aggregate
.venv/bin/ruff format --check . ../tools ../evals/aggregate
# frontend cwd, Node 24.14.1 on PATH:
npm ci
npm run generate:check
# root:
git diff --check
```

Focused tests cover actual service boundaries, isolation, pre-funding absence,
correction history, independent acceptance of child scope, audit compatibility,
hash/version/cell failures, suppressed-null/private values, unsupported references,
false passing observations, strict labels, freeze tampering, denominator accounting,
stable rendering, no gold in serialized runtime inputs, no runtime evaluator import,
real child timeout/continuation, step limit and fake provider/network guards.

Remaining dependencies: Rehan's independently reviewed expectations/split decisions;
Jeff's source-stage output-agreement interpretation and separately reviewed compiler/
Claude feature integration. No UI/model quality or held-out qualification is implied.
Work remains local: no push, main merge or PR publication.
