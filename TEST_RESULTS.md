> This document describes the preserved `/api/jobflow` invoice workbench.
> Catalog/payment handoff status is in [docs/IMPLEMENTATION_STATUS.md](docs/IMPLEMENTATION_STATUS.md);
> catalog policy is HACK.md, and invoice policy is [archived separately](docs/jobflow/INVOICE_POLICY.md).

# Integrated v0.2 verification

Date: 2026-10-23 local. Base: origin/main 06112e2. These are fresh branch results,
not imported qualification scores.

| Gate | Result |
| --- | --- |
| Backend full suite | 224 passed in 49.44s |
| Ruff | All checks passed; 54 Python files formatted |
| Frontend unit/integration | 29 passed across 6 files |
| Generated schema / TypeScript | Passed |
| Next production build | Passed; app, not-found and icon routes generated |
| Real browser | Edge 156.0.4314.42; 1280x720 and 1440x900 |
| Browser errors | No uncaught JavaScript or console errors in final run |
| Source/PDF review | Highlight matched invoice number; all 7 register pages inspected |

The connected 100-document regression completes 20 original retries, one included-field
regeneration for 80 remaining units, actual register verification, one base capture,
and separately accepted/authorized/paid/fulfilled/accepted four-field additions.
Final state COMPLETE: received and recognized 10800 minor units, liability zero,
correction cost 100, original denominator 100. Existing valid outputs are not retried.

The browser case confirms 79 green, 20 red and 1 orange initially; all 20 failures
then validate. The disputed base remains held while the separately authorized $8
addition is paid; received 800, earned zero, liability 800, correction cost 20.
Source drilldown, highlighted rendering, verified PDF bytes, reload and replay run
against the actual backend. Inspection/replay produce zero mutation requests.

Other checks cover early eight-criterion capture, acceptance/cutoff, held disputes,
independent expiry, original API compatibility, existing worker-token boundaries,
agreed fees versus accepted quotes, separate payment authorization at execution,
signed future obligations in the original sweeper, duplicate requests, stale approval,
two-question limits, source/hash mismatch, UNKNOWN reconciliation, restart/recovery,
and bounded free regeneration. The four-unique/six-PDF fixture handles a duplicate and
conflicting versions, excluding the conflict from totals without losing coverage.

Live Anthropic acceptance was not run without configured approved access. The actual
SDK path has mocked transport/budget/boundary tests. No live settlement or deployment
was attempted; container/Railway packaging is provided but not container-built here.
Synthetic portrait PDF coordinates were inspected; arbitrary crop/rotation is not
claimed verified. Run commands are in RUN_INSTRUCTIONS.md.

Release secret scan and remote commit verification are recorded in the draft PR.

## V5 and current-main integration

October 24, 2026: 415 backend tests passed in 155.83 seconds; Ruff check/format pass
(123 files). Latest frontend: 59 tests across 10 files, generated drift, TypeScript
and Next production build pass. Main `46f6c07`'s existing screens/styles/components
are preserved. Root catalog OpenAPI equals the frozen main schema.

The 12-development/6-transfer improvement run passes all endpoint/financial checks
across static, memory-only and evolving-process arms. A bad candidate is retained as
negative evidence; actual approval/activation, experience reuse and rollback run.
Browser acceptance at `/jobflow` validates all 100 original jobs, held base/separate
paid addition, no replay mutations or JavaScript errors. Final broker PDF visually
passes as a one-page source/methodology report. See EVALUATION_RESULTS.md for exact
counts, modes, preserved failures, source fingerprints and the early results ZIP.
