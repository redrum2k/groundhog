# Data brokerage migration and Lucas run-canvas integration

Implement the agreed product pivot: the primary product is now a data broker
delivering contract-checked aggregate datasets, replacing the supplier-catalog PDF
shortlist journey. This is an explicit product decision, not a domain mismatch to
resolve by keeping PDFs as the primary product. Complete the migration, connect
Lucas's existing canvas, and validate the result offline. Preserve his visual design.

This prompt supersedes conversation 5's limited data-broker adapter scope. Run one
migration/integration conversation, not both prompts in competing worktrees. If
conversation 5 is already running, use this prompt to steer that same conversation
and retain its useful work.

## Starting point and ownership

Inspect git status, branch, worktrees and commits. For a fresh conversation, work in
a separate worktree on `codex/data-broker-migration`, based on conversation 4's
completed, committed `codex/backend-integration` result. Fetch origin, inspect its
current main tip, and merge that reviewed commit into this task branch to integrate
**Jeff's PR #4 with the existing backend integration and Lucas's canvas**. PR #4,
"Add broker review and improvement workflow", is already merged into main at
`5c8dc726326bb9e3539cdb51e5aec221868223bc`; it includes Lucas's PR #3 at
`46f6c07994bae4f1f0dec7c4c0d3d367b4e8f0d1`. Verify current history rather than assuming
either is still the tip. Do not merge or cherry-pick either original feature branch
again; Jeff's PR was squash-merged. If continuing conversation 5 or 6, retain its
existing branch/worktree and checkpoint only its task-owned edits before integration.
The migration and payment-readiness worktrees already existed at the October 24
prompt review; inspect and reuse the assigned one instead of recreating it.
Do not reset branches or edit other worktrees. You are not alone in the repository;
preserve teammates' changes and integrate through their existing interfaces.

Verified baseline: conversation 4 completed at
`39dd58602b3f8ac0a7906b4db4ddbbdb57b3d981`, with a clean worktree and a handoff reporting
442 passing backend tests. Use that commit or a reviewed descendant containing it;
verify ancestry. The old local main at ac385a1 does not include this integration.
This baseline has offline validation only, with no observed live RPC/testnet results.
After integration, verify with `git merge-base --is-ancestor` that the backend
baseline, Lucas's merge and Jeff's merged SHA are all ancestors of HEAD. Merely
starting from current origin/main would omit the completed backend integration.

A non-checkout merge preview of `39dd586` with `5c8dc72` found conflicts in
`backend/app/main.py` and `README.md`. Resolve them semantically: retain the integrated
payment setup/injection, capability reporting, CatalogWorker and independent bounded
background lanes, and add Jeff's broker/improvement mounts, broker deadline sweep
and improvement recovery to that lifecycle. Do not restore the older serial sweep
or drop either recovery path by choosing an entire side. Check automatically merged
startup code too; a clean textual merge alone does not prove the hooks run.

Read AGENTS.md and applicable nested instructions, HACK.md, CONTEXT.md,
docs/PAYMENT_SPIKE.md, docs/PAYMENT_RUNBOOK.md, docs/API.md, handoffs for Nikita,
Jeff and Lucas, docs/workstreams/01-runtime.md, docs/workstreams/02-base.md,
docs/workstreams/03-settlement.md, docs/workstreams/04-integration.md and
frontend/HANDOFF.md, docs/responsibilities.md, and Jeff's root HANDOFF.md,
POLICY_DELTA.md, PIPELINE_MAPPING.md, IMPROVEMENT_DESIGN.md, API_CONTRACT.md,
TEAM_HANDOFF.md and EVALUATION_RESULTS.md from PR #4. If the verified baseline is
unavailable in this checkout, resolve that dependency before implementation; do not
substitute an incomplete branch.

Inspect the actual order/contracts/catalog/investigation/storage modules, worker,
payment journal/executor, and frontend/lib/run/{contract,source,fold,scenario,
stub-store}.ts, frontend/components/run, frontend/app/api/run-stub and their tests.
Inventory reusable infrastructure versus PDF-specific semantics before editing.

Own this coordinated domain migration, run contracts/event persistence/API, narrow
lifecycle hooks, Next bridge, generated types, necessary canvas data plumbing,
tests and documentation. The user authorizes the domain-specific changes required
in compiler, verification and investigation code. Preserve Jeff's substantive work
where applicable and document changed interfaces for him; do not replace reasoning
with browser-scripted verdicts. Reuse Nikita's worker, gateway, payment executor and
journal. Do not build a second orchestration system or ledger or redesign Lucas's UI.

