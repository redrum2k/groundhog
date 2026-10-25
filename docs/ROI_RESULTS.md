# Groundhog ROI Lab — observed results and conditional economics

## Strongest supported headline

> On the same 60-scenario controlled workload, approved learning eliminated 88 repeated source-owner questions versus the no-learning ablation, while all three arms correctly handled all 60 scenarios. A competent operator with retained notes also avoided repeated owner questions. Under the stated illustrative cost assumptions, capacity break-even requires 39 seconds saved per scenario; actual human-minute savings remain unmeasured.

Do **not** replace this with “X% less operator attention.” The 60 scenarios comprise 52 fulfilled scenarios, six pre-acceptance holds and two funded holds in **every** arm. Holds are correct safe dispositions, not fulfilled orders or collected revenue. Each arm created 61 actual order records across the 60 scheduled scenarios because expansions have separate parents/children; seven additional teaching orders are recorded and charged separately.

## Open the deliverables

- GitHub-ready [standalone dashboard](evidence/roi-dashboard.html): download the raw HTML and open locally. It contains the original per-case counts and interactive assumptions, but intentionally omits private trace links and process identities.
- Final read-only dashboard: [report-release.html](../.local/roi-attempt-001/report-release.html). It works directly from a local file; no server or paid calls are needed.
- [Desktop screenshot](../.local/roi-attempt-001/report-release-desktop-top.png) and [mobile screenshot](../.local/roi-attempt-001/report-release-mobile-top.png).
- [Method, fairness, economics and literature](ROI_METHOD.md).
- [Sanitized evidence/assumption index](evidence/roi-lab-20261025.json).
- [Frozen-suite index](../evals/roi/frozen_suite.json), with all 67 per-arm scheduled/setup input hashes. It indexes the original capsule, not a newly selected subset.
- [Original case results](../.local/roi-attempt-001/results.json), [work ledger](../.local/roi-attempt-001/work-ledger.json), [quality audit](../.local/roi-attempt-001/quality.json) and [authority/approval audit](../.local/roi-attempt-001/lineage-audit.json).
- [Timing-pilot instructions](../.local/roi-attempt-001/pilot/README.md), [12 paired assignments](../.local/roi-attempt-001/pilot/assignments.json), [blank timing form](../.local/roi-attempt-001/pilot/timing-form.json). There are 24 task packets and zero completed human observations.

Raw databases, generated rows and screenshots remain in this worktree's private `.local` directory, not Git. The committed runner regenerates them in a new isolated directory. Local links require this preserved artifact directory; they are not public downloads.

## Newly executed results

| Measure | Operator + persistent notes | No new learning | Approved learning |
| --- | ---: | ---: | ---: |
| Correctly handled / scheduled | 60 / 60 | 60 / 60 | 60 / 60 |
| Fulfilled scenarios | 52 | 52 | 52 |
| Pre-acceptance / funded holds | 6 / 2 | 6 / 2 | 6 / 2 |
| Actual recurring order records | 61 | 61 | 61 |
| Recurring provider work episodes | 212 | 240 | 152 |
| Teaching/setup provider episodes | 35 | 28 | 49 |
| Total provider episodes, including setup | 247 | 268 | 201 |
| Recurring source-owner episodes | 0 | 88 | 0 |
| Teaching source-owner episodes | 14 | 14 | 14 |
| Recurring buyer episodes | 191 | 191 | 191 |
| Teaching scenarios, correctly handled | 7 / 7 | 7 / 7 | 7 / 7 |
| Quality failures / known safety issues | 0 / 0 | 0 / 0 | 0 / 0 |
| Observed provider inference cost | $0, offline | $0, offline | $0, offline |
| Measured human attention / metered compute cost | unavailable | unavailable | unavailable |

Including setup, the candidate has **46 fewer scripted provider episodes** than the competent operator proxy and **67 fewer** than the learning ablation. These are counts under a declared workflow protocol, not observed employee effort or a lower bound on what a good operator can achieve. Operators may batch or automate their ordinary tools; their real attention could be much lower than the illustrative 45-second glossary application assumption.

