# Current aggregate integration pickup

Latest correctness pass: [BROKER_RECOVERY_REMEDIATION.md](BROKER_RECOVERY_REMEDIATION.md).
Fresh Greptile review of `9bff90c` found a numeric-consent P1: `yes, 65+` lost its
qualifier and could create unsupported ready terms. Test-first commit `2146cde`
reproduces 21 failures / 5 controls; fix `3f90ad5` preserves numeric/symbolic
qualifiers, with 332 focused tests passing. Full backend: 970 pass / the exact
same 16 Windows failures. The report preserves original broker-fix evidence
separately. No paid calls; the shared API ledger hash remains unchanged.
The two subsequent Greptile findings on `e60aa6f` were reproduced before fixing:
accepted amendments now fulfill through the shared successful-verification helper;
pending dispute work and command receipts now commit atomically. The existing
backend worker recovers known-unsent work; uncertain attempts are never retried.
Backend fixes: `ba79817`; frontend integration: `e45ddde`, importing Lucas's PR #20
from main `3d69b92` unchanged. Focused tests: 44 pass. Frontend: 120 tests plus
generated-contract checks, TypeScript and build pass. Full-suite evidence is in
the current report. The earlier three P1 fixes remain preserved at `43cb18c`.

Next: inspect the fresh Greptile review for PR #12 at its exact head, resolve any
backend findings, and recheck main before merge. Main merges automatically create
`calm-serenity / production` deployments; do not merge until that consequence is
explicitly resolved against the prior no-deployment boundary. Upstream PR #20's
inspector colors UNKNOWN citations as failures; flag for Lucas, do not silently
rewrite his frontend. No new paid calls or spending-window extension is authorized.
The existing $45 ledger and historical qualification evidence remain unchanged.
For new outbox work recovery is automatic while eligible; old pre-outbox receipts
are adopted only by exact replay in an unambiguous OPEN/current-PASS state. Old
UNKNOWN/question or FAIL/correction receipts retain their completed effects.

Read [AGGREGATE_MODEL_QUALIFICATION.md](AGGREGATE_MODEL_QUALIFICATION.md) first:
30 actual Claude Opus 5.5 calls, preserved negative pilot results, fresh post-fix
dispute/intake qualification, cumulative costs and model features OFF by default.
[AGGREGATE_INTEGRATION.md](AGGREGATE_INTEGRATION.md) retains the prior integration
checkpoint and exact event seam. Branch `feature/aggregate-intake-integration-20261024`,
PR https://github.com/redrum2k/order-to-cash/pull/12 targeting main. Do not self-merge.
Latest frontend and Human naming are preserved. The user's separate 90-minute
qualification window runs conservatively from 12:52 to 14:22 Pacific on October 24.
Old windows/spending were not reset. Real API evidence is distinct from injected
tests; no production/shared-main enablement or merge into main occurred.
Integration commit `3a15bd8` brings main `b177d53` into this feature branch only.
Qualified semantic components are unchanged; newer payment/frontend work is retained.

The original semantic evidence in [PRIMARY_HANDOFF.md](PRIMARY_HANDOFF.md) and
[PRIMARY_RESULTS.md](PRIMARY_RESULTS.md) is frozen history, not current integration
instructions. Earlier local branches/worktrees/archives remain intact. The sections
below preserve historical context; current counts/commands/ownership are in the new
integration handoff, not the old V5 assertions.

## Completed legacy dispute follow-up

The backend dispute follow-up is delivered **feature OFF / not qualified**.
Read [DISPUTE_HANDOFF.md](DISPUTE_HANDOFF.md) and [DISPUTE_RESULTS.md](DISPUTE_RESULTS.md)
for current state, verified calls/tests, remaining blockers and the expired-or-bounded
authorization window. The V5 handoff below is preserved historical evidence, not the
current qualification result; no V6 evidence or original clock was reset.

# V5 pickup and evidence (historical)

This change adds source-checked broker review, bounded questions/human handoff, and
an application-run prospective improvement loop. It integrates current main
`46f6c07` without replacing its catalog/payment architecture or frontend.

