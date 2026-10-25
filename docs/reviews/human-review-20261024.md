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

## Follow-up: 21:03 screenshots and failed return

The pictured `request-258335e396f74b71bd7a7f641e4c3dcf` answer was received at
21:03:08 Pacific, before the fixed backend started at 21:10:14. It ran the older
questioning path. The current handler also accepts “I can't provide evidence.”
The open investigation panel now moves to Admin review when the server confirms
the transition; reviewers can still reopen the investigation history afterward.

The approval receipt now uses a compact neutral card with a separate payment
status, collapsed reviewer note, and explicit submission-failure presentation.
The active question is not repeated above its answer form.

The 21:03 return attempt failed before submission and has no transaction hash.
The original executor discarded the underlying exception text, so its precise
historical cause cannot be recovered. A fresh read-only unsigned-return check
failed on `eth_getCode`; a later direct lookup returned HTTP 200 with a result.
This reproduces intermittent RPC unavailability, not proof of the original cause.
No diagnostic signed or broadcast a transaction. Future preparation failures
retain capability-free `BaseTransportError` detail; arbitrary exceptions remain
redacted.

A regression also reproduced an older funding audit clearing a later failed
return's payment status. Funding confirmation no longer erases that failure.
Failed returns still require an explicit new action, not automatic resubmission.

Validation: dataset/payment suites passed (591 tests), frontend suite passed
(215 tests), focused handoff UI tests and TypeScript passed after the final
navigation change, Ruff/diff checks passed. Desktop/mobile browser replays checked
pending, confirmed and failed receipts. React Doctor reported no diagnostics;
changing concurrent scan scope makes its numeric scores incomparable. The backend
was reloaded with unchanged live settings under the user's existing authorization.
