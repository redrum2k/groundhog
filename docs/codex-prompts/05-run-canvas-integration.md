# Conversation 5 — connect Lucas's run canvas to the integrated backend

**Superseded by the agreed data-brokerage pivot:** use
[06-data-broker-migration.md](06-data-broker-migration.md) instead. It includes the
canvas integration and makes brokerage the primary domain. If this conversation is
already running, steer it with prompt 6 rather than launching an overlapping agent.
The text below is retained as the earlier integration plan.

Integrate Lucas's existing Next.js run canvas with real persisted backend runs,
events and reviewer decisions. Implement the integration and its tests; preserve
his visual design. This task authorizes the necessary frontend data plumbing,
generated types, server routes and small rendering corrections, not a UI redesign.

## Starting point and ownership

Use a separate worktree on codex/run-canvas-integration, based on the completed,
committed codex/backend-integration branch from conversation 4. Inspect git status,
worktrees and commit history first. Fetch origin and merge its current main into
this branch, preserving both backend integration and Lucas's frontend. Lucas's
run canvas was verified on remote main at merge 46f6c07994bae4f1f0dec7c4c0d3d367b4e8f0d1
(PR #3); fetch current history rather than assuming that remains the latest commit.
Do not merge lucas/run-canvas again if already included in main. Never reset another
branch, edit another worktree or overwrite teammates' uncommitted changes.

Read AGENTS.md, applicable nested instructions, HACK.md, CONTEXT.md,
docs/PAYMENT_SPIKE.md, docs/PAYMENT_RUNBOOK.md, docs/workstreams/04-integration.md,
the three earlier workstream handoffs, frontend/HANDOFF.md, frontend/README.md,
docs/handoffs/lucas.md and the actual implementation. If conversation 4 has not
finished, report that dependency and continue independent contract/frontend
inspection; do not treat its incomplete branch as the validated integration base.

Inspect these frontend files in particular:
- frontend/lib/run/contract.ts, source.ts, fold.ts, scenario.ts and stub-store.ts
- frontend/components/run/run-app.tsx, canvas.tsx and panel.tsx
- frontend/app/api/run-stub/runs/route.ts
- frontend/app/api/run-stub/runs/[id]/events/route.ts
- frontend/app/api/run-stub/runs/[id]/decisions/route.ts
- frontend/tests/run-live.test.ts, run-app.test.tsx and run-scenario.test.ts

Own the new run contracts/storage/API/projection, narrow lifecycle event hooks,
Next server bridge, generated run types, feed/fold integration, tests and docs.
Reuse the existing worker, payment executor/journal and settlement gates. Jeff owns
investigation and document/data reasoning; use his available interfaces and an
explicit offline substitute where needed. Preserve both root catalog endpoints and
the invoice API at /api/jobflow, with the invoice UI now at /jobflow.

## Reconcile the domain and policy before wiring events

Lucas's canvas models Bayline Data's aggregated SF fitness counts by ZIP, interview
messages and dataset cells. The catalog backend currently models supplier PDFs.
Create a bounded data-broker run adapter with persisted transcript, accepted terms,
versioned dataset artifacts and evidence references. Reuse the durable lifecycle
and payment infrastructure where its invariants apply. Do not relabel catalog
products as ZIP counts or claim a PDF verifier checks the data-broker contract.
Document which checks run against actual dataset bytes and which investigator
behavior is an offline fixture. Preserve existing catalog/invoice accepted policies.

The payment decision is already made: **Base Commerce Payments on Base Sepolia**.
Use the integrated adapter. Replace the run draft's rail: "x402" with an explicit
Base Commerce Payments value in generated models and related UI copy. Do not build
an x402 path or a second wallet/ledger implementation. Keep mock as the default;
this task does not authorize broadcasts or paid application model calls.

The frontend's $120/$60/$30 prices, $6 costs, 48-hour windows and automatic learned
rules are scenario assumptions, not accepted backend policy. Live display values
must come from persisted server terms, deadlines and postings. Current catalog
review is 60 seconds; do not install 48-hour clocks from scenario.ts into existing
orders. If a new broker-specific demo policy/configuration is necessary, make it
explicit, versioned and separate; freeze accepted terms and document its choices.
Missing cost data is unavailable, not a fabricated $6 expense or profit figure.

Keep the live milestone bounded: backend-fed amber investigation and Maya's decision,
with an honest mock settlement path. Recorded shared/red/green/learned demonstrations
may remain explicitly recorded. A scripted buyer may call real command APIs in an
explicit demo harness; its answers, acceptances and funding simulation must be
persisted actions, never implied by browser playback. Implement useful independent
work before escalating any genuinely missing domain decision.

## 1. Backend-owned contracts and durable event feed — first deliverable

Create discriminated Pydantic models and export matching TypeScript from backend
schemas. Replace handwritten transport definitions in frontend/lib/run/contract.ts;
a thin re-export is fine. Preserve camelCase wire fields through explicit aliases
where useful. Keep pure view-model types separate. Add repeatable generation and a
freshness check without confusing run types with the invoice-only generator.

Implement the exact backend paths:
- POST /runs -> {id, poll_after_ms}. Define and document its real creation body and
  idempotency. A normal request cannot supply an ending that chooses its verdict.
- GET /runs/{id}/events?after=<seq> -> {events, poll_after_ms}. Default after=0,
  strictly increasing per-run seq, exclusive cursor, ordered bounded batches,
  no-store responses and 1000 ms polling guidance. Specify invalid/future cursor
  behavior, pagination/draining and empty responses. Missing run is 404; invalid
  input is 422. Reads must not advance the workflow or manufacture events.
- POST /runs/{id}/decisions {action, binding} -> documented acknowledgement compatible
  with the canvas's {ok:true} response, with the authorization/version rules below.

Persist events in SQLite with additive migrations. Append state changes and their
events atomically, or use a durable transactional outbox. Give each emitted domain
effect a stable deduplication key. Restart, concurrent writers, retries and repeated
polls must not lose transitions or duplicate effects. A snapshot diff between polls
cannot substitute for the event log. Do not replace the stub with a server-side
timer that plays the same hardcoded scenario. Bootstrap any explicit demo run from
persisted synthetic state and label it as such.

Support the complete existing RunEvent union, including steps_planned, the three
step lifecycle events, message, contract_line_drafted, contract_approved,
delivery_ready, check_passed/failed/fixed, evidence_found, dispute_opened, verdict,
amendment_signed, controller_decided, rule_updated, payment_authorized,
payment_captured and books_posted. Supporting a schema does not require falsely
emitting an event for an operation the backend has not performed. Add typed payment
status/error/binding metadata where the existing union cannot represent reality;
update generation, fixtures and the fold together.

Keep five main step IDs: clarify, paid, produce, review, captured. A dispute adds
up to three displayed steps: investigate, verdict or grey, amend or decide. Step
events carry an explicit attempt (initially 1); permitted reruns re-enter produce
with attempt 2 while retaining its step ID. Attempt is not deliveryVersion or
evidenceVersion. Stage completion must reflect durable outcomes. Preserve history
and explain allowedBy from the actual check/policy enabling an action.

Events carry server timestamps. reviewClosesAt is the persisted server deadline,
with server time supplied for rendering; polling, answers and reloads do not reset
it. Include a server-issued current binding consistently with the returned event
cursor. Remove fold.ts's inference that evidenceVersion equals the number of cards.
Bind actions to the exact run/order/snapshot and current delivery/evidence versions;
add an opaque token or revision fields if the draft's two counters are insufficient.

Evidence must resolve to a persisted message ID or exact dataset identity/version,
row and column (including a missing-row claim), with provenance sufficient to verify
it. Keep source.kind="none" only for an explicitly unavailable target, never as
invented proof. Strip generator/evaluation truth from investigator inputs. The
synthetic dataset's flag fields and selected rehearsal lane are not verdict evidence.

## 2. Reviewer decisions and browser integration — second deliverable

Use the existing reviewer-token check on the backend decisions route. Add same-origin
Next route handlers, for example /api/run-backend/runs and its events/decisions
children, forwarding only allowlisted calls to a server-configured backend URL.
REVIEWER_API_TOKEN remains server-only; never forward browser-supplied authority,
expose a generic proxy or put credentials in NEXT_PUBLIC variables. Preserve the
distinction between internal worker and reviewer credentials. This is a trusted
local demo bridge, not production customer/reviewer authentication; keep its local
demo access explicit and fail closed outside the supported deployment mode.

Validate action, reviewer authority, current review state and binding in the same
transaction as recording the decision and its events. Use an idempotency header
or generated request field that survives exact HTTP retries. Preserve actor, reason
and evidence provenance; identity comes from trusted server context, not a browser
string. Reject stale delivery/evidence/snapshot or incompatible current state with
409 before mutation. Exact replay returns the original result without another
decision/event/booking; changed payload under the same key is 409. Never silently
replace a stale binding with the latest version on the server.

Document these action semantics and implement their safe mappings:
- approve: support the complaint/proposed resolution only where current policy and
  evidence allow; reserve a permitted correction or require new accepted terms for
  changed scope. It is not unconditional capture or unilateral contract rewriting.
- reject: record the reasoned rejection; any additional-work offer still needs
  separate buyer acceptance and funding. No automatic purchase or complaint fee.
- ask: persist one bounded evidence question and wait for an actual answer. A demo
  scripted answer, if used, is a separate labeled API command with its own binding.
- escalate: persist a destination/reason and retain a held human-review state.

Return server available actions/reasons so the browser doesn't infer permissions
from color or step names. On 409, show the conflict, refresh the event feed/binding
and require a new deliberate action. Do not automatically replay a stale approval.

Replace source.ts's stub-only live path with the server bridge. Respect poll_after_ms;
cancel in-flight requests/timers on unmount or run change, reject responses from old
runs, deduplicate events and preserve cursor order. Make run creation/reload resumable
and idempotent, including React remounts. Do not mix browser-recorded prefix sequence
numbers with the backend cursor. Either replay the whole persisted backend stream
or use a documented versioned seed/cursor; keep recorded playback separate.

The live fold, step plan, prices, binding, captions and citations must use backend
data rather than scenario.ts's canned outcome. Disable the ending selector as a
live verdict input. Retain explicit recorded fallback; a backend error must not
silently switch to a successful scripted ending. Preserve the canvas layout and
animations while correcting data-dependent labels and states.

## 3. Payment, amendments and books semantics

Keep step ID paid for compatibility, but describe it as authorized/funds held as
appropriate. A buyer signature is not confirmed escrow funding; confirmed funding
is not provider payment. Produce stays blocked until the backend's funding gate
passes. Expose pending, uncertain, failed, returned and expired states honestly.

Emit payment_captured only after the existing settlement boundary records the
confirmed outcome (or explicit simulated mock completion). Real captureTx must
come from observed matching chain evidence. Mock events have mock=true, null hashes
and no explorer link. Do not generate success events on submission or timeout.
Use exact backend money/atomic-unit types; replace Money=number as a financial
contract and restrict floating-point formatting to presentation.

Emit amendment_signed only for durable explicit acceptance of identified new
terms, not from a reviewer click or animated buyer message. Retain child-order
funding and parent-return dependencies from the integrated backend. A rule_updated
event requires a persisted scoped/versioned rule change with authority and effective
scope; a recommendation may be shown as proposed. Do not let Maya's decision mutate
an already accepted contract or silently install a global learned rule. The learned
replay may remain clearly recorded until an actual approved rule path exists.

books_posted must refer to persisted idempotent postings backed by confirmed/mock
settlement and recorded costs. Preserve balanced accounting if double-entry rows
are shown. Do not synthesize revenue/cost/margin from scenario constants or create
a competing payment ledger. Clearly distinguish internal demo books from an
external accounting integration, which is outside this task.

## Acceptance and handoff

Use temporary DBs and synthetic datasets/transcripts, injected model and RPC clients,
and controlled clocks. Prove ordered cursor replay, no missed transitions between
polls, restart/concurrent-writer safety, exact retry semantics, repeated step IDs
across attempts and resolvable source references. Exercise all four reviewer actions,
stale bindings (including an evidence change that adds no card), role/token failures,
bounded questions and no mutation on rejected requests. Test remount/reload, duplicate
or delayed polls, 409 refetch, server failure and explicit recorded fallback.

Demonstrate one real-backend local amber journey with durable evidence, Maya's
decision, applicable consent/correction gates and truthful mock payment/books. Verify
pending/uncertain transactions cannot complete captured. Preserve the catalog and
invoice regression suites and Lucas's existing recorded-mode tests. Run full backend
tests/Ruff, generated-contract checks, frontend tests/typecheck/build using the Node
version required by package.json, and a browser smoke test against the actual backend.

Update OpenAPI, generated run types, examples and frontend configuration/run commands.
Write docs/workstreams/05-run-canvas.md covering exact endpoints/bodies/errors,
event ordering/bindings, reviewer semantics, payment rail, domain/policy mappings,
tests actually run and remaining mocked/planned features. Reconcile misleading x402,
48-hour and automatic-learning claims in handoffs without rewriting historical
accepted records or pretending unimplemented behavior is complete.

Commit only task changes on codex/run-canvas-integration. Return the commit SHA,
changed interfaces, local demo commands and a PR-ready description. Do not push,
merge main, deploy, broadcast transactions, invoke paid models or read existing
private .env/wallet/database files. Report real blockers precisely and continue
independent authorized work; never substitute a fake success for a missing feature.
