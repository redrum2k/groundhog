# Current scope/dispatch remediation — October 24

Fresh review of `9bff90c` found one further P1: numeric qualifiers were removed
from affirmative consent. Test-first `2146cde` reproduces it in model and offline
restart paths; fix `3f90ad5` retains qualifiers. 332 focused tests pass; full backend
is 970 pass / the exact same 16 Windows failures. See the current report.
No paid calls or frontend changes.
Subsequent integration `e41dd03` imports Lucas's main `34aa770` (PR #21) intact;
frontend 120 tests, generated contracts, TypeScript and build pass again. The
backend still exactly matches tested `3f90ad5`.

See [current report](../../BROKER_RECOVERY_REMEDIATION.md): the two follow-up
findings on `e60aa6f` have test-first reproductions and fixes at `ba79817`.
44 focused tests pass; `e45ddde` imports Lucas's main `3d69b92` unchanged, with
120 frontend tests, generated contracts, TypeScript and build passing.
The shared scope-fulfillment helper preserves acceptance/payment gates; the
transactional outbox recovers only undispatched work without retrying uncertain
attempts. Full-suite results and exact baseline failures are in the report.
Earlier [three P1 fixes](../../GREPTILE_P1_REMEDIATION.md) remain intact.
PR #12 still needs fresh independent review and an explicit resolution of main's
automatic production-deployment consequence before merge. No paid calls, payment
execution changes or shared procedure activation. Lucas owns the imported
inspector's UNKNOWN-as-failure presentation caveat, documented in the report.

# Earlier paid qualification and integration — October 24

PR #12 now contains the completed R3/R4 and conversational-intake fixes, plus
actual guarded Claude Opus 5.5 qualification. See
[AGGREGATE_MODEL_QUALIFICATION](../../AGGREGATE_MODEL_QUALIFICATION.md) for frozen
versions, retained failures, fresh follow-up cases, usage and test evidence.
The feature branch incorporates main `b177d53`, preserving Lucas's frontend and
Nikita's payment work. Model flags remain OFF by default; no main merge or
deployment is authorized. The historical assignments below do not restart work.

# Aggregate evaluation tooling handoff — Prompt 10

The user/Jeff delegation assigns Nikita the general offline runner, requirement
scoring, independent audit integration and reports. This does not transfer compiler
R3/R4, conversational interpretation, explicit scope consent, Claude wiring,
evidence enforcement or developer regressions. No runtime files change in this PR.
The pure present-cell audit is extracted with exact attribution and compatibility
tests; no feature-branch merge, private ledger access or historical regrading occurs.
See [workstream 10](../workstreams/10-aggregate-evaluation.md). Its D05/D06 development
expectations flag `R-ARTIFACT=PASS` in source-blocked orders without output bytes;
money correctly remains held and evidence is requested. This is an owner review
dependency, not permission for the evaluator to change your semantics.

# Earlier integration status — October 24

[Reviewed integration](../reviews/frontend-payment-integration.md) includes payment
`593e02f` and published main `04756e1`, validated at `4a24c9f`. R3/R4 still fail
under their original strict markers on this combined baseline (720 passes, two
expected failures). They were neither removed nor reinstated by integration.

Your published `origin/feature/aggregate-intake-integration-20261024` is available
initially at `e774495192f903d0c1191590cf13cfc4a9439977`, including `d2b6ba1`,
`5946378` and `ef8c99a`. The final fetch advanced it to
`849e98a791551546ee29fda67392041301bf1a43`, including newly published intake work
at `706f41e`. These commits remain a separate review/integration item. The reported `0983c1b`
object is still unavailable. This integration does not qualify the newly published
conversational-intake amendment or rewrite your existing branch. Prompt 10's audit
reuse candidate is `tools/audit_primary_evidence.py` at `ef8c99a` (same blob at
`e774495` and `849e98a`); inspect and attribute it separately, without running its private-path
entry point or merging compiler/runtime changes just to obtain tooling.

The review and job assignments below are preserved as historical checkpoints.

# Review remediation — Jeff's remaining release blockers

## Primary semantic follow-up delivered locally

