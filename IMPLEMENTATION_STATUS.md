> This document describes the preserved `/api/jobflow` invoice workbench.
> Catalog/payment handoff status is in [docs/IMPLEMENTATION_STATUS.md](docs/IMPLEMENTATION_STATUS.md);
> catalog policy is HACK.md, and invoice policy is [archived separately](docs/jobflow/INVOICE_POLICY.md).

# Jobflow implementation

## V5 extension

The broker backend, actual data/PDF verification, versioned review policy, persistent
question/human paths and bounded prospective improvement loop are implemented in
the same application. Generated APIs/types and compatibility helpers are ready for
Lucas. Rebased on main `46f6c07`, preserving catalog default/payment architecture
and the existing root run canvas plus `/jobflow` frontend.
Current checks: 415 backend tests, 59 frontend tests, generated-contract check,
TypeScript, production build and real-backend browser acceptance pass. The results-first
ZIP and 12+6 evaluation are recorded in EVALUATION_RESULTS.md. Real generation is BLOCKED by missing
application configuration; deterministic infrastructure tests are not labeled live.

## V4 integrated baseline

Rebased on main `06112e2`. User resolved the base financial policy to HACK.md v0.2.

- Existing OrderService, contracts, payment policy, polling API and tests retained.
- One SQLite database; original order ledger owns base payment. Jobflow adds related
  unit state, artifacts, events, bounded provider work and separate additions.
- 100-document end-to-end regression completes original correction, accepted field
  regeneration, eight-criterion PDF verification, base capture and the $8 addition.
- Green/red/orange browser workflow, exact source checks, actual PDF rendering and
  highlighted source inspection; corrections generate new bytes and validation.
- Separate customer quote acceptance and payment authorization. Original fee path
  retains agreed prices and otherwise requires a separately accepted authorized quote.
- No base prepayment, automatic invented fees or second base settlement ledger.
- Startup recovery, deadline sweep, exact replay, stale approvals, cross-customer and
  role checks, UNKNOWN reconciliation and current-time terms remain tested.
- SDK Anthropic integration is configured explicitly and bounded by a durable cap.
  Live-model acceptance was not run: no approved key/model/call budget was supplied.
- Payments and provider execution are explicitly local/simulated. Production customer
  authentication and live payment adapter remain team-owned. No deployment occurred.
- Docker/Railway configuration supplied; container build/deployment not verified.
- Packet reference images were not available; the written job-level UI requirements
  were used. Crop/rotation beyond the synthetic portrait fixture is not yet verified.

The implementation is newly written. Earlier local behavior was inspected for
source binding, transaction, authorization and recovery requirements. No earlier
application source, runtime data or benchmark scores are imported.

See TEST_RESULTS.md, RUN_INSTRUCTIONS.md and TEAM_HANDOFF.md for verification and use.
