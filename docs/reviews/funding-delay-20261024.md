# Funding delay and lower-left overlap — October 24, 2026

The Source learning launcher occupied the same bottom-left coordinates as the
live canvas caption. It now participates in the wrapping toolbar; its expanded
panel remains viewport-bounded. Verified at 1440×900 and 390×844, including opening
and closing learning. No overlapping launcher/caption rectangles or browser errors.
TypeScript and all five source-learning component tests pass. React Doctor reports
92/100 and no findings in its changed-file scan. Existing next-env.d.ts edits remain
untouched. Browser screenshots are local-only under `.local/ui-overlap-check/`.

## Observed funding delay

Read-only inspection of the running backend's events and SQLite payment observations
for request `request-35844cd6c3e441ccb42cb667d909703d` established the following.
Times are October 24, America/Los_Angeles (UTC−07:00).

| Transition | Time | Elapsed since funding request |
| --- | --- | --- |
| Funding operation reserved after buyer authorization | 19:15:29.457 | 0 s |
| Durable submitted transition, immediately before broadcast | 19:16:02.837 | 33.380 s |
| Funding confirmed and booking applied | 19:16:29.436 | 59.979 s |
| Dataset delivered and review opened | 19:16:29.687 | 60.230 s |

The delay is in the payment lane, before fulfillment. The first recorded funding
observation already had 107 confirmations; accepted terms require two. This is
application-observed confirmation latency, not evidence of a minute-long chain
inclusion time. No new RPC measurement or transaction was performed for this review.

## Cause supported by code and observations

`main.py` runs a single payment lane calling `payments.work(limit=1)`.
`PaymentJournal.pending(include_confirmed=True)` mixes active operations with
confirmed-payment audits and orders all of them by `updated_at`. There is no audit
interval or priority for unfinished funding. Every audit does full reconciliation.

Four old confirmed operations were audited at 19:15:33.847, :39.463, :44.105 and
:48.736 before the new payment reached submission. After submission, those four
were audited again at 19:16:10.146, :16.293, :20.485 and :24.875 before the new
payment was confirmed at :29.436. The older operations were one captured payment
and three held payments. Their intervening audits explain substantial queue delay.

`BasePaymentTransport` also performs sequential preflight/simulation RPC reads and
sequential receipt, transaction, state, balance and canonical-block reads.
`HttpRpc.request` creates a disposable process and fresh HTTP connection for each
call to enforce a hard elapsed-time bound. The observed audit completions are
roughly 4–6 seconds apart during this interval. Historical data does not separate
network latency from process/TLS overhead, nor give the precise broadcast-return
time; those proportions remain unmeasured.

## Separate subsequent wait

The buyer opened a complaint at 19:16:55.451. At 19:17:03.478 the investigation
requested an actual buyer evidence answer, with a 19:17:55.450 deadline. That later
hold is a dispute/evidence gate, independent of the initial funding delay. The
review window is also intentionally 60 seconds; it does not explain the funding
delay before delivery. Held funds must not be described as completed settlement.

## Proposed next change

Schedule unfinished payment work ahead of routine confirmed-receipt audits, with
a bounded audit cadence and fairness so neither reconciliation nor reorg detection
can starve. Test selection with several historical confirmed payments and one new
funding operation. Preserve operator nonce serialization, lease/attempt fences,
exact saved transactions, canonical checks, confirmation requirements and atomic
booking. Measure individual RPC durations using redacted method/timing metadata
before considering batching or connection reuse; preserve hard cancellation.

This task changes UI placement only. Payment scheduling and financial state were
not modified, the backend was not restarted, and no paid call, broadcast or deployment
was initiated. Investigation used existing local evidence rather than live-chain
reverification.
