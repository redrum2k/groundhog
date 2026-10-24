# V5 results-first handoff

The bounded offline run at source revision `150dab924f107eefa7653301eb32fd61e03bdd76`
passed. Evidence is in `D:\Downloads\OBJECTION_V5_Results_20261024`; the portable
handoff is `D:\Downloads\OBJECTION_V5_Results_20261024.zip`. Start with the ZIP's
`COMPLETION_MANIFEST.json`, then `evidence/result.json` and `evidence/offline-score.json`.
The manifest distinguishes reused verification from the newly executed offline run.

## What works

- Typed, mutually accepted broker specifications; source-bound JSON/CSV/PDF checking;
  green/red/orange workflow; bounded questions and free correction; owned human holds.
- New broker PASS opens 600-second review, not capture. Current complete verification,
  the accepted review trigger, exact amount and independent authorization are required.
  Accepted invoice v0.2 remains separate. Additional work requires its own acceptance
  and authorization. No live payment or automatic new fee was introduced.
- The application's deterministic improvement mechanism generated two candidates,
  rejected the vague-question candidate, probed/approved/activated the retained one,
  reused recorded experience in a second proposal, and verified revoke/restart.
- Twelve development and six reserved transfer worlds match all expected endpoints
  and financial effects in static, memory-only and evolving-process arms. Historical
  ambiguous contracts stay UNKNOWN. Accepted versions survive rollback unchanged.
- Reused integrated verification: 341 backend tests; 32 frontend tests; generated-type
  drift check; TypeScript; production frontend build; Ruff check/format. Four genuine
  acceptance counterexamples are fixed with regressions retained.

## What the results mean

These are synthetic deterministic application-command runs, not real-model quality
or enterprise accuracy results. All three arms achieve 18/18 expected endpoints and
18/18 financial effects. The process candidate reduces scripted intake intervention
events from 30 to 0 in development and 18 to 3 in transfer; required review tasks and
customer-answer counts do not change. These counts are not measured staff time or
dollar savings. Second-cycle effectiveness is not qualified. Real application-model
generation is BLOCKED: no approved key/model/allocation is configured; zero calls ran.

## Integration state and decisions

The feature is `feature/grey-area-reduction-v5-20261023`, based on main `39538c0`.
Newer main `ac385a1abf1ce66dfd1f792cac021cfa5286d7ae` arrived during implementation.
It makes catalog/payment handoff the default and moves invoice compatibility into
`backend/app/orders/invoice_compat.py` and `runtime/invoice_policy.py`. No rebase or
merge has begun. The ZIP includes both exact source snapshots for comparison.

Preserve the newer catalog product, its catalog-v0.3 60-second policy, payment journal,
API and DTOs. Do not replace these with the feature's older OrderService/main.py.
Broker-review-v0.3 is a separate accepted 600-second profile, not a migration of
catalog or invoice terms. Keep one app/DB and existing financial authority. Lucas
owns UI design. No new paid budget, chain broadcast, deployment or auto-merge.

The Harness2 audit and build-versus-borrow decision are in IMPROVEMENT_DESIGN.md:
use the small typed adapter and existing application primitives, not an imported
executor, arbitrary code mutation or expanded credential authority. Gold remains
under evals/expected, never in runtime/model context.

## Negative findings and gotchas

- The rejected candidate causes acceptance/completion regressions; its full probe
  remains in evidence/probes. Do not remove failures from the denominator.
- The acceptance worker found cutoff bypass, stale questions, cross-source duplicate
  entities and stale human-task evidence. Its historical red report is retained in
  the packet; WORK_LOG.md records the fixes and the green integrated suite.
- An old worker's deadline-test observer missed a persisted capture. The existing
  test later passed unchanged on the integrated tree; no timeout was weakened.
- The runner refuses an existing output directory. Reuse this completed run; if a
  changed implementation needs another run, use a new named directory and preserve
  this evidence. Approval binds the backend/lockfile hash, so source changes require
  fresh probes; do not relabel these results as evidence for a later revision.

## Ordered remaining work

1. Read current-main AGENTS.md/HACK.md/CONTEXT.md and its payment/interface documents.
   Rebase on current main, preserving the catalog default and invoice compatibility.
   Port profile extensions to the moved compatibility seams without restoring retired
   root invoice routes or overriding catalog financial controls.
2. Run required merged regression/type/build checks once the integration changes.
   Keep broker, legacy invoice and catalog policy tests distinct and intact.
3. Render/inspect the actual result PDF and run existing browser acceptance. Neither
   visual polish nor browser evidence is a prerequisite for this results ZIP.
4. Reconcile final docs, inspect the sanitized diff, push only the feature branch,
   and verify the remote SHA. Do not auto-merge. No push has happened for V5 yet.
5. Real-model evaluation requires existing approved application access to be available;
   do not create spending authority. Keep that status separate from local completion.

Do not repair RAP/Goal Autopilot or repeat the old WAITING_HUMAN checkpoint. The user
prioritized this under-512-MB ZIP within 30 minutes, then continuation of remaining work.
