# Integrated MVP handoff

## Nikita

The original OrderService owns base authorization, ten-minute review, capture,
held disputes, expiry and additional-processing bookings. No live adapter was added.
Its create/mutate methods accept an optional existing SQLite connection so job effects
and financial transitions commit together. Original API shapes remain supported.
Additive contracts: ScopeObligation, QuoteAuthorization and projected base_order.
Signed effective scope is enforced by the original deadline/capture gates, including
when only the original sweeper is running. Base bookings are not duplicated as job
postings. Added-scope receipt/cost postings retain exact operation IDs and UNKNOWN
reconciliation; customer authorization is distinct from quote acceptance.

Review app/runtime/jobflow_base.py, tests/jobflow_runtime/test_main_integration.py
and the extended full-100 test. Production authentication and live payment adapter
remain yours. Keep both APIs local until customer authorization is integrated.

## Lucas

Frontend is connected through the same-origin /api/jobflow rewrite, generated types
and two-second polling. BaseReview consumes the original server projection/deadlines;
the browser never supplies prices to capture or chooses its own role authority.
Field citations have normalized rectangles and a hash-bound rendered-page endpoint.
The canonical PDFs remain downloadable, not substituted by screenshots.
JobMatrix and Courier have separate React keys; source inspection/replay have no POST.
Use scripts/acceptance.cjs for the real-backend browser route and tests for focus,
stale responses, retries, reduced motion and independent added-scope controls.

## Jeff / investigation

Scope investigator stays source-scoped with exact source/hash/quote validation,
independent customer/provider signatures and a two-question ceiling. The register
verifier independently reopens sources, unit artifacts, structured sidecar and actual
delivered PDF. It checks duplicate/conflicting invoices, per-currency totals, source
links and exact delivery text before constructing all eight criterion assessments.
The four-unique/six-PDF fixture is covered by a fresh regression. Hosted Anthropic
calls remain disabled without explicitly approved backend configuration.

## Review focus

The user-selected hybrid is deliberate: HACK.md v0.2 governs the base, with separate
V4 change orders for genuinely new work. One free regeneration is shared at order
level. Older prepayment databases are preserved, not silently converted. The active
demo uses a fresh v0.2 database. Root API_CONTRACT.md and RUN_INSTRUCTIONS.md describe
the extension; docs/API.md is still the original team API reference.