Nikita may run the isolated payment-readiness task in parallel. That task owns only
spikes/payments, dedicated lab tests and docs/workstreams/07-payment-readiness.md.
Leave those files to that workstream; preserve the shared transport/executor/journal
interfaces and coordinate concrete shared fixes by commit. This migration owns
application deadline policy, domain settlement checks, public DTOs, API/event wiring
and generated artifacts. It must not wait for live transactions to finish its mock
and injected-chain acceptance tests.

## Reconcile Jeff's existing broker implementation

PR #4 is useful implementation to integrate, not a finished version of this pivot.
It leaves catalog as the default and adds `/api/broker` plus `/api/improvements` on
the invoice-compatible mock OrderService. Its `broker-review-v0.3` accepted policy
uses 600-second reviews, a 1,800-second case bound and USDSIM authorization at order
creation. It does not use the integrated Base funding gate or connect the run canvas.
This prompt supersedes its "catalog remains default" guidance for new orders;
existing accepted catalog, invoice and broker profiles keep their own policy.

Inventory and reuse these concrete seams before adding equivalents:

- `app/contracts/data_product.py`, `app/data_products.py`: typed specifications,
  source pins, requirement citations and delivered-byte checks. Extend/version the
  reusable semantics; `age_within_days` checks source recency, not cohort age.
  The existing float-valued rows, PASS/FAIL/UNKNOWN union and mandatory methodology
  PDF do not satisfy integer/suppressed counts, CONFLICT or the new CSV/JSON path.
  Frozen coverage IDs are useful, but still require the independent authoritative
  ZIP registry and authority evidence specified below.
- `app/runtime/broker.py`, `app/storage/broker.py`, broker contracts/routes: preserve
  useful intake, bounded questions, human tasks, immutable artifacts, receipts and
  durable events. Adapt domain operations to Nikita's funded jobs/payment journal
  for the new policy; do not make the new `/runs` facade a wrapper around legacy
  mock authorization/capture. Retain the old profile as compatibility, not a second
  financial execution path for new orders. Source-check FAIL currently leads to
  `reserve_free_regeneration`; distinguish source deficiency from established
  provider fault before spending the new policy's free correction.
- `app/improvement/`, `app/storage/improvement.py` and improvement contracts/routes:
  preserve Jeff's scoped proposal/probe/approval/activation/revoke loop and negative
  evidence. Do not rebuild it or treat review approval as template activation.
  Any reuse for new brokerage intake needs an explicit versioned adapter and tests;
  otherwise keep it scoped to the compatibility profile and disclose that boundary.
  Existing templates cannot change accepted terms, mandatory checks or money gates.
- `frontend/lib/{broker-api,broker.generated,improvement.generated}.ts`, the shared
  generator and Next proxies: retain compatible clients and extend the generation
  pipeline. Lucas's visual components were preserved by PR #4; keep that design.

Record which pieces were reused, adapted or retained only for compatibility. Jeff's
415-backend/59-frontend result and conversation 4's 442-backend result belong to
different trees; neither validates their merge. Preserve both regression sets and
report a newly run combined result, not a sum of historical counts.

## 1. Define and implement the bounded brokerage domain

Use Lucas's Bayline Data / Summit Fitness story: a buyer requests synthetic aggregate counts
for San Francisco adults aged 25–34 interested in fitness, grouped by ZIP. The
contract specifies geography, age bounds, category meaning, population/counting
unit, source editions, required columns, completeness and suppression rules. Do
not build live data acquisition, a vendor marketplace or personal-record delivery.

Make these concepts explicit in typed models and CONTEXT.md's glossary:

- Dataset specification: the requested cohort, grouping, measurement and output rules.
- Coverage universe: a frozen authoritative list of expected geographic keys,
  separate from whatever rows happen to exist in a vendor file.
- Source manifest: exact registered dataset editions/hashes and authority records.
- Dataset delivery: immutable CSV plus structured JSON preview/manifest with stable
  row identities, schema, content hashes and verification results.
- Evidence reference: a persisted message or source/delivery dataset, version/hash,
  stable row and column; absence claims resolve to an expected key and actual artifact.
