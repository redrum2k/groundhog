# 08 — Runtime review remediation

Branch: `codex/review-remediation`, in the existing assigned worktree. Baseline:
`35194536da06481591291f2d486725ccb448e59d`, retaining migration `1956f18` and
payment-readiness `f8a929a7fab2ac10ffee2a0aca112ca93a72fb2d`. Initial status was
clean. No second worktree, reset, main merge, push, deployment, private state,
paid model, live RPC or broadcast was used. The commit containing this handoff
is the local reviewable result; its exact SHA is returned with completion.

**R1/R2/R5/R6 are addressed. R3/R4 remain Jeff-owned release blockers.** The
compiler file has no completed later patch in available local history (its last
commit remains `1956f18`). Do not treat the passing suite or happy-path browser
smoke as approval for a new feature/deployment milestone. Live payment execution
also remains blocked on the separately scoped recovery and measured preflight below.

## R7 follow-up — unavailable preview recovery

Continued the same worktree from clean `086b5ba596af445dcf8009b6c3ddc82b03ac69de`,
matching `origin/codex/review-remediation` and retaining reviewed `692f500` and the
combined 06/07 history. This follow-up owns only `orders/dataset.py`, its new HTTP
regressions and this record. No Jeff branch was merged; his compiler and R3/R4
tests are unchanged. Earlier validation below records the original 08 pass.

**Cause and fix:** `DatasetLifecycle.complaint_targets` reopened the delivered
preview before returning mandatory targets. Hash mismatch raised 409 and absence
raised 404, aborting caught-up status pages and valid complaints. Both failures
were reproduced on the starting descendant using newly created temporary DBs,
synthetic sources, explicit mock funding and an injected clock. Target construction
now uses the immutable accepted requirement IDs/checks and coverage keys. It performs
no artifact I/O and retains the existing field/row/column validation. Unexpected
delivery rows cannot add accepted row identities; the whole-dataset artifact target
remains available to report delivery defects.

`tests/dataset/test_review_artifact_availability.py` adds eight HTTP regressions,
covering both missing and overwritten previews:

- Three-event pages reach catch-up, followed by an empty caught-up page. Events,
  binding, current funded payment metadata and deadlines stay intact. Controls remain
  withheld until catch-up, and future cursors/oversized pages are rejected.
- Complete SQLite dumps are unchanged after reads, including reads crossing review
  and authorization expiry. Application restart precedes clock advancement because
  startup has an existing explicit deadline sweep; GET does not perform that sweep.
  Neither missing files nor overwritten bytes are repaired by polling.
- A current R-ARTIFACT/dataset complaint records once and replays the exact HTTP
  response after restart and dispute expiry. Prior events, snapshots and delivery
  records remain intact. Invalid targets/intents, changed idempotent requests and
  stale bindings remain rejected without writes.
- Preview downloads still return 404/409 and expose no substituted bytes. Independent
  verification rejects the preview, HTTP acceptance refuses capture before and after
  restart, and the explicit deadline sweep retains human review with funded payment
  metadata and no capture/return booking.

Commands actually run from this worktree:

```sh
# Before the fix: polling reproduced 409/404; valid complaints independently did too.
uv run --locked --directory backend pytest tests/dataset/test_review_artifact_availability.py -q --tb=short
uv run --locked --directory backend pytest tests/dataset/test_review_artifact_availability.py -k whole_dataset -q --tb=short
# After the fix:
uv run --locked --directory backend ruff format tests/dataset/test_review_artifact_availability.py
uv run --locked --directory backend pytest tests/dataset/test_review_artifact_availability.py -q --tb=short
uv run --locked --directory backend pytest tests/dataset tests/api -q --tb=short -rx
uv run --locked --directory backend pytest tests/dataset/test_lifecycle.py::test_reads_replay_restart_concurrency_and_cursor --tb=short
uv run --locked --directory backend pytest tests/dataset tests/api --tb=short -rx
uv run --locked --directory backend pytest tests/dataset/test_compiler_review_blockers.py --runxfail -q --tb=short
uv run --locked --directory backend pytest
uv run --locked --directory backend ruff check . ../tools/brokerage_acceptance.py
uv run --locked --directory backend ruff format --check . ../tools/brokerage_acceptance.py
git diff --check
git diff 086b5ba -- backend/app/agents/dataset.py backend/tests/dataset/test_compiler_review_blockers.py
git diff f8a929a7fab2ac10ffee2a0aca112ca93a72fb2d -- spikes/payments/run.py spikes/payments/README.md backend/tests/payments/test_payment_readiness.py docs/workstreams/07-payment-readiness.md
# From frontend, using Node 24.14.1 and uv on PATH:
env PATH=/Users/nikitaafanaskin/.nvm/versions/node/v24.14.1/bin:/Users/nikitaafanaskin/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin npm run generate:check
```