Feature branch `feature/broker-dispute-assessment-20261024`, based on current main
`62fe035`. R3/R4 fixes are in `de53450`; primary integration in `d2b6ba1`; final
equivalent-proof implementation in `5946378`. See [PRIMARY_RESULTS](../../PRIMARY_RESULTS.md)
for exact tests, real calls, retained negative cases and Windows full-suite failures;
[PRIMARY_HANDOFF](../../PRIMARY_HANDOFF.md) contains Lucas's mapping instructions.
The primary feature remains OFF. No main merge, deployment or new push occurred.
Final tested code: `ef8c99afb9cf5f3b6928f505242f2d622fce2c3e`. All 19 compiler and
38 primary semantic tests pass; full suite 747 pass / 13 disclosed failures in
unchanged platform/settlement tests. Frontend 104 tests, typecheck, generated checks
and build pass. Later reporting commits do not change that tested code.
Final upstream fetch observed Lucas's frontend-only PR #6 on main `5a68ea1`.
It was not merged into this tested worktree; preserve that newer UI during Git
integration. Do not copy the archive's `62fe035`-based frontend over current main.

The original strict R3/R4 tests passed as XPASS before their markers were removed.
Added negation/paraphrase/correction/geography/contradiction checks preserve original
history and contractual clocks. Nikita's completed R1/R2/R5/R6/R7 work is retained.
Actual primary verdict/evidence examples: [JSON](primary-semantic-events.example.json).

## Prior remediation instructions (preserved)
## Historical job after the payment-lease review — October 24

Continue R3/R4 on your existing compiler branch/worktree; do not recreate or reset
it. The full 09 backend suite still reports the two strict expected failures. No
new compiler implementation was present in the fetched remote main (`63ac21f`).
Your acceptance cases and ownership below remain unchanged.