- Evidence repair, provider correction, additional work and substantive replacement:
  separate operations with the existing consent and financial boundaries.

Update the primary product policy in HACK.md and vocabulary in CONTEXT.md; put
implementation details in technical docs. Record a short migration decision with
the tradeoff and compatibility plan. A name-only search-and-replace is insufficient.

Replace PDF-centric qualification and output checks for new brokerage orders with
stable server-owned requirements covering cohort/category, geography/age, schema,
coverage, suppression and provenance. Inspect the delivered CSV/JSON bytes through
an independent validation path; producer sidecars or a model's self-report are not
proof of output correctness. Require agreement between downloaded artifact and preview.

The existing runtime/catalog_policy.py capture gate explicitly requires global:pdf
and other catalog obligation IDs. Replace this assumption for brokerage orders with
a server-owned required-check registry selected by the immutable accepted domain/
policy version. Preserve the original checks for historical PDF orders. Require all
brokerage mandatory checks and current bindings before settlement; a missing report,
empty obligation list or arbitrary model-supplied PASS must never bypass the gate.

Check that every expected ZIP is accounted for, without duplicates or silent drops.
Specify inclusion of SF ZIPs through an explicit versioned synthetic reference
registry; do not pretend postal ZIPs inherently equal city boundaries. Define the
demo's nonnegative integer count unit and disjoint group assumptions. Preserve
suppressed rows with null counts and an explicit suppression status: every released
count must be at least 50. Unknown/missing and suppressed are different. Never leak
the suppressed exact count in previews, citations, messages or public events. This
threshold is a demo contract check, not a claim of a general privacy guarantee.

Keep PASS/FAIL/UNKNOWN/CONFLICT as evidence assessments. Resolve their dependencies
and materiality deterministically; neither PASS nor a reviewer opinion grants
payment permission. Category interpretation and disputed source meaning can use
Jeff's bounded investigator with cited inputs; schema, thresholds, identity and
coverage checks should be deterministic. Preserve an injectable model interface
and conservative offline implementation. Do not hardcode a verdict from a lane,
scenario ending, hidden expected label or generator mutation flag.

Provide synthetic source data, authority records, a coverage registry and transcripts
that support these cases without exposing evaluation answers to runtime:

1. A conforming dataset completes review and becomes eligible for settlement.
2. Missing ZIP 94110 is detected against the coverage registry. Establish provider
   fault before reserving the one free correction. A bad vendor source alone does
   not prove provider fault. Never deliberately weaken verification to recreate
   the animation; a deficient published fixture must be explicit fault injection.
3. Adding Oakland is additional scope: provider offer, explicit buyer acceptance,
   separate order/authorization and funding before work.
4. Whether yoga counts as fitness requires evidence about the accepted definition.
   Resolve it when supported; otherwise ask a useful bounded question or escalate
   to Maya. Do not force grey merely because the UI has a grey panel.

## 2. Reuse lifecycle and financial policy; migrate safely

Keep intake, clarification, quotes, acceptance, delivery, evidence and dispute
endpoints where compatible. Add explicit versioned brokerage schemas/handlers where
PDF-specific inputs cannot be preserved honestly. Document every changed contract
and generate clients together; do not silently reinterpret a legacy DTO or record.
Use additive persistence migrations and a domain/policy discriminator where needed.
New default intake and fulfillment use brokerage. Preserve historical catalog
snapshots, artifact access, idempotent responses and bookings under their accepted
policy, plus the isolated `/api/jobflow` API and `/jobflow` UI. Preserve PR #4's
accepted `broker-review-v0.3` records, artifacts, receipts and mock bookings through
its explicitly scoped `/api/broker` compatibility API, along with the scoped
`/api/improvements` records/API. Do not reinterpret these as live funded obligations
or overwrite their accepted 600-second/1,800-second clocks. Give new brokerage
orders a distinct domain/policy version; do not repurpose that existing policy ID.
Retain only the PDF code needed for compatibility; no PDF generation or parsing
requirement in the new brokerage happy path. Avoid a broad internal rename that
adds risk without behavior.

