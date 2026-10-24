# V5 pickup and evidence

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
