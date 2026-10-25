# 11 — Implement the yoga objection backend pitch demonstration

Implement the backend changes described here; do not stop at a plan. The target
is a reproducible aggregate-brokerage demonstration: intake → meaningful
clarification → accepted agreement → explicitly simulated funding → real CSV/JSON
and independent verification → nuanced yoga taxonomy complaint → cited resolution
presented to the customer → explicit customer acceptance → eligible mock capture.

Updated direction: Path B. The thesis is minimizing staff intervention through
explicit agreements and evidence-based dispute resolution. Human escalation remains
the fallback for genuinely unresolved cases, not the planned ending. Customer
clarification and acceptance still occur; do not claim zero human involvement.

## Base, instructions and ownership

Start in a separate worktree branched from the working `codex/local-claude-live`
checkout. Its observed base is `800c985f520324981a75b596785c5f4aa3ef0bb6`, including
main `3d69b92` and Jeff's aggregate intake integration. Inspect status, ancestry
and actual code before editing; do not reset, clean or modify the running demo
checkout. Do not merge another branch merely because an old handoff calls it
unmerged. Preserve all teammate work.

Read root/nested AGENTS.md, HACK.md, docs/PAYMENT_SPIKE.md,
docs/workstreams/06-data-broker.md, docs/responsibilities.md,
docs/INTEGRATION_CHECKPOINT.md, docs/PAYMENT_RUNBOOK.md and PRIMARY_HANDOFF.md.
Historical qualification records establish only their own recorded runs.

Own the backend demonstration fixture/setup, a thin runner and report under tools,
focused backend tests, minimal additive API/read projection if needed, and
docs/workstreams/11-yoga-pitch-demo.md. Jeff's compiler/investigation implementation
is the base to reuse; make only necessary, tested semantic changes for this task.
Nikita's durable runtime/payment gates and Prompt 7/09 payment work stay intact.
Lucas owns frontend design: provide exact backend payload examples,
but do not create a UI prompt/PRD or modify frontend components. Regenerate contracts if a public
DTO changes. Do not spawn additional agents.

No private .env reads/copies, existing-database access, paid application-model calls,
real RPC, broadcasts, deployments, pushes or main merges. Use fresh temporary state,
explicit mock payments and fake model clients. Do not reuse old paid-run cutoff or
budget authorizations. Do not alter global developer configuration.

## Required scenario

1. Begin with an ambiguous request: “SF adults 25–34 interested in fitness,
   counts by ZIP.” Let the actual compiler persist a meaningful question. Answer
   it through the normal clarification command: “Gym membership or fitness-app
   use; exclude standalone yoga.” Verify the accepted specification reflects that
   consent, without silently broadening the product.
2. Prepare the server's $120 quote, explicitly accept it, explicitly simulate
   funding, and wait for confirmed mock funding before exactly one runnable job.
   Produce actual CSV/JSON and run all eight independent mandatory checks.
3. Raise a timely factual category complaint with a valid actual target. Suggested
   natural complaint: “Your source calls yoga fitness. Why isn't it included?”
   The layered source classifies yoga under the broad Fitness & Wellness umbrella,
   but its specific eligibility rule excludes standalone yoga-studio membership
   from gym/app counts. This is consistent evidence at different levels, not two
   contradictory authorities. Show umbrella label, detailed eligibility and agreed
   scope together. These are proposed synthetic fixture contents, not existing
   source facts. Register and freeze them before acceptance.
4. Execute the existing guarded investigation. Preserve raw candidate, effective
   result, provenance, attempt status, source refs, accepted-specification hash,
   assessed binding and committed binding. Show the actual disposition, including
   UNKNOWN/CONFLICT/question/advisory/stale paths. Never hardcode a desired verdict.
5. Use the evidence already available to resolve the complaint without a staff
   reviewer when it is sufficient. Do not ask the customer to find source passages
   the agent already possesses. The target explanation is that umbrella membership
   does not establish eligibility under the purchased population. Verify both
   source facts and contract compliance independently; a broad yoga-is-fitness
   proposition may be true even when the assertion that this delivery owes yoga
   is false. Preserve that distinction in the finding.