Freeze the accepted specification, sources/coverage registry, price, parties,
payment terms and deadlines. Prices come from a versioned server pricing policy,
never the compiler or browser. For the new brokerage demo policy, use Lucas's
$120 base, $60 Oakland extension and $30 separately offered yoga expansion as
explicit synthetic defaults, documented as new demo assumptions; these do not
change historical $15/$5 catalog agreements. Yoga already owed under an accepted
contract is not billable expansion. Keep the current 60-second demo review/dispute
windows unless explicitly configured in a new policy; do not import the frontend's
48-hour timer or PR #4's 600-second profile. Freeze the selected durations at
acceptance and publish server deadlines. New prices and authorization deadlines are
server-owned; do not carry over legacy BrokerCommand's arbitrary offer price and
caller-supplied authorization expiry as authority for the new policy.

Close the known capture-deadline gap. Existing terms expire capture authority one
hour after quote preparation, but delivery and dispute windows currently open for
60 seconds from their own start times. They are not guaranteed to fit before expiry.
The immutable on-chain authorizationExpiry is the capture deadline; review/dispute
clocks cannot extend it. Add a versioned, documented scheduling budget and positive
transaction margin, accounting for elapsed funding/fulfillment time, a dispute opened
at the end of review, and any permitted correction and fresh review. Check remaining
time before dispatch, delivery publication and correction reservation, and recheck
capture eligibility against a latest-safe-submission cutoff. Use a conservative
margin for RPC latency, block inclusion and clock skew; it is not a finality guarantee.

Do not silently shorten a promised review, extend signed terms or capture early to
beat expiry. If the full applicable window no longer fits, persist an explicit
unresolved/non-settling outcome and use the existing authorized release/reclaim
path. Still record a late complaint; no timing check may discard it or allow disputed
capture. Surface the effective deadlines and permitted actions. Reconcile already
submitted operations even after the cutoff. Expiry/reclaim eligibility is not proof
of returned funds. Do not rewrite historical snapshots to introduce new deadlines.

Retain bounded clarification/investigation, two questions maximum, no deadline
extension by answers, current evidence bindings, permitted source authority and
required consent. Evidence-only repair changes evidence revision, not automatically
delivery version. One established provider defect allows one durable free correction;
a failed/repeated correction escalates. Initial operational retries are separate.
Substantive replacement needs an accepted child agreement and confirmed parent void
before child funding/work. Ordinary additional work keeps a separate accepted price.

Payment rail remains **direct Base Commerce Payments on Base Sepolia**. The user
relayed judges' guidance allowing a lightweight implementation without end-to-end
x402 (their option 2); record that guidance and the disclosed choice in the handoff.
This is not a guarantee of an award or proof of full x402 compliance. The x402
auth-capture EVM binding uses the same Commerce Payments escrow stack, but our
implementation has no x402 facilitator layer or CDP server-wallet operator. Do not
add them during this migration. Post-capture refunds remain unimplemented; void
returns uncaptured funds. Never label direct Commerce Payments as completed x402.
Reference: https://github.com/x402-foundation/x402/blob/main/specs/schemes/auth-capture/scheme_auth_capture_evm.md

Reuse the integrated transport/journal and keep mock mode the default. Preserve
exact atomic integer amounts, JSON decimal strings, accepted conversion and verified
live token domain. No new escrow or wallet protocol. Keep quote acceptance, signature
preparation, buyer wallet signature, submission and confirmed held funds distinct.
Wire the existing buyer signing endpoints/actions and typed data; never require a
buyer private key on the backend or represent a mock signature as chain authority.

Work starts only after the established confirmed-funding gate or explicit mock
simulation. Capture still requires current mandatory checks, no material blocker,
unresolved dispute or pending consent, customer acceptance or undisputed review
expiry, valid exact terms and terminal exclusivity. A reviewer click, model verdict,
timeout, signature or transaction submission cannot stand in for confirmed payment.
Preserve reconciliation, late-dispute handling and parent-return dependencies.

## 3. Backend contracts and durable events first, then decisions

Pydantic is the transport source of truth. Generate OpenAPI and matching TypeScript;
replace frontend/lib/run/contract.ts's handwritten transport types with generated
types/re-exports. Preserve useful wire aliases, separating view models from transport.
Add repeatable generation and freshness checks, including existing catalog, invoice,
broker and improvement clients. Extend the current generator instead of replacing
its broker/improvement exports with a runs-only generator.

Implement the exact backend routes Lucas requested:

- `POST /runs` -> `{id, poll_after_ms}`. Specify a typed creation body and durable
  idempotency. Creation cannot imply quote acceptance, buyer consent or funding.
  A browser `ending` must not select a live verdict.
