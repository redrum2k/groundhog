# Evidence answers and human-review continuity

Read-only inspection of the actual port-8000 database found that the customer's
no-additional-evidence answer was saved, but still queued another investigation.
The 20:51 Pacific case received two answers and reached human review on its
original deadline. Its reviewer approval was recorded at 20:51:59, followed by a
confirmed return in the application at 20:52:29. The UI continued showing the old
review controls during that return and omitted a decision receipt after closure.
These are persisted application observations, not an independent chain audit.

## Changes

- A complete first-person statement that no evidence can be supplied ends bounded
  questioning immediately. The answer and human handoff commit atomically, without
  another model call/job, changed deadline, factual verdict or payment operation.
  Conditional, quoted and mixed assertions continue through investigation.
- Evidence requests introduce the requested material conversationally, preserving
  the original evidence description. An explicit “I don’t have this evidence”
  action submits the same bounded answer command.
- Human review stops the investigation spinner. Reviewer decisions remain visible
  through pending and confirmed returns, including replay of historical events.
  Return approval is distinct from confirmation; factual findings are unchanged.
- Poll failures retain the last confirmed display, disable mutations and retry.
  Admin review remains accessible for its recorded decision after order closure.

## Validation

- The new backend handoff and frontend review tests failed before the fixes.
- 743 backend tests passed across dataset, catalog, investigation, payments and API.
- 196 frontend tests passed; TypeScript, changed-file Ruff and diff checks passed.
- React Doctor reported no diagnostics; its final score service was unavailable.
- Browser replay of the actual saved return verified persistent pending/confirmed
  receipts on desktop and mobile. All browser API mutations were blocked. Temporary
  replay artifacts are in `/tmp/human-review-browser`.

The user explicitly approved restarting the existing live backend with its existing
paid-model and Base Sepolia settings. The existing launcher/configuration, database,
model ledger, budget and cutoff were retained. No new demo order, model evaluation,
manual payment operation, deadline reset or historical-data rewrite was performed.