6. Present the enforced conclusion with exact scope and source citations. Keep
   funds held through investigation and until normal settlement eligibility is met.
   Use the customer's actual delivery-acceptance command after resolution, then
   observe confirmed mock capture and one booking. Neither a model finding nor
   clicking a UI explanation is purchase/delivery consent or payment authority.
7. Restart against the task-owned database and retrieve the same accepted terms,
   finding, customer acceptance and payment state. This is a durable audit trail,
   not a procedural-learning claim.

This scenario follows the user's selected Path B direction. Distinguish
a taxonomy-membership claim from “the contract includes yoga” and from a request
to buy additional yoga data. Do not make those different claims share one verdict.
If the source fixture cannot pass legitimate delivery verification, preserve the
block and document the mismatch; do not suppress a check to force scene order.

## Fixture and integration design

Inspect and reuse backend/app/datasets.py, agents/dataset.py,
investigation/dataset.py, orders/dataset.py, orders/runs.py, orders/run_events.py,
contracts/{dataset,runs,semantic}.py, tools/brokerage_acceptance.py and the dataset
semantic/intake/review tests. The assessment pipeline already persists attempts in
catalog_records and exposes verdict.finding. Do not build a second assessor,
workflow engine, decision store, ledger or generic learning framework.

Register a separately identified synthetic fixture/edition BEFORE request creation
and acceptance in isolated state, using the existing registry/storage interfaces.
Keep the default sf-aggregate-v1 behavior and historical snapshots unchanged. If a
new allowlisted corpus/configuration seam is required, keep it explicit, local-demo
scoped and independently tested; do not expose arbitrary path/URL loading.
Freeze source bytes, source authority, dataset, coverage and all version/hash pins.
Never edit an accepted artifact or silently replace a source edition.

The runtime sees only ordinary allowlisted evidence. Expected outcomes, fixture
mutation instructions, grading metadata and desired endings remain test-owned.
Use the default excluding taxonomy as a simple regression, the layered taxonomy
as the centerpiece, and missing/contradictory authority as fallback regressions.
Tests must prove a change in evidence affects the assessment path without a
scenario-name switch in runtime code.

Inspect the current bounded predicate parser and citation resolver before claiming
the natural complaint or extra taxonomy fields are supported. Reuse current typed
proofs for eligibility. If needed, add narrowly tested claim normalization and
source-field support that preserves qualifiers/negation and carries evidence for
each proposition. Do not widen a regex until every yoga complaint maps to the same
predicate. The broad label alone cannot prove entitlement, and the exclusion alone
cannot establish the source's taxonomy. Unsupported compound claims stay unresolved.
Do not infer that all people practicing yoga are absent from gym/app counts:
someone who independently meets the gym/app criterion may qualify. The issue is
whether standalone yoga membership alone establishes eligibility.
If the implemented semantic boundary cannot support the exact natural complaint,
report that dependency and the supported wording; do not quietly substitute a much
easier claim while describing the harder one as demonstrated.

Existing checks establish exact source/output category agreement, not universal
natural-language entailment. State their actual scope. Preserve integer counts,
coverage uniqueness and suppression; never reveal exact suppressed counts.
Do not invent provider fault, automatic correction or a yoga expansion fee from
semantic support alone. Already owed yoga is never billable again.

## Customer finding and fallback behavior

Reuse existing findings, evidence-resolution endpoints, acceptance commands and
payment state. Prefer no new public DTO. Expose a compact explanation containing
the exact customer claim, accepted scope, umbrella taxonomy, eligibility rule,
enforced finding/provenance and available customer actions. Resolve citations from
actual frozen bytes. Keep the raw candidate and binding details in audit output;
they need not dominate the customer-facing explanation.

Do not add a human decision packet endpoint for the primary Path B demo. Preserve
the existing human-review path and verify it with missing/contradictory evidence:

Reuse Runs.reviewer_actions and Runs.decide. Server-provided enabled actions and
reasons are authoritative. Approve means an eligible proposed return; reject and
escalate retain review; ask consumes the existing bounded question allowance.
No reviewer action rewrites factual findings, accepted scope, expired authority,
or grants unconditional capture.

Avoid a new mutable duplicate of the decision. Preserve atomic effects and exact
idempotent acknowledgements. A stale mutation must return 409 without effect;
same-key same-payload replay must return the original response. Do not expose
privileged tokens, private model transport bodies or hidden suppressed data.