- `GET /runs/{id}/events?after=<seq>` -> `{events, poll_after_ms}` with documented
  additive current binding/actions/server-time metadata consistent with the cursor.
  Use exclusive, strictly increasing per-run sequence numbers, ordered bounded
  batches, default after=0, no-store and 1000 ms polling guidance. Specify empty,
  invalid/future cursor and catch-up behavior. Reads do not advance workflow.
- `POST /runs/{id}/decisions {action, binding}` -> documented `{ok:true}`-compatible
  acknowledgement. Use an idempotency header and existing trusted reviewer checks.

Document request/response examples and error envelopes: 404 unknown run; 422 invalid
input without echoing secrets; 409 stale binding/incompatible state or changed
payload under a reused key; existing 401/403 semantics for missing/invalid authority.
Preserve existing command error behavior where callers depend on it.

Persist append-only events and their stable effect keys in SQLite, atomically with
domain changes or via a durable transactional outbox. Ensure restart, concurrent
writers and retries neither lose transitions nor duplicate effects. Snapshot diffs
and server timers replaying a fixed script are not an event log.

PR #4 already writes transactional `jf_events` with entity-local sequences, but
its generic Event payload and unbounded event list are not Lucas's typed `/runs`
contract. Reuse or durably map actual effects with stable keys, bounded cursors and
explicit run/order identity. Do not proxy polling through `Broker.view`/`_sync`,
which can advance deadlines and finances on a read. Do not let `_base_mutation`'s
server-selected current binding replace validation of the binding the reviewer saw.

Support Lucas's union: steps_planned; step_started, step_completed, step_waiting;
message; contract_line_drafted/approved; delivery_ready; check_passed/failed/fixed;
evidence_found; dispute_opened; verdict; amendment_signed; controller_decided;
rule_updated; payment_authorized/captured; books_posted. Add typed pending/failure/
uncertainty metadata needed to represent real states. Emit only actual persisted
effects; schema support does not require pretending all features are implemented.

Keep the five main step IDs clarify, paid, produce, review, captured, and up to
three dispute steps investigate, verdict or grey, amend or decide. Every step
event carries attempt starting at 1; a permitted rerun re-enters produce with the
same step ID and attempt 2. Attempt, delivery version and evidence revision differ.
Paid describes funding/held funds, not provider receipt. Provide server-owned
reviewClosesAt, binding, available_actions and reasons. Never infer evidence version
from the number of visible cards. Bind decisions to the exact run/order/snapshot
and delivery/evidence versions, extending the draft binding if necessary.

Validate authority, current state, binding and idempotency atomically with decisions:
approve supports an eligible proposed remedy, not unconditional capture or scope
rewriting; reject records the reason without buying extra work; ask persists one
bounded evidence request and awaits an actual answer; escalate retains human review.
Record trusted actor, reason and cited evidence. Return available actions from policy.
Exact retries return the original result; stale requests mutate nothing. Do not
silently substitute a fresh binding or automatically retry a stale approval.

## 4. Connect the existing canvas and disclose mock behavior

Use same-origin Next route handlers to bridge the runs/events/decisions APIs to a
server-configured backend URL. Forward only allowlisted operations. Reviewer and
internal tokens remain distinct and server-only, never NEXT_PUBLIC or browser
authority. Make the trusted local-demo access boundary explicit; fail closed
outside supported demo mode instead of exposing privileged actions publicly.

Use persisted backend events for the live flow from intake onward. A scripted buyer
is permitted only as an explicit demo harness issuing real persisted commands;
animated messages do not count as acceptance or an answer. Keep recorded rehearsal
separate, with no recorded prefix spliced into a live cursor and no silent successful
stub fallback after backend failure. Remove live dependence on scenario.ts for
contracts, prices, deadlines, sources, permissions or outcomes. Preserve the design.

Make creation/reload resumable and idempotent; cancel old polls, ignore responses
from old runs, deduplicate events and handle attempt transitions without stale UI
state. On 409 refresh binding/events, explain the conflict and require another
deliberate action. Evidence clicks resolve actual messages or dataset cells.