Validation: **664 passed, 2 expected failures in 108.53 s** in the full backend
suite; the final focused dataset/API run had **112 passed, 2 expected failures
in 19.96 s**. All eight R7 cases pass. Ruff lint/format passes (154 Python files),
all generated contracts are current, and whitespace checks pass. One upstream
websockets deprecation warning remains.

The first focused run encountered an artifact-storage collision in the existing
concurrent run-creation test, inside `seed_registry` / `ArtifactStore.put`, before
any delivery or complaint-target construction. The unchanged test passed on its
targeted rerun, the full backend run and the final focused rerun. This intermittent
concurrent artifact-write failure is disclosed for separate follow-up; R7 does not
repair that path. R3/R4 still produce exactly two failures with `--runxfail`; they
are not fixed or waived. The compiler integration and the payment lease/recovery/
preflight limitations below remain outstanding. No independently reviewed Jeff
commit was supplied in this pass. Prompt 07's four owned files remain byte-identical
to `f8a929a`.

No frontend or contract files changed, so frontend tests, typecheck, builds and
browser smokes were not rerun for this API-only follow-up. Their earlier results
below remain historical evidence. Use the **Clean-checkout local demo** commands
below to start the mock backend on 8028 and frontend on 3028 with a fresh temporary
DB. For R7 specifically, run the new test module above; it creates and faults only
its own temporary artifacts. No private state, paid calls, live RPC, broadcasts,
push, main merge or deployment were used.

## Review mapping and evidence

| Review | Implementation and regression | Status |
| --- | --- | --- |
| R1: suppressed exact count without discriminator | `contracts/dataset.py` strictly allowlists source, manifest, coverage and authority JSON; `datasets.public_bytes` validates every JSON object, rejects unknown schemas and duplicate keys, and checks all CSV rows. Reference resolution uses the same boundary, including absence-denominator evidence. `CanvasEffects.verified` resolves citations before emitting them. | Fixed at public boundary; original bytes/hashes remain private evidence. |
| R2: accepted references disappear | Additive `CatalogOrder.evidence_answers` stores request/case, accepted buyer actor, original binding/revision, receipt time, text and up to eight references. `orders/dataset_evidence.py` enforces frozen source/current delivery identity, resolves actual bytes, and transports at most sixteen current-case references after restart. `Runs.answer` commits answer, invalidation, one job, event and exact acknowledgement together. | Fixed transport; Jeff retains interpretation. |
| R3: “Do not include yoga” expands scope | `test_compiler_review_blockers.py::test_negative_yoga_instruction_does_not_expand_scope` contains the exact reproduction and desired result. | **Not fixed. Strict expected failure; Jeff release blocker.** |
| R4: corrected cohort cannot supersede original | `test_compiler_review_blockers.py::test_question_bound_cohort_correction_supersedes_original_text` preserves original history/deadline and expects a ready 25–34 specification after the bound answer. | **Not fixed. Strict expected failure; Jeff release blocker.** |
| R5: returned/held disagreement | Shared `PaymentAccountState`, additive `payment_state_changed` effects committed with existing order/payment transactions, and `fold.ts` current state projection. Historical capture/book events remain. Legacy `state_changed.paymentState` still projects. | Fixed; no second ledger or extra transfer. |
| R6: all complaints target category | Server provides generated requirement/field/row/column targets and rejects inconsistent combinations before mutation. The existing live form now selects that target and explicit factual/scope intent. | Fixed basic data plumbing; Lucas retains visual design and row-click UX. |

Targeted baseline regressions failed before implementation: R1 returned 200 for
missing/renamed markers and unknown JSON; R2's recording assessor lacked the
Wellness passage after restart; R6 accepted all four inconsistent targets; R5's
whole LiveRun render had a voided funding panel but no returned canvas coin.
Two additional regressions caught and repaired old-command replay drift from the
additive request/column fields. No existing test expectation was weakened.

`tests/dataset/test_review_boundary.py` covers actual HTTP safe downloads for
source/coverage/authority/CSV/preview, malformed missing/renamed discriminators,
suppressed and unknown exact values, unknown JSON, duplicate keys, safe evidence
resolution, preserved original bytes, safe emitted events and historical catalog
PDF access. The emitted preview and citations are checked after real verification
of the malformed source, not just before fulfillment.