Do not emit aggregate rule_updated or enable global learning. A saved decision is
not a learned procedure. Leave /api/improvements and broker-review-v0.3 intact.
Leave procedural learning out of this pitch's main journey. Closing narration:
“The agreement defines what we owe. The evidence establishes whether we delivered.
This objection was resolved without a staff reviewer.” Use the last sentence only
if the observed run actually required no staff reviewer. Do not build the broader
learning system or claim that one demonstration measures a reduced intervention rate.

## Runner and pitch handoff

Keep tools/brokerage_acceptance.py and its four scenarios working. Add a thin
reproducible offline pitch runner using the real service/worker interfaces. Use
normal create/clarify/quote/accept/fund/dispute/answer/accept-delivery boundaries,
plus existing reviewer commands for fallback tests, never direct
SQL state fabrication or synthetic PASS/settlement injection. A fake assessor is
allowed only at the existing injectable test boundary and must be labeled a test
double in every report that could be mistaken for Claude evidence.

Default execution must positively disable paid models and real payment transport,
even under an inherited enabling environment. Use fresh run directories and reject
reuse that could overwrite evidence. Provide bounded waits, actionable errors,
--help and a validate/list path without creating an order. Do not patch expired,
Windows-specific historical supervisors into a new authorization mechanism.

Produce schema-versioned JSON and a readable chronological report with request,
clarification, accepted contract, mock funding, actual artifact paths/hashes,
verification, complaint, source refs, candidate/effective finding, customer-facing
explanation, explicit acceptance and terminal or held payment state. Preserve
failures and incomplete attempts; distinguish test-double, deterministic, recorded
and actual model modes.
No fabricated Claude usage, live receipts or explorer links.

Provide a manual API runbook with exact current DTOs, routes, role requirements,
polling and explicit acceptance/funding. Automated customer answers are rehearsal.
Document the separately guarded existing Claude path without executing it:
ENABLE_PAID_MODELS and ENABLE_DATASET_MODEL_ASSESSMENT, explicit model selection
and bounded budget/cutoff requirements. Do not claim offline results qualify that
live path. Do not invent new authorization based on keys being present.

Map outputs to the 180-second pitch: 0–20 thesis, 20–45 clarification/acceptance,
45–65 mock funding/dataset/checks, 65–120 complaint/evidence/finding/hold,
120–150 customer explanation/acceptance, 150–180 confirmed mock capture and thesis.
Model latency remains unmeasured until separately authorized rehearsal. Prepare
the complaint before funding and file promptly after publication. Never shorten
or extend real 60-second clocks. A test clock is only for isolated tests; a recorded
fallback must identify its original run and timestamps and say it is recorded.

Give Lucas an exact backend-to-display handoff with real example payloads from the
offline run, including provenance, source resolution, latest-binding commands and
available actions. Target funded aggregate /live; the root canvas's retained broker
flow cannot be presented as the same funded aggregate run. Frontend completion is
not an acceptance criterion for this backend task.

## Validation and completion

Test the meaningful clarification and frozen consent; no fulfillment before mock
funding; actual CSV/JSON byte checks; simple versus layered taxonomy evidence;
contract-inclusion versus taxonomy versus additional-scope claims; candidate versus
effective findings; invalid/stale citations; provider timeout or unsupported model
answer; question limit and unchanged deadlines; held funds with unresolved review;
no capture or fee from a finding alone; customer acceptance binding/idempotency;
restart persistence; and confirmed mock capture booking exactly once. In fallback
regressions preserve bounded escalation, trusted decisions and eligible mock return.

Use focused tests first, then the full backend suite and existing offline acceptance
runner. Run Ruff lint/format on backend and task-owned tooling, git diff --check,
and generated-contract freshness using the repository's Node version if public
DTOs change. Record baseline failures accurately; never weaken assertions, add
xfails or fabricate passing historical test counts to finish.

Write docs/workstreams/11-yoga-pitch-demo.md with base SHA, changed interfaces,
exact commands, artifact locations, observed results, known limits, actual pitch
script and frontend handoff. Add the actual implementation scope to the prompt
index only if that index exists on this branch; preserve historical entries.
Commit only task-owned changes locally. Return the commit SHA, validation results,
demo commands and what still requires frontend work or paid-model qualification.
Do not push, merge main, change the running demo or run paid/live operations.
