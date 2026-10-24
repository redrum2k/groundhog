# Pickup: broker dispute assessment (feature remains OFF)

Branch: `feature/broker-dispute-assessment-20261024`, based on `c2f5619`.
Read DISPUTE_RESULTS.md first. This is a negative/partial qualification delivery,
not V6 continuation or a production release. V6 source/archive remain intact.

## Implementation seam

- `backend/app/runtime/dispute_assessment.py`: issue-scoped evidence acquisition,
  exact JSON cell bundle, one logical attempt per meaningful snapshot, model call
  outside transactions, commit binding/deadline checks and conservative support.
- `backend/app/runtime/broker.py`: optional integration after explicit investigation/
  answer/controller-resume commands; no model calls from GET/replay/navigation.
- `backend/app/contracts/dispute.py`: raw candidate, validation and effective event.
- `backend/app/storage/broker.py`: non-authoritative durable attempt audit; effective
  state stays in existing broker/base order and event stream.
- `backend/app/agents/{budget,bounded_client}.py`: selectively ported V6 shared-dollar
  controls, plus audited separate authorization windows/allocation history.

Use `CLAUDE_MODEL`, never `OBJECTION_MODEL`. Private credentials stay in the ignored
original `C:/Users/sajee/order-to-cash/backend/.env`; no copy is in this worktree/export.
The existing enablement is `ENABLE_PAID_MODELS=true`; optional dispute flag is
`ENABLE_BROKER_DISPUTE_ASSESSMENT`, default false. **Do not enable this failed feature.**

`backend/dispute_followup_access.py status` safely reports configured non-secret
metadata when launched with uv's explicit private `--env-file`. Its authorization
operation is an explicit operator transition tied to this user's artifact, not
something models/retries can invoke. The registered window expires at
2026-10-24T12:25:38-07:00, regardless of remaining dollars. No further work is
authorized after that cutoff. Old-window clients still expire at 10:10.

Shared ledger: `D:/Downloads/order-to-cash-v6-20261024/backend/artifacts/v6-model-budget.sqlite3`.
Never replace it with the exported read-only snapshot or reset spent/reserved amounts.
Counters are telemetry; per-case correctness limits are not removed.
The authorization receipt's `original_ledger_sha256` names the pre-window-registration
database after additive schema migration, not the byte identity of V6's archived ledger.
The untouched V6 results archive remains the original immutable evidence anchor.

## Lucas-owned integration work, not performed here

Read DISPUTE_EVENT_CONTRACT.md and generated `DisputeEvent` types.
In `frontend/lib/run/broker/translate.ts`, distinguish verification from dispute
disposition; consume `dispute.assessed`, preserve raw/validation/effective provenance,
map justified→agree, not_justified→disagree, unclear→grey, and use exact server binding.
In `driver.ts`, refetch after the acquisition acknowledgement; do not treat an old
idempotent receipt as the assessment. Provide exact source links and preserve
controller/money/held/mock distinctions. A separate catalog route is missing on
this base. Do not replace `frontend/components/run/run-app.tsx` with archived V6 UI.

## Evidence

`backend/artifacts/dispute-followup/` (ignored; included in local results export):
authorization.json, smoke.json, original and technical-cohort-2 frozen results,
per-case SQLite stores/raw requests/responses/events, test XMLs, browser/HTTP evidence,
and stopped supervisor state. Never silently rerun an existing directory or count
a rules fallback as successful model output. Source hashes and first-attempt failures
are documented in DISPUTE_RESULTS.md.

## Concrete next steps (require a new task, not automatic continuation)

1. Coordinate the frontend-owner adapter changes above and add tests showing U1 never
   briefly displays disagreement from verification PASS; verify source clicks and
   read-only navigation in an available real browser. Do not change root canvas ownership.
2. Decide an independently checkable wider complaint representation before expanding
   the narrow recognizer. Add the N2 counterexample without accepting arbitrary model
   entailment. Preserve the U1 negative result as a regression.
3. Define a legitimate public justified-dispute scenario that existing deterministic
   verification does not already intercept. Do not weaken production checks to obtain it.
4. Freeze a genuinely new suite/source revision, obtain any new time/spend authority
   needed after this cutoff, and retain the same cumulative ledger. No current evidence
   authorizes enabling the feature. Re-run semantic and UI qualification before release.

Verification commands from repo root: `uv run --locked --directory backend pytest`,
`uv run --locked --directory backend ruff check .`, and `ruff format --check .` through
the same uv invocation. From frontend/: `npm run generate:check`, `npm run typecheck`,
`npm test`, `npm run build`. Tests are offline unless the explicit qualification script
is invoked with private env; do not rerun that script just to inspect existing results.