`test_review_answers.py` uses an injected recording assessor: a resolving
`yoga_category=Wellness` citation reaches its next call after service restart.
Exact replay adds no answer/job; stale/unrelated/expired/forged answers mutate
nothing. An injected acknowledgement failure rolls back the answer, invalidation,
job and events. Source repair requires actual references and keeps malformed
sources blocked; customer testimony alone remains UNKNOWN. All accepted terms,
sources and review/dispute/repair/authorization deadlines remain unchanged.
Previous findings remain in append-only events; the current semantic findings are
cleared on answer invalidation. Historical acknowledgements replay without allowing
new unbound answers. Dataset calls to the old text-only order-answer route are
rejected; retained catalog orders still use their existing route.

`test_review_payments.py` drives the existing executor with injected RPC through
funded → void_pending → voided, funded → uncertain/expired_not_returned and
captured → reorg_hold. It compares event and payment projections, restarts, checks
unchanged broadcasts and verifies one-time bookings. Separate mock-only transition
fixtures exercise the complete canvas and funding panel in
`broker-payment-states.test.tsx`. Their unusual mock states are explicitly injected
for projection testing; they are not chain observations. All mock hashes are null
and explorer links absent. Regenerate these fixtures explicitly with:

```sh
REVIEW_TRANSITION_OUTPUT="$PWD/frontend/fixtures/run-payment-transitions.json" \
backend/.venv/bin/python -m pytest backend/tests/dataset/test_review_payments.py \
  -k mock_transition
```

`test_review_targets.py`, `broker-evidence-targets.test.tsx` and the production
`scripts/review-remediation-smoke.cjs` preserve requirement, field, ZIP, optional
column and intent through the form/API/worker. ZIP 94110 reaches coverage and is
resolved against the actual delivered CSV as unsupported, with zero questions.
Scope requests remain separately offered/accepted/funded work; recording them
does not purchase anything or alter accepted terms.

## Wire handoff

Generated OpenAPI and all five client families are authoritative. New run polling
metadata: `evidence_request` (current request/case/prompt/deadline, references-required
flag and up to 32 safe frozen reference choices) and `complaint_targets` (accepted
requirement, field, allowable rows and columns). These controls are withheld until
event catch-up. Answers send `{binding,request_id,text,references}`. The nullable
request ID exists solely to replay historical acknowledgements; new submissions
without it return 409. At most eight unique resolving references are accepted.
No caller-supplied actor is trusted: the accepted buyer actor is recorded.

`payment_state_changed` carries the payment ID, display amount, mock flag, typed
current state and optional reason. It is a current-state effect, not a transfer or
booking. Consume it even after a prior `payment_captured`. `void_pending` means
return pending; `voided` means returned; `expired_not_returned` means expired but
not returned; uncertain/reorg hold must override a completed-looking money display
without erasing historical events. Order/payment metadata and event high watermark
are read coherently. Existing `state_changed.paymentState` remains compatible.

Lucas's existing layout/styles are retained. Small `ComplaintForm` and
`EvidenceAnswer` components replace hardcoded category and empty-reference
submissions. Controls reset on a changed binding/request, require explicit action,
and retain existing 409 refresh behavior. No client verdict or money authority was
added. Follow-up design tasks and Jeff's semantic expectations are in their local
handoffs; no teammate messages were sent.

## Validation

Final commands run from this worktree, with temporary/synthetic data and injected
clocks/assessors/RPC. Frontend uses Node 24.14.1, not the older system Node.

```sh
uv sync --locked --project backend
uv run --locked --directory backend pytest tests/dataset -q --tb=short -rx
uv run --locked --directory backend pytest tests/dataset/test_compiler_review_blockers.py --runxfail -q --tb=short
uv run --locked --directory backend pytest
uv run --locked --directory backend pytest tests/payments/test_payment_readiness.py --tb=short --show-capture=no
uv run --locked --directory backend ruff check . ../tools/brokerage_acceptance.py
uv run --locked --directory backend ruff format --check . ../tools/brokerage_acceptance.py
backend/.venv/bin/python spikes/payments/examples.py
uv run --locked --directory backend python ../tools/brokerage_acceptance.py --output /private/tmp/review-remediation.eYYIm1/acceptance
git diff f8a929a7fab2ac10ffee2a0aca112ca93a72fb2d -- spikes/payments/run.py spikes/payments/README.md backend/tests/payments/test_payment_readiness.py docs/workstreams/07-payment-readiness.md
git diff --check
# From frontend, with the installed Node 24 directory and ~/.local/bin on PATH:
npm ci --cache /private/tmp/review-remediation-npm-cache
npm run generate
npm run generate:check
npm test
npm run typecheck
BACKEND_URL=http://127.0.0.1:8028 BROKER_BUILD_DIR=.next-broker-production npm run build
npx react-doctor@latest --verbose --scope changed --base 35194536da06481591291f2d486725ccb448e59d --include-untracked
```

