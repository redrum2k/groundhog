# Independent capture UI regression check — October 24, 2026

The adjacent payment chat is implementing both active-payment scheduling and
canvas/review progress. This follow-up leaves those changes in place and adds
independent coverage for historical events and unresolved evidence requests.

## Additional change

`frontend/tests/historical-capture-replay.test.ts` adds five tests using synthetic
events that reproduce the old aggregate event ordering, including its missing
investigation/finding completion events. No private database or observed payment
capability is committed as a fixture.

The tests cover resolved findings without payment authority, pending capture on
reload, older `state_changed.paymentState` events, incremental polling with repeated
pages, confirmed capture, and unanswered evidence requests. Four tests failed
before the adjacent chat's projection fix. That fix passed those four but exposed
one additional regression: a grey finding replaced the existing specific evidence
request with a generic waiting message.

The one-line follow-up in `frontend/lib/run/fold.ts` preserves an existing
`investigation.waitingOn` when an unresolved finding arrives, using the generic
message only when no specific request exists. An actual request for the buyer's
answer therefore remains identifiable after the verdict event.

## Verification

- All 169 frontend tests passed, including the five new regression tests and the
  adjacent chat's payment progress tests. TypeScript and `git diff --check` passed.
- Replayed the original screenshot's archived events in an isolated Playwright
  context at 1440×900 and 390×844, both while capture was pending and after it was
  confirmed. Investigation and Finding are done; pending settlement displays
  Release pending; only the confirmed frame displays Captured. Reloads rebuild
  the correct state from the old events. No browser errors occurred.
- The browser intercepted all `/api/live` requests and served the archived replay;
  commands were rejected. This is a display check, not a new settlement or a latency
  measurement. The original page was fetched read-only. No backend restart, paid
  call, transaction or deployment was initiated by this follow-up.
- React Doctor: 87/100, with one complexity warning in `LiveDelivery`, outside the
  one-line projection change. No diagnostic was suppressed.

Ignored local evidence is in `.local/capture-delay-check/`: `replay.cjs`, archived
events/page, and `final/` screenshots plus browser results. The earlier
[capture investigation](capture-delay-20261024.md) retains the original timing
evidence; its statement that fixes were not yet implemented describes that earlier
checkpoint.