## What is verified

- 415 backend tests; Ruff check/format (123 files).
- 59 frontend tests in 10 files, generated drift, TypeScript and production build.
- Catalog root OpenAPI exactly matches the frozen main schema.
- Both existing screens remain main's code: Lucas's canvas at `/`, invoice workbench
  at `/jobflow`. No replacement component, screen, style or UI dependency is added.
- Real-backend invoice browser acceptance: 100 original jobs validated, held base,
  separate 800-minor-unit addition paid, no replay mutations or JavaScript errors.
- Live same-origin checks: both screens and all three mounted OpenAPI routes return
  200; an authenticated improvement-view request works through Next.
- Actual final broker PDF is one page, visually inspected without clipping/overlap.
- Two candidates, one rejected; 12 development and 6 reserved transfer worlds;
  all three arms have 18/18 endpoint and 18/18 financial matches. Approval,
  activation, experience reuse, revoke/restart and immutable accepted versions work.

These are deterministic synthetic application-command results, not live-model
quality or real settlement. Missing approved model/key/allocation leaves real model
generation BLOCKED with zero calls. Details and negative findings:
EVALUATION_RESULTS.md, WORK_LOG.md and IMPROVEMENT_DESIGN.md.

## Evidence locations

The results-first ZIP was delivered within the user's 30-minute limit:
`D:\Downloads\OBJECTION_V5_Results_20261024.zip`, 3,198,759 bytes. Its immutable
completion manifest records pre-rebase revision `150dab9`; it must not be relabeled.

The later integrated run is `D:\Downloads\OBJECTION_V5_Integrated_20261024`,
executed at `c85d9cc`. The frontend-only rebase and proxy fix leave its backend/lockfile
fingerprint unchanged:
`fa1b5bb680a3dc83bbf92ed299ebb05c7a662d4e08cfe979708643a9205a39ab`.
Reuse these results unless the implementation changes. The runner rejects an
existing output directory. A new run must preserve earlier failures.

## Contracts and integration decisions

Catalog stays default with its existing funding/journal/60-second policy.
Invoice v0.2 remains isolated. Broker-review-v0.3 is a separate 600-second accepted
profile: PASS opens review; acceptance or undisputed expiry plus current complete
verification and exact unexpired authority permit capture. UNKNOWN/disputes hold;
one free correction, two questions, 1,800-second case bound. Added work needs its
own accepted offer and authorization. No automatic fee, renewal or live payment.

The broker reuses `orders/invoice_compat.py` and `runtime/invoice_policy.py`;
the catalog financial authority is untouched. All share the app/DB, with mounted
`/api/jobflow`, `/api/broker` and `/api/improvements` schemas. Historical unrelated
rows stay read-only. New proxy routes are additive; the exact improvement-root
rewrite avoids an auth-losing slash redirect. Scoped LF attributes preserve pinned
payment hashes and generated-schema comparisons on Windows.

Read API_CONTRACT.md for broker/improvement DTOs and RUN_INSTRUCTIONS.md for commands.
Existing run-canvas events are still recorded/stub data owned by Lucas, not silently
connected to the broker or relabeled as live learning. HACK.md/POLICY_DELTA.md govern
accepted policies; old UI design notes do not replace them with 48-hour review/x402.

## Remaining owner work

1. Lucas + Nikita: connect the existing run-canvas event/action seam to the chosen
   real backend profile using its exact identities, revisions and deadlines. Keep
   recorded/stub versus actual application evidence distinct.
2. Jeff: if existing approved application access becomes available, run the bounded
   real-model evaluation and report it separately. No new spending is authorized.
3. Rehan: independently review finite fixture labels and sponsor requirements.
4. Nikita: production identity and any separately authorized live-payment milestone.

The user subsequently requested a main merge with the short subject
"Add broker review and improvement workflow", explicitly preserving existing UI.
No deployment, live transfer, new budget or destructive cleanup is included.
Do not repair RAP/Goal Autopilot or reopen the resolved financial-policy decision.