Mock payments remain labeled mock with null transaction hashes and no explorer
links. Real hashes come only from matching observed chain evidence; pending or
uncertain operations never emit completed capture. Provide runnable fixtures for
every payment state and signing error the UI supports. An amendment_signed event
requires durable buyer acceptance of identified terms. A rule_updated event needs
an actual scoped/versioned approved rule; otherwise show a proposal or explicitly
recorded learning illustration. Never rewrite an accepted contract or install a
global learned rule just because Maya clicked approve.

If using Jeff's improvement loop, a rule_updated event must identify the applicable
persisted activation/version/scope; proposal, probe, approval and activation are
different effects. Keep unrelated compatibility-profile improvements out of new runs.

Books refer to existing idempotent ledger postings. Unknown cost/margin is unavailable,
not the scenario's fabricated $6 expense. Display double-entry rows only if backed
by balanced postings. Do not imply an external accounting integration exists.

## Acceptance and handoff

Use temporary databases, synthetic sources, fake model/RPC transports and injected
clocks. Prove delivered-byte validation, independent coverage, no suppressed-count
leakage, provenance resolution, conforming delivery, free correction, separately
accepted expansion and evidence-backed yoga resolution/escalation. Add cases for
incorrect age/geography/category, missing/duplicate rows, tampered artifact/preview,
unknown authority and historical-policy compatibility.

Test event replay across restart/concurrency, no missed transitions between polls,
idempotency, repeated step IDs/attempts, all four reviewer actions, stale bindings
including evidence updates adding no card, role failures and unchanged state on
rejection. Exercise frontend reload/remount, delayed/duplicate polling, 409 refresh,
backend failure and clearly separated recorded mode. Confirm funding alone enables
one job, pending capture does not book, confirmed/mock completion books once, and
uncertain/expired/replacement dependencies stay truthful.

Add injected-clock cases for near-expiry funding/fulfillment, delivery too late for
the accepted review/dispute budget, a last-moment dispute, correction with too little
time, cutoff boundary equality, worker delay/restart and submission before cutoff
with reconciliation afterwards. Prove no premature capture, silently shortened
review, dropped complaint, deadline extension or invented return. Verify brokerage
capture requires the full dataset check registry while legacy PDF gates still work.

Run uv sync --locked --project backend, relevant tests and then the complete backend
suite, Ruff lint/format, generated contract freshness, frontend tests/typecheck/build
using its documented Node version, and a browser smoke test against the backend.
Reuse tests and adapt obsolete primary-domain assertions deliberately; do not delete
historical regression coverage or weaken financial policy to pass fixtures.
Include PR #4's `tests/broker`, question-delivery/resume and improvement regressions,
plus startup/restart tests proving broker expiry and improvement recovery coexist
with the integrated worker/payment lanes. Adapt catalog-default assertions deliberately
while preserving legacy route, accepted-policy and financial isolation checks. Verify
all retained generated clients and the new run client together. Historical PR browser
results do not establish a live canvas-to-broker connection.

Update HACK.md, CONTEXT.md, API/status docs, handoffs and relevant AGENTS.md ownership/
domain guidance to reflect the pivot and verified implementation. Write
docs/workstreams/06-data-broker.md with the migration map, exact endpoints/schemas/
errors/events/actions, signing flow, policy defaults, compatibility, commands, tests
actually run and remaining mock/planned components. Give Lucas a concise runnable
handoff. Explain any blocked capability precisely; do not claim end-to-end success
from recorded playback.

Make the local acceptance handoff directly runnable from a clean checkout: include
exact backend/frontend commands, server-only bridge/demo configuration, fresh DB
and artifact paths, synthetic source/authority/coverage setup, backend-mode URL or
control, explicit acceptance/mock funding steps, and the brokerage browser-test
command/browser dependency. State where traces, screenshots and final ledger/payment
evidence are saved. The old invoice `frontend/scripts/acceptance.cjs` is not the
brokerage smoke test. Verify the production frontend build against the same local
backend, or document any intentional production-mode access block precisely.
Use docs/LOCAL_AND_RENDER_RUNBOOK.md from the original checkout as the provisional
run plan if available, and replace pending setup details with observed commands in
your committed handoff. Hosted access beyond the trusted local-demo boundary remains
a separate deployment prerequisite; do not bypass that boundary to make Render work.

Self-review and commit only task changes locally. Return branch/SHA, implementation
summary, demo/test commands and a PR-ready description. Do not push, merge main,
deploy, broadcast, invoke paid application models or access existing private .env,
wallets or databases. This task authorizes offline implementation and validation.
