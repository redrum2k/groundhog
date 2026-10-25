# Payment scheduling and early-acceptance display — October 24, 2026

Implemented in the `order-to-cash` working tree used by the running backend process.
Existing teammate changes were preserved. The backend process was not restarted;
activating its new scheduler still requires a restart. No live command, model call,
RPC request, broadcast or deployment was initiated by this work.

## Behavior

`PaymentJournal.pending` selects unfinished funding, capture, void and reconciliation
ahead of routine confirmed-receipt audits. Active work rotates by last update;
submitted and uncertain operations retain their saved transaction and nonce. Only
the latest confirmed non-mock operation for each payment is eligible for a routine
audit, starting 60 seconds after its last update. After eight active claims, a due
audit gets a turn; idle capacity also processes due audits. A singleton scheduling
counter in the existing SQLite database preserves fairness across restarts. It holds
no financial entries and changes no accepted payment terms.

The audit interval is a minimum gap, not a maximum reorg-detection latency. Audit
backlog and bounded operation duration still affect detection time. Existing claims,
operator nonce serialization, hard RPC cancellation, confirmation thresholds,
canonical checks, terminal exclusivity and atomic booking remain enforced. Explicit
inspection of a specific operation bypasses routine audit scheduling.

Early delivery acceptance already reserved capture before review expiry. An added
aggregate integration test accepts five seconds into review and confirms capture
before the unchanged original deadline, using an injected chain. It also proves
that acceptance and submission produce no premature ledger entry and that replay
does not duplicate capture.

The frontend now marks review complete and displays Release pending while capture
awaits confirmation. The countdown stops displaying during pending/confirmed capture;
the accepted deadline stays available in details. Confirmed payment alone produces
the captured display. Invalidated capture, uncertainty and reorg hold remain distinct.
Resolved findings complete investigation/finding steps; UNKNOWN continues waiting.
The projection also handles historical events without rewriting their audit stream.

## Validation

- Backend: `pytest tests/payments tests/dataset tests/catalog tests/api` — 635 passed.
- Frontend: all 169 tests passed; TypeScript and generated-contract drift checks passed.
- Ruff check/format and `git diff --check` passed.
- Production webpack build passed in `.next/payment-scheduling`; generated changes
  to `next-env.d.ts` and `tsconfig.json` were restored to their pre-build contents.
- React Doctor: 87/100 before and after, no remaining changed-scope diagnostics.

Tests use temporary databases and synthetic chain observations. Scheduling coverage
includes five old confirmed payments plus a new fund/capture/void, immediate subsequent
receipt selection, exact audit due boundary, sustained pending and uncertain traffic,
restart fairness, batch fairness, leased work, reorg detection and unique booking.
Older financial-state tests now request explicit inspections when intentionally
checking a receipt immediately after confirmation; cadence is tested separately.

Browser verification replays the previously recorded slow run through the actual
frontend, with all API requests intercepted by a read-only local fixture. It checks
pending customer/canvas states, resolved investigation, absent review countdown and
the later confirmed capture state. No browser commands reach the live backend.
Screenshots are retained locally in `.local/payment-scheduling-check/`.

Live post-change payment latency is unmeasured. The selection tests establish removal
of the historical audit backlog from the active payment path; they do not establish
network speed. A currently running audit, active queue traffic, sequential RPC reads
and chain confirmation still take time. Transport batching/connection reuse is outside
this change.
