# PR #12 — accepted scope and durable dispute dispatch

This focused follow-up addresses Greptile's two findings on `e60aa6f` in the
retained `broker-review-v0.3` path used by Lucas's animated demo. It does not change
aggregate intake contracts, prices, payment execution, model budgets or feature
defaults. No real Claude calls, real broadcasts or shared procedure activations.

Tested backend: **`ba79817191449cd64fb9b096788c81c739128264`**.
Final frontend integration: **`e45ddde81e8abac8b7c96b53d9831eca1c241a4a`**;
the backend tree is identical to the tested backend commit.
Test-first commit: `30ddd34`, on the unchanged `e60aa6f` runtime.
Main integration: `01429b7`, importing **`f5cc8ed5b9b9d1bb2d57f7716ce937a3d0ec3abc`**,
including Lucas's PR #19 dispute mapping, PR #14 customer guide and orb styling.
Those frontend files were imported intact, not replaced or edited by this fix.
The later integration imports main **`3d69b92181327b7ebf44324e0fdb3603008a1c2c`**
(Lucas's PR #20 customer guide/inspector). Its eight frontend files are likewise
unchanged from main, and frontend checks were repeated after that integration.

## Finding 1 — resolved complaint with unfulfilled accepted scope

[Greptile finding](https://github.com/redrum2k/order-to-cash/pull/12#discussion_r4368486065).
The model-enabled `_verify` branch returns before the normal PASS branch fulfills
effective `scope_obligations`; the later `NO_REMEDY` branch did not perform that
update. A factual refutation could therefore coexist with an unfulfilled accepted
amendment, and the existing customer-acceptance gate correctly refused settlement.

The regression uses real accepted sources, mutually accepted source-amendment
commands and compliant regenerated PDF/data/sidecar bytes. A fixture seam defers
verification of those bytes so the test can exercise the pending-verification
state. It does **not** inject PASS, fulfillment, consent or a financial outcome.
The normal verifier passes the control; the model-enabled branch leaves the
accepted obligation unfulfilled on `e60aa6f`.

`Broker._fulfill_verified_scope` now shares the original effective-obligation
update between normal PASS and validated `NO_REMEDY`. It requires current complete
passing verification before marking currently effective obligations fulfilled.
It does not waive or alter the customer-acceptance/capture gates, accepted terms,
future-effective obligations, deadlines or correction limits. Re-verification
also repairs an already-resolved pre-fix record without another model call.

Tests prove the snapshot/deadline remain unchanged, no model decision books money,
the correction allowance is unchanged, and only the customer's subsequent explicit
acceptance creates the existing single mock booking.

## Finding 2 — receipt committed, assessment never dispatched

[Greptile finding](https://github.com/redrum2k/order-to-cash/pull/12#discussion_r4368486066).
The old command receipt committed before `run_assessment` created an attempt.
A process interruption in that gap left no durable work. Replay returned the
receipt and skipped dispatch forever. Fault injection reproduced zero calls after
replay/restart, including an actual backend-lifespan restart without client replay.

The correction adds a small transactional outbox, `br_assessment_work`, **inside
the existing jobflow SQLite store**. It reuses the existing attempt table, command
receipts, worker ownership and supervised background lanes. It is not another
ledger, external queue, timer service or general workflow framework. An attempt
alone cannot represent the old gap: no attempt exists until dispatch acquisition.

For a verified assessment-capable command, pending work and its immutable receipt
commit together. The work binds actor/causal identity, issue, broker/order revisions,
proposal binding, effective specification hash and evidence digest. Claiming work
and inserting its `DISPATCHED` attempt are one write transaction. Model I/O remains
outside that transaction. Concurrent replay/recovery cannot send twice.

| Work state | Recovery behavior |
| --- | --- |
| `PENDING` | Replay or the backend worker may claim once, only while the original binding, verification and deadlines remain current. |
| `DISPATCHED` | May have reached the transport. Never automatically retry, even if no raw response is saved. |
| `COMPLETE` | Outcome and attempt are recorded; receipt replay remains identical. |
| `DEDUPLICATED` | A historical/current attempt already covers the same information; preserve it without another call. |
| `CANCELLED` | Binding/verification/authority expired or changed before dispatch; no call or financial effect. |

The existing backend supervisor drains bounded pending work on startup and later
ticks. GET/order/event polling does not dispatch. Turning the feature off leaves
work undispatched. Ordinary provider errors retain the existing bounded failure
handling; uncertain process interruptions retain their durable attempt instead of
being treated as free retries.

Explicit replay can also recover a **pre-outbox** receipt, but only when its saved
binding/verification still matches the current case and its OPEN/current-PASS state
proves it was awaiting this model path (the deterministic PASS path would have
resolved the complaint). Historical receipts with UNKNOWN/FAIL may instead have
completed by asking a question or reserving a correction; turning the feature on
later must not reinterpret those completed effects. They require a new valid
command if further investigation is wanted. This restriction applies only to
pre-outbox adoption, not new durably acknowledged pending work. Historical receipts are not
mass-scanned or reinterpreted. Existing uncertain attempts are still deduplicated.
Changed evidence requires a new valid command; an old receipt cannot authorize a
new interpretation. No old receipt or accepted snapshot is rewritten.

There remains an unavoidable crash boundary after the durable `DISPATCHED` marker
but before an actual network send. That state is conservatively uncertain, not
proof of dispatch or proof of non-dispatch; automatic retry is intentionally absent.

## Reproduction and validation

`backend/artifacts/broker-recovery-20261024/valid-reproductions-e60aa6f.xml` records
**3 failures / 1 passing control** before production edits. The expanded upgrade
checks initially found three additional manifestations of the same defects:
already-resolved scope, a pre-outbox receipt, and auditing an old uncertain attempt.
These are preserved in `upgrade-before.xml`, not overwritten by the fixes.

- Final focused amendment/dispatch suites: **44 passed**, including all 19 new
  regressions and the original 25 dispute-assessment cases.
- Earlier broader broker/runtime/API check: **180 passed / 1 known Windows failure**
  (the `.venv/bin/python` portability test). The final full run covers the later
  compatibility additions too.
- Ruff lint/format: **210 files passed**.
- Frontend with Lucas's latest main: **120 tests / 19 files passed**; generated contracts,
  TypeScript and production build passed. No public DTO changes in this follow-up.
- Full backend: **944 passed / 16 failed / 0 skipped / 0 errors** (960 tests,
  382.56 seconds). `full-final.xml` covers the final `ba79817` backend tree,
  unchanged by frontend-only integration `e45ddde` during the run.

All 16 failure IDs exactly match the prior normal full run in
`docs/evidence/greptile-p1-20261024.json`: three evaluator Windows encoding/child
environment failures, eleven payment HTTP subprocess failures, one POSIX-mode
assertion and one `.venv/bin/python` portability failure. Thus all original 13
Windows/payment failures and the three evaluator failures persist; there are no
new failing test IDs. This is **not** a green full-suite claim. Nikita's evaluator
and payment files were not modified or tested with replacement assertions.

Portable counts, raw JUnit hashes, exact failure IDs and integration/budget evidence:
[broker-recovery-20261024.json](docs/evidence/broker-recovery-20261024.json).
The shared cumulative ledger SHA-256 remains
`000cfe72360895d2ae1c0fec6ed6023499d31bcbcb265ea699930f4a23b7fad5`,
identical before and after this pass; no real API call was made.

No existing test was removed, weakened, skipped or changed. New regressions cover
receipt rollback, restart/replay, actual worker-lifespan recovery, concurrent workers,
unknown outcomes with/without raw bytes, feature-off and read-only behavior, stale
evidence, all original cutoff categories and legacy receipt compatibility.

Fixture-development artifacts are retained separately. Early amendment fixtures
failed for real report/specification mismatch or complaint clearing during ordinary
regeneration; they were not treated as proof of the reported defect. An attempted
amendment before any delivery binding exposed a separate pre-existing `NoneType`
binding failure; this pass does not claim that pre-delivery workflow is qualified.
The first implementation run also caught a missing helper import; Ruff and the
existing normal-verification tests now guard it. These exploratory failures are
distinct from the valid test-first reproduction and final results.

An additional attack on the upgrade path found that a completed deterministic
UNKNOWN/evidence-question receipt could be reinterpreted after enabling the model
feature. `legacy-question-before.xml` preserves that failed regression on `36e9eb8`.
The stricter legacy-origin guard fixes it; both UNKNOWN/question and FAIL/correction
controls pass in `focused-origin-guard.xml`. New durable pending work is unaffected.

## Integration and merge boundary

Lucas's `dispute.assessed` mapping consumes the unchanged event shape, quotes
references as evidence and labels validated model decisions in its text. Its
documented compatibility choice to keep the canvas typed `decidedBy` field as
`rules` was preserved; no frontend provenance rewrite was made here. Customer
actions still go through the existing backend acceptance/payment checks.

Review caveat in upstream PR #20: `Inspector.lookFor` groups `unknown-*` citation
IDs with `fail-*` and returns `failed: true`, which colors an evidence gap as a
failed contract check. This conflicts with the frontend instruction to distinguish
evidence gaps from operational failures. It is pre-existing in the imported main,
not a backend regression, and remains a Lucas-owned presentation issue; this pass
does not rewrite his inspector or claim a visual/UNKNOWN qualification. The current
inspector tests cover FAIL but do not independently qualify UNKNOWN presentation.

Nikita's payment/runtime execution and lab files are unchanged. The only shared
startup change adds the bounded broker-assessment operation to the existing
supervisor; its shutdown draining and payment stop hook remain intact. All prior
[P1 corrections](GREPTILE_P1_REMEDIATION.md) and
[real Claude qualification evidence](AGGREGATE_MODEL_QUALIFICATION.md) are preserved.
This pass uses injected assessors and temporary mock stores, not new paid evidence.

Main merges have a production consequence: GitHub records a successful deployment
of `f5cc8ed` to **`calm-serenity / production`** (deployment `7304383666`, created
20:56:34 UTC, success 20:57:21 UTC, October 24). Other recent main merges show the
same pattern, including a production deployment record for PR #20 / `3d69b92`
(`7304755498`, created 21:30:01 UTC). Therefore this PR must remain unmerged until fresh review is complete
and the production-deployment consequence is explicitly resolved under the prior
no-deployment boundary. No main merge or deployment was performed by this pass.