Nikita's payment commit `9622fe0` is held for
[09b's two boundary fixes](../codex-prompts/09b-payment-attempt-boundaries.md), per
the [09 review](../reviews/09-results-review.md). You do not need that branch to
fix compiler semantics. Avoid payment executor/journal/HTTP/lab files; preserve
the current 08b complaint and artifact safety behavior. Return your exact tested
commit, commands and results; remove each strict expected-failure marker only when
its original regression and related semantic cases pass. Integrate the two tasks
only after independent review, preserving newer remote main and Lucas's UI work.

## Start from the shared remediation branch

The combined 06/07 work, prompt 08's reviewed implementation (`692f500`) and
08b's polling/complaint fix (`845b7c5`) are merged into `main`. The integration
also preserves Lucas's newer broker compatibility demo and visual updates.
From your clone, create a separate compiler worktree from current `main`:

```sh
git fetch origin
git worktree add -b codex/compiler-review-fixes ../order-to-cash-compiler-review origin/main
cd ../order-to-cash-compiler-review
```

Own `backend/app/agents/dataset.py`, the R3/R4 regressions and related semantic
tests. Nikita's [08b](../codex-prompts/08b-polling-recovery.md) is complete; its
complaint-target/runtime API fix does not change compiler semantics. Keep compiler
commits on your feature branch and update this handoff with your exact validation
evidence. Return an exact tested commit for integration. The
[main integration record](../reviews/main-integration.md) covers the combined
validation and the artifact-publication race fixed during integration.

If you already branched from `origin/codex/review-remediation`, keep that work;
its baseline is included in `main`. Do not reset or recreate an existing branch.

See the [08 results review](../reviews/08-results-review.md) for the original R7
artifact-failure reproduction, now addressed by 08b, and the distinction between
mock startup and release/live payment readiness.

## Compiler blockers and evidence seam

See [workstream 08](../workstreams/08-review-remediation.md). Compiler semantics
in `app/agents/dataset.py` remain yours; no semantic patch was integrated or
claimed. Local history has no later reviewed compiler commit beyond `1956f18`.
The new `tests/dataset/test_compiler_review_blockers.py` contains strict expected
failures for the exact R3/R4 reproductions. Supply an exact tested commit for
integration and remove each expected-failure marker only when its patch passes.

- R3: `SF adults 25-34, gym membership or fitness app users. Do not include yoga.`
  currently compiles `gym_app_or_yoga`. Expect gym/app exclusion or a bounded
  clarification, never inferred expansion. Cover affirmative inclusion, exclusion,
  negation and contradictory answers.
- R4: start with `SF adults 18-24, gym membership or fitness app users, grouped by ZIP.`
  Answer its cohort question: `Yes, change to San Francisco adults 25-34 grouped by ZIP,
  gym membership or fitness app use.` It currently repeats the rejected cohort.
  Expect ready 25–34 terms from the explicit question-bound correction, retaining
  original prompt/answer history and deadline. Also cover corrected geography and
  unresolved contradictions without extra question/deadline budget.

R2 transport now persists typed request/case/actor/original binding/time/text/refs
in `order.evidence_answers`. `orders/dataset_evidence.answer_references` re-resolves
up to sixteen current-case frozen references; the injected assessor receives
actual passages, including `yoga_category=Wellness`, after restart. Only a narrow
passage-assembly call changed in `investigation/dataset.py`. Interpretation stays
with your assessor. Customer text is testimony, not source authority or purchase
consent; a cited answer never mutates accepted editions/terms. Preserve UNKNOWN
when the references cannot establish the claim. `test_review_answers.py` defines
the tested seam, including source repair, abstention, rollback and replay.

R1 now strictly allowlists DatasetSource, DatasetManifest, CoverageSource and
AuthoritySource at the public boundary. Schema evolution must explicitly extend
that allowlist; arbitrary JSON remains private, even when its discriminator is
absent. R6 sends validated requirement/field/ZIP/column/intent. A 94110 coverage
complaint reaches coverage, not category; expand substantive assessment behavior
only with cited tests. No messages were sent by this task; this is the local handoff.

# Aggregate brokerage migration handoff

Current primary product: `aggregate-brokerage-v1`; historical profiles retain their
accepted policy. Start with [workstream 06](../workstreams/06-data-broker.md): complete
migration map, route/examples, demo commands, mock signing boundary and validation.

`contracts/dataset.py` reuses your Frozen/SourcePin/TermProvenance semantics and adds
strict integer/null rows. `datasets.py` independently checks actual source/CSV/JSON,
including a separate frozen ZIP registry. `investigation/dataset.py` adapts your
bounded injectable SemanticAssessor; `EvidencePassage.citation` also accepts a
DatasetReference. New findings are still Assessment/Verification with current
bindings. Source deficiency is distinct from established provider-output fault.
Catalog PDF code and your broker/improvement profile remain intact for compatibility;
no improvement activation changes a new run. Dataset answer/offer routes are explicit
versions, not silent reinterpretations of PDF upload or legacy arbitrary-price offers.

## Historical catalog handoff

# Jeff — evidence semantics, unchanged ownership

Own requirement compiler/clarification, corpus generation/extraction/normalization/provenance,
PDF content/coordinates, independent verification, amendment classification, investigation,
model/prompt strategy and quality evaluation. No payment plumbing or wallet work is required.
Nikita owns gateway transport/permissions/budgets and runtime application of your findings.

Inputs and outputs remain the existing typed contexts in `app/contracts/catalog.py`. Return
current-bound PASS/FAIL/UNKNOWN/CONFLICT assessments, explicit dependencies/material blockers,
cited questions and recommendations. Unknown authenticity is UNKNOWN, not fraud. A score,
recommendation or passing report never authorizes a transfer. Do not rewrite the accepted
mandatory requirement registry or turn missing evidence into consent.

The [fixed current Verification example](verification-report.example.json) is a deliberately
small schema-valid blocked report for an unreadable product price, with no fabricated citation.
It demonstrates shape/materiality, not a complete fulfillable report or independent evaluation.
Use the repaired offline journey for a complete real-PDF-derived report and citation set.
The runtime independently requires all allowlisted global/source/PDF checks; omitting them
from an example cannot create settlement authority.

Settlement consumes current snapshot/evidence/delivery binding, every mandatory check passing,
no material blocker, source authority/consent clear, no unresolved dispute, current customer
acceptance or undisputed 60-second review expiry, exact funded amount, unexpired authorization
and no previous capture/competing terminal action. Recheck before submission. A substantive
change still requires a new offer/acceptance; parent void must confirm before child funding.

The evidence policy, 60-second review/dispute clocks, two questions, source-repair consent,
one durable free correction and no unsupported-complaint fee stay unchanged. New payment
terms live in schema-4 snapshots under `catalog-payments-v1`; no historical financial rewrite.
Lucas consumes your citations and versioned findings; Rehan keeps independent labels outside
runtime. No runtime model gets evaluator answers or wallet/storage/general-web authority.