| Check | Result |
| --- | --- |
| Locked Python/frontend dependencies | Passed; no dependency/lock changes. |
| Full backend suite | **656 passed, 2 expected failures in 82.01 s.** The expected failures are the explicitly unpatched R3/R4 compiler blockers. |
| Focused dataset review regressions | Passed, apart from the two explicit compiler expected failures. |
| Compiler blockers with `--runxfail` | Exactly two failures reproducing R3 and R4; neither is claimed fixed. |
| Payment readiness reproductions | 9 passed in 0.56 s, including slow lease and unsent-submission limits. |
| Isolated lab | All 27 subprocess commands passed. |
| Offline brokerage acceptance | Conforming capture, injected missing-ZIP correction, separate funded Oakland and cited yoga resolution passed. |
| Ruff lint/format | Passed; 153 Python files formatted. |
| Frontend | 100 tests in 13 files passed; typecheck passed. |
| Generated contracts | All five client families and root OpenAPI freshness passed. |
| Production build | Passed under Node 24.14.1. |
| Production browser | Happy path and targeted coverage complaint passed against real loopback backend/Next bridge; zero page errors. |
| React Doctor against task baseline, including untracked files | No new issues, score 90 after checkbox fixes. |
| Prompt 07 preservation / whitespace | Four owned files byte-identical to `f8a929a`; `git diff --check` passed. |

One upstream websockets deprecation warning remains. A final source-repair edge
test also verifies that a source whose registered version disagrees with its bytes
is omitted from evidence choices instead of breaking polling; its original bytes
remain private and the source stays blocked.

Observed production browser evidence is under
`/private/tmp/review-remediation.eYYIm1/{browser-complete,coverage-browser-complete}`.
The ordinary journey used `request-342c255608244395850d673f029749a3`; coverage used
`request-f90ef87d0fcc43cfa8ec4146932aa568`. Chromium 156.0.8078.4 reported no page
errors. The downloaded CSV has 27 unique ZIPs, 94110 count 170, 94129 suppressed
with no exact count, and SHA-256
`72af48f698cc4857f784f51a5e75f4c017d88e5232fc3556c008f1007de0037f`.
The event page has exactly one mock capture and one books event, null transaction
hashes and no explorer links. Screenshots/CSV/events/trace are retained locally,
not committed. The offline acceptance report is
`/private/tmp/review-remediation.eYYIm1/acceptance/broker-lhr64kaw/report.json`.

React Doctor's default origin/main comparison includes eight pre-existing migration
diagnostics (score 45): panel complexity, bridge response propagation, intentional
polling, cleanup/late-state heuristics and deliberate loading resets. The bridge
forwards actual HTTP status; polling cleanup aborts, clears its timer and fences
late responses, covered by existing tests. The task-baseline comparison initially
found four new checkbox-selection warnings; stable reference keys and a Set fix
them. Its final task comparison reports **no issues, score 90**. No diagnostics
were suppressed and no global frontend refactor was attempted.

Environment-only retries: npm DNS/cache access, uv's cache from generation,
loopback server binding and macOS Chromium launch needed approved sandbox
escalation. No configuration or dependency versions were changed. Next's isolated
build rewrites next-env.d.ts; only this task's generated path change is restored
before commit. Other worktrees, including the migration's pre-existing generated
file change, were untouched.

## Payment limitations and separately scoped follow-up

Prompt 07's four owned files are byte-identical to `f8a929a`. Its nine readiness
tests and 27 subprocess examples pass on this combined tree. The shared executor,
journal and Base transport were not rewritten here.

1. **Fenced lease renewal and total operation budgets — Nikita.** The existing
   slow-RPC reproduction still takes 34 × 4 = 136 simulated seconds inside a
   120-second claim lease, without durable signing/send. Add compare-and-update
   renewal for the same unexpired ownership token, with independent short
   transactions and cancellation on lost ownership. Preserve persistence/send
   fencing. Bound the entire prepare-to-submit sequence against both elapsed time
   and original funding/capture deadlines; renewal cannot extend accepted terms.
   Test competing workers, stale completion, renewal failure and slow reads. Do
   not merely raise timeouts. Actual endpoint latency remains unmeasured.
