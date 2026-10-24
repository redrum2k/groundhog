> This document describes the preserved `/api/jobflow` invoice workbench.
> Catalog/payment handoff status is in [docs/IMPLEMENTATION_STATUS.md](docs/IMPLEMENTATION_STATUS.md);
> catalog policy is HACK.md, and invoice policy is [archived separately](docs/jobflow/INVOICE_POLICY.md).

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

## V5 ownership handoff

- Nikita: catalog/payment handoff from main `ac385a1` is preserved. The broker reuses
  the compatibility OrderService (`orders/invoice_compat.py`) in the same DB; it does
  not replace CatalogService or the catalog journal. Review scoped v0.3 dispatch and immutable
  source/spec/delivery capture binding. Human tasks explicitly retain expired or
  uncertain authority for the payment owner; no renewal/live payment path was invented.
- Jeff: typed regional-data predicates, scoped questions/answers, incident diagnosis,
  protected proposal surface and actual isolated improvement loop are implemented.
  Real model generation still needs the existing approved application configuration;
  fixture generation and injected SDK tests are separately labeled.
- Lucas: use the generated broker/improvement DTOs, typed request helpers, current
  ownership/next-action fields, full probe/diff records and existing Event schema.
  New routes proxy through the existing Next app with separate OpenAPI schemas.
  Root catalog OpenAPI remains frozen. No broker screen redesign is imposed.
- Rehan: review the 12 development inputs and 6 reserved transfer inputs and the
  separately stored offline reference endpoints. Results include declined/unknown
  cases, real command traces and company/customer effort separately. No enterprise
  performance or payroll savings is inferred from synthetic fixtures.

Template rollback: POST `revoke` with the active `version_id` as controller, using a
new stable idempotency key. New drafts revert; existing accepted orders stay pinned.
Keep the V5 application/schema when rolling back a template. Do not replace a V5 DB
with an older parser or restore an old DB over new orders as a template rollback.

The original V4 PR is already merged at main `39538c0`. V5 is a separate feature
change on current main `46f6c07`. The user subsequently requested merging this work
with the simple subject "Add broker review and improvement workflow", preserving
the existing frontend. No deployment or live-money action was added to that scope.
See EVALUATION_RESULTS.md and updated run instructions for evidence and follow-up.

The current `/` run canvas and `/jobflow` workbench are unchanged from main. Added
frontend files are typed broker/improvement clients and generated DTOs; proxy routes
are additive. The run canvas's recorded/stub event seam remains Lucas's integration
surface, not an invented backend or payment authority. HACK.md and POLICY_DELTA.md
govern real accepted policies; older design notes mentioning 48-hour review or x402
do not replace the current catalog/broker contracts or Nikita's payment architecture.
