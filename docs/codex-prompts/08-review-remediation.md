# Nikita — close runtime review gaps before the next milestone

The review of conversations 06/07 did not pass. This is the corrective next task
for Nikita's API, persistence, evidence transport, artifact access, event contracts
and payment observability responsibilities. Do not begin deployment or claim live
payment success. Read the review at
`/Users/nikitaafanaskin/Documents/Developer/order-to-cash/docs/reviews/06-07-thermo-nuclear-review.md`
and the runnable test guide at
`/Users/nikitaafanaskin/Documents/Developer/order-to-cash/docs/TEST_PLATFORM_NOW.md`.

## Baseline and ownership

Inspect status, worktrees and ancestry. Start an isolated worktree/branch
`codex/review-remediation` from `35194536da06481591291f2d486725ccb448e59d`, or a
reviewed descendant retaining it. Do not use the original checkout's `ac385a1`
main. Do not reset or modify another active worktree. The combined baseline
includes migration `1956f18`, payment-readiness `f8a929a` and validation `3519453`.
The migration worktree already had a generated `frontend/next-env.d.ts` change
when reviewed; preserve teammates' changes.

Read AGENTS.md and nested instructions, HACK.md, docs/responsibilities.md,
docs/PAYMENT_SPIKE.md, docs/PAYMENT_RUNBOOK.md, workstreams 04/06/07 and current
Nikita/Jeff/Lucas handoffs. Shared DTOs and narrow frontend data plumbing need
compatible tests/examples. Do not redesign Lucas's UI or replace Jeff's semantic
subsystem. You are not alone in the repository; preserve and integrate others'
changes without requiring a blanket teammate-approval gate.

## 1. Repair the public artifact boundary (review R1)

Reproduce the malformed-source case: a registered source without `count_unit`
contains `{zip:"94129",count:42,status:"suppressed"}`. Verification rejects it,
but the current artifact route returns its exact count.

Make public access select and validate an explicit allowed artifact kind using
trusted metadata/strict schemas. Support legitimate coverage and authority JSON
without treating arbitrary JSON as safe. Unknown/malformed datasets must be
withheld even when the discriminator is missing or renamed. Keep original bytes
and hashes as private evidence. Downloads, citation resolution, previews and
events must not reveal unsafe suppressed values. Do not fix this by deleting
evidence or hiding only the UI column.

Add endpoint-level tests for safe source/delivery downloads, malformed JSON with
missing markers, suppressed/unknown exact values, and intact historical PDF
access. Nikita owns the boundary; coordinate dataset schema meaning with Jeff.

## 2. Persist and transport actual evidence answers (review R2)

Introduce additive typed evidence-answer storage recording request/case identity,
actor, original binding, timestamp, text and resolving references. Commit it
atomically with the existing idempotent acknowledgement, evidence invalidation,
event effect and queued job. Retain exact request/response replay. Reject stale
or unrelated answers without mutation. Keep all original deadlines.

Supply those persisted references as bounded current evidence to the investigator
after restart. A resolving `yoga_category=Wellness` answer must be present in the
next evidence bundle; merely storing its text or fingerprint is insufficient.
Customer testimony is not source authority. Do not mutate accepted source
editions/terms from an answer or treat cited evidence as purchase consent.

Jeff owns interpretation of the passages. Define/test the transport seam with an
injected assessor that records its inputs. Preserve conservative abstention if
the new evidence still cannot resolve the claim. Give Lucas the generated answer
DTO and reference-selection requirements; the current browser always sends an
empty references array, which cannot satisfy a source-repair request.

## 3. Make financial event state usable throughout the UI (review R5)

Ensure current payment state is represented by an explicit, typed, transactionally
persisted effect/consistent polling projection. Preserve append-only history and
one-time ledger effects. A voided payment must not remain displayed as held;
expired-but-not-returned must not become returned; uncertainty/reorg hold after a
prior completed event must remain visible without deleting history or sending
another transfer.

Agree the wire semantics with Lucas through generated contracts and transition
fixtures. Make only necessary event/data plumbing changes within this task; Lucas
owns the visual projection. Add replay tests from funded to void_pending to
voided, funded to uncertain/expired, and captured to reorg_hold. Exercise the whole
canvas projection and funding panel together, not only individual state headings.
Mock receipts keep null transaction hashes and no explorer links.

## 4. Preserve complaint targets and hand off semantic fixes

For R6, specify/validate consistent requirement, field, row/cell and intent on the
server and generate the frontend contract. A coverage complaint about ZIP 94110
must reach the coverage check, not an unrelated yoga question. Give Lucas an
actionable task to replace the form's hardcoded R-CATEGORY/category/dataset values
and distinguish scope requests. Preserve current-binding/idempotency handling and
the existing investigation limits.

Jeff owns R3/R4 in `app/agents/dataset.py`: negated "include yoga" must not expand
scope, and question-bound corrections must supersede rejected cohort text while
retaining history/deadlines. Provide exact reproductions from the review and
integration-test expectations. Do not silently take over compiler semantics or
report these findings fixed without a tested patch. Integrate completed teammate
fixes by their exact reviewed commit when available; otherwise identify them as
remaining release blockers in the handoff. No messages to teammates are authorized
by this prompt; write local handoff files.

## 5. Keep payment readiness claims precise

Prompt 07 completed its authorized offline scope. Its slow-RPC lease expiry and
crash-before-broadcast limitations are existing shared-runtime work owned by Nikita,
not hidden fixes in the lab. Rerun its reproductions on the final combined tree.
Document a separately scoped follow-up for fenced lease renewal/total deadline
budgets and an audited exact-persisted-byte recovery operation. Do not fold a
large payment-executor rewrite into these review fixes, remove fencing, increase
timeouts blindly, reset payment identities/nonces, or introduce automatic ambiguous
rebroadcast. Keep live execution blocked pending the required measured preflight
and recovery decisions.

## Acceptance and handoff

Use temporary databases, synthetic evidence/keys, injected RPC/assessors/clocks.
Add meaningful regressions for the failing cases before fixes. Run focused tests,
the complete backend suite, Ruff, all generated-client freshness checks, frontend
tests/typecheck/build and the production brokerage browser smoke. Preserve
catalog, invoice/jobflow, broker-review-v0.3 and improvement regressions.

Baseline evidence to beat: 615 backend tests and 88 frontend tests passed, along
with the ordinary production browser happy path, but all six targeted probes
reproduced defects. A green existing suite alone is not acceptance.

Write docs/workstreams/08-review-remediation.md mapping R1–R6 to code/tests or
explicit owner/blocker, exact commands/results, remaining payment limitations and
clean-checkout demo instructions. Commit only task-owned changes locally. Return
branch/SHA and a PR-ready summary. Do not push, merge main, access private state,
invoke paid models, broadcast, create wallets, transfer funds or deploy.