2. **Audited exact-byte recovery — Nikita.** Crash after durable `submitted` and
   before broadcast still remains pending across ordinary reconciliation, with
   no fresh signature, nonce, salt, send or booking. Design a separate explicitly
   authorized recovery command: audit original identity/signed-byte hash, canonical
   receipt/transaction/event/state, latest and pending nonce, remaining deadlines
   and signer ownership. Reconcile matching evidence normally. Missing RPC data
   is not proof of absence. Conflicts, expiry, consumed nonce and reorg remain
   held/manual. Only a separately authorized, idempotent resend of the exact
   persisted bytes may be considered; no automatic ambiguous rebroadcast or fee
   bump. Test crash on both sides of send and response loss.

Before any separately authorized live use, resolve those recovery decisions and
measure full read-only preflight/reconciliation latency. Verify pinned deployment,
historical canonical reads, parties/domain/balances and provider non-authority as
specified in workstream 07. No observed testnet outcome is claimed. The 0.10 test
USDC lab fixture does not fund a $120 dataset order.

## Clean-checkout local demo

Use this branch's committed checkout; never copy a private .env or existing DB.
After `uv sync --locked --project backend`, terminal A at the repository root:

```sh
BROKER_DEMO_DIR=$(mktemp -d /private/tmp/datumco-review-demo.XXXXXX)
ORDER_DB_PATH="$BROKER_DEMO_DIR/orders.sqlite3" ARTIFACT_ROOT="$BROKER_DEMO_DIR/artifacts" \
INTERNAL_API_TOKEN=review-worker REVIEWER_API_TOKEN=review-reviewer \
ENABLE_PAID_MODELS=false PAYMENT_ADAPTER=mock ENABLE_TESTNET_BROADCAST=false \
backend/.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8028
```

Terminal B in `frontend`, with Node 24 and uv on PATH:

```sh
npm ci
npm run generate:check
BACKEND_URL=http://127.0.0.1:8028 BROKER_BUILD_DIR=.next-broker-production npm run build
BROKER_BUILD_DIR=.next-broker-production BACKEND_URL=http://127.0.0.1:8028 \
BROKER_LOCAL_DEMO=1 INTERNAL_API_TOKEN=review-worker REVIEWER_API_TOKEN=review-reviewer \
npm run start -- --hostname 127.0.0.1 --port 3028
```

Terminal C in `frontend` (install Playwright Chromium if absent):

```sh
BROKER_SMOKE_ORIGIN=http://127.0.0.1:3028 BROKER_SMOKE_OUTPUT=/private/tmp/datumco-review-happy \
node scripts/brokerage-smoke.cjs
BROKER_SMOKE_ORIGIN=http://127.0.0.1:3028 BROKER_SMOKE_OUTPUT=/private/tmp/datumco-review-coverage \
node scripts/review-remediation-smoke.cjs
```

The first exercises create/quote/accept/explicit mock funding/worker/CSV/reload/
capture. The second creates its own run and submits the actual coverage form,
checking the backend finding and absence of an unrelated question. Stop temporary
servers with Ctrl-C. These are local production-build checks, not deployment.
For manual intake, use the unambiguous gym/app prompt in the scripts; the negated
yoga and corrected-cohort paths remain blocked by R3/R4.

## PR-ready summary

**Title:** Close artifact, evidence transport and payment projection review gaps

Fail closed on unrecognized or unsafe aggregate artifacts, persist request-bound
evidence answers atomically and transport their resolving references after restart.
Expose typed current payment effects alongside immutable history, and bind live
complaints/answers to generated server targets. Preserve existing financial gates,
catalog/invoice/broker/improvement compatibility and historical command replay.

Includes failing-before/fixed-after HTTP and restart regressions, payment transition
fixtures, full canvas/panel tests and real production browser coverage targeting.
Jeff's compiler R3/R4 remain explicit release blockers; shared lease and exact-byte
payment recovery remain separately scoped. No live settlement or deployment claim.

Validation: 656 backend tests pass with two explicit compiler expected failures;
100 frontend tests, Ruff, generated clients, typecheck, production build, both
production browser flows, offline brokerage acceptance and all 27 lab subprocesses
pass. React Doctor finds no new task-baseline issues. Temporary servers were stopped.