The 20 eligible repeat-source cases require two new source-owner resolutions each in the no-learning arm, and zero in both the notes baseline and approved-learning arm. Across all eligible recurring cases, the learner reuses its version on **44 fresh cases**. An additional independent audit verified **88 component bindings** against exact current authority pins, publisher/schema/scope, saved qualification and controller approval, and distinct training/current source hashes. Six invalid/changed-source cases stop without acceptance or booking.

All 10 current-documentation cases succeed in every arm without source-owner questions. The eight output defects are deliberately injected before publication and corrected by the existing verification/correction workflow; none is described as an LLM-resolved customer dispute. The identical yoga scope question changes answer only after a separate expanded agreement, consent and funding. Three arms each cross a genuine process boundary after repeat case 10 while preserving their own store and knowledge.

No model accuracy advantage is claimed. All arms use the same offline compiler/assessor, independent artifact checks and financial gates. No evaluator answers enter runtime inputs; the literal-byte scorer runs afterward. No business case was rerun or discarded for an unfavorable outcome.

## Revisions, capsule and runtime

- Baseline main, inspected and pinned: `956d4e470b390bacc7564d31dcd160d05b4b0222`.
- Branch/worktree: `feature/roi-lab-20261024`, `C:\Users\sajee\order-to-cash-roi-20261024`.
- **Executed benchmark core:** `f314b6dc5d74568f40280bb235a587590f5b384e`.
- **Presentation, pilot, supplemental audit and regression code:** `77c32f0b4882751d856416e5da13ba7f56f535ec`. The executed plan, driver implementation, scorer, ledger and economics core are byte-identical to their versions in `f314b6d`; the CLI adds only report/pilot/audit entry points.
- Capsule SHA-256: `313ceeb238083e3d36a0ca69da109b223d8db903a3e11fcb4498a46e6cb19f72`.
- Public input digest: `104b91bf2b941f56b461b0860abcf3b0215fd39d36c3a4530516703000d658a1`; separate evaluator digest: `7fa5a9df71dc6842cde745feda3f7e284fd0072d990858a6c1976dbdc124fc19`.
- LOCAL attempt 1: 27 finite child processes, all joined with exit 0; 201 case executions (67 × three arms); approximately **341 seconds machine elapsed**. This is not human attention or a throughput benchmark.
- No persistent service or remote resource allocated, no paid budget touched, no broadcast, no existing demo modified. All output directories and original report previews are retained.

The inherited real-Claude trials in `HYPHENATE_FINAL_QUALIFICATION.md` are earlier evidence, not new model/timing observations. Their costs must not be relabeled as this run's recurring bill. The current offline onboarding/qualification uses zero provider calls; production startup/qualification expense remains covered by explicit setup assumptions, not secretly omitted or claimed measured.

## Conditional economics — not measured savings

Default provider scenario: 1,000 scheduled commercial scenarios/month for 12 months; $40/hour loaded wage; $0.20 incremental variable cost/scenario; $150/month incremental fixed support/hosting; $1,000 total setup allowance **including** teaching/qualification/approval labor. The components and every assumed event duration are exposed in the dashboard and `assumptions.json`. Source-owner and buyer minutes are separate. Default provider roles are operator/controller; source-owner payroll classification remains an assumption, not a fact about all brokers.

These inputs produce **$5,200 incremental cost**, **39 seconds capacity break-even**, and **78 seconds positive cash break-even at 50% realization** when there are no negative category-level labor impacts. At 0% realization, there is no positive cash break-even. Negative labor impacts are always charged at 100%.

Under the illustrative **medium-repeat mix** (40% repeats, 20% current documentation, 10% each defects, objections, scope and exceptions):

| Comparison | Assumed net seconds released / scenario | Projected annual capacity | Net capacity value after costs | Conditional cash at 50% |
| --- | ---: | ---: | ---: | ---: |
| Versus operator + notes | 45.0 | 150 hours | $800 | **−$2,200** |
| Versus no new learning | 43.5 | 145 hours | $600 | **−$2,300** |

These are calculator outputs from **assumed** episode seconds, not experiment-measured labor savings. The reported cash result remains negative rather than being hidden behind a positive capacity number. At 100% realization the cash values equal net capacity value; at 0%, costs and any negative labor effects remain. Sliders expose low/medium/high repeat profiles, source-change frequency, event times, volume, wages, incremental inference/compute/storage/payment/support costs, ongoing governance and realization. Original outcomes never change.

The finite replay does not amortize the illustrative $1,000 setup allowance. Projected break-even crossing depends on the chosen volume, net per-scenario benefit and recurring costs. When unit benefit cannot cover variable costs the dashboard explicitly reports **no volume break-even**. No mock gross transaction value, returned funds or hypothetical prevented fraud is included.

## Verification and commands

Executed core:

```powershell
uv sync --locked --project backend
uv run --locked --directory backend python ../tools/roi_benchmark.py freeze --output ../.local/roi-attempt-001
uv run --locked --directory backend python ../tools/roi_benchmark.py run --output ../.local/roi-attempt-001
```

Use a **new** output name for a new execution; existing evidence refuses overwrite. A fresh run pins the checked-out commit. The checked-in frozen-suite index reproduces the original case input hashes.

Supplemental audit, report and pilot (supported CLI at `77c32f0`; the original supplemental audit invoked the same function directly before the CLI shortcut existed):

```powershell
uv run --locked --directory backend python ../tools/roi_benchmark.py audit-lineage --output ../.local/roi-attempt-001
uv run --locked --directory backend python ../tools/roi_benchmark.py pilot --output ../.local/roi-attempt-001
uv run --locked --directory backend python ../tools/roi_benchmark.py report --output ../.local/roi-attempt-001 --report-name report-release.html
npm --prefix frontend ci --no-audit --no-fund
node evals/roi/browser_check.cjs .local/roi-attempt-001 report-release.html
```

Do not rerun these export commands into an already populated output; use a new report filename for a presentation iteration. Data/assumption files must still match exactly. Pilot export and audit output likewise preserve existing files.

Checks performed:

- **104 tests passed in 81.70 seconds:** ROI accounting/boundaries/execution/pilot, all existing source-learning tests, exact money narration, scope inquiries, payment justification and request-bound model audit regressions. XML `.local/roi-relevant-tests.xml`, SHA-256 `4f871daf1061ea459f06177e4d1ee2d6a406b31458d804b26f38a1baa9f3240f`.
- One subsequent frozen-index regression added; the **12-test accounting file passes** including that new check. There are 105 distinct checked tests across these runs, not a new full-repository run.
- Existing acceptance passes A/B/C/D, answered scope question and restart: `.local/roi-existing-acceptance/broker-c6l210la/report.json`. Explicit offline/mock environment; no paid calls or RPC.
- Read-only browser PASS at 1440×1000 and 390×844: **18 Python/JavaScript calculator parity comparisons**, zero network requests, zero browser errors, all 60 cases/eight holds visible, trace files exist and original evidence hashes unchanged. Invalid economic inputs clear projections; zero realization and negative unit economics are tested. Desktop/mobile screenshots were visually inspected.
- Additional regression checks cover exact paired inputs, no expected outcomes in public case inputs, duplicate episode rejection, absent human timings, missing cases retained in denominators, current-documentation baseline completion, persistent operator notes, unapproved ablation, wrong atomic amount rejection, tampered learned-authority rejection, offline budget/network tripwires and no dashboard mutation interface.
- Ruff lint and format checks pass on the new tooling/tests; `git diff --check` passes.
- Initial browser QA found mobile grid overflow; a minimal `min-width:0` fix resolved it. The original preview/screenshots remain, and the browser regression checks page width. No experiment inputs/outcomes were changed or rerun for this presentation fix.

Exact relevant-test command:

```powershell
uv run --locked --directory backend pytest tests/roi tests/source_learning tests/dataset/test_money_narration.py tests/dataset/test_scope_inquiries.py tests/dataset/test_payment_justification.py tests/dataset/test_model_journey_audit.py -o addopts='' --tb=short --junitxml=../.local/roi-relevant-tests.xml
uv run --locked --directory backend pytest tests/roi/test_accounting.py -o addopts='' --tb=short
uv run --locked --directory backend ruff check ../evals/roi ../tools/roi_benchmark.py tests/roi
uv run --locked --directory backend ruff format --check ../evals/roi ../tools/roi_benchmark.py tests/roi
```

The historical full repository run had 16 disclosed Windows baseline failures. That full suite was **not** rerun for this additive lab; no unrelated tests were rewritten and no fully green repository claim is made.

## Completion audit and remaining unknowns

The brief's three arms, six workload categories, complete no-learning resolution path, persistent-notes baseline, distinct fresh rows/hashes, restart, source invalidation, changed-context/same-words control, explicit consent, independent byte/financial scoring, failure-inclusive denominators, deduplicated provenance ledger, setup/ongoing/shifted work, normalized economics, negative-impact accounting, no-break-even conditions, sensitivity, traceable read-only dashboard and 12 paired timing packets have concrete implementation and evidence above.

No humans participated; active-minute savings, real operator mistakes/time distribution, production inference/compute/storage/support/payment expense, empirical prevalence, cash realization, real deployment reliability and broader business impact remain unmeasured. The pilot export is the explicit permitted fallback, not a claim that the pilot was run. Literature supplies mechanisms only, not calibration or sponsor promises. Zero failures in this finite synthetic suite does not prove production reliability.

The original experiment was delivered as focused **local commits only**. The subsequent user-authorized GitHub publication is recorded below. Production application behavior, live authorization, existing budgets, accepted agreements, prior qualification evidence and sealed evaluation keys are unchanged by the ROI changes.

## GitHub integration — October 25, 2026

The user subsequently requested publication in the main repository and a fresh Greptile check. Current upstream `0407a71` was merged into this feature branch at `57f9191`, preserving the team's UI, source-visit and mock-payment changes. The only merge conflict was README wording; both the ROI section and Summit Fitness naming were retained. There are no ROI changes to production backend/frontend code relative to that main revision.

The public dashboard is a sanitized **export of the original run**, not a rerun or a claim that the 60-case workload executed at this integration revision. The original results, hashes, capsules and all private artifacts remain untouched. Its SHA-256 is `dabe93d7c3b9bbd6a9c0728aa8bb2352f7a6a3987155d86d221f17bdd7550117`. Git preserves its LF bytes. Private evidence links lead to an explicit disclosure instead of broken local paths; the repository contains the sanitized evidence index and reproduction tooling, not raw databases, evaluator artifacts, credentials or generated datasets.

Fresh compatibility checks on the integrated branch:

- **115 tests passed** in 66.81 seconds: the prior relevant set plus upstream's ten mock-payment-pacing tests. XML `.local/roi-main-integration-tests.xml`, SHA-256 `4edb0e8840b49fae7ccbc66627ad7358cb55db98ec921f05de1a4031bb08fd87`.
- Additional public-export regression checks preserve failed-case denominators, reject overwriting, strip private links/metadata and compare the committed snapshot against the frozen evidence and current dashboard script.
- Public dashboard browser checks passed desktop/mobile, 18 calculator comparisons, 60 visible cases/eight holds, valid internal links, no private trace metadata, no network calls/browser errors and no mutation of the original evidence.
- Ruff and whitespace checks pass. The full repository suite and live-model experiment were not rerun; earlier live-model qualification remains separate inherited evidence.

The earlier PR #53 received Greptile **5/5** at `82dd93a`; that rating does **not** cover this ROI change. Request a fresh review of the ROI PR's exact head. This publication does not authorize deployment or production activation.

Public-export reproduction from the preserved artifact directory (use a fresh filename):

```powershell
uv run --locked --directory backend python ../tools/roi_benchmark.py report --output ../.local/roi-attempt-001 --report-name report-github.html --public-snapshot
node evals/roi/browser_check.cjs .local/roi-attempt-001 report-github.html --public-snapshot
```
