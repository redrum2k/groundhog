# Capture delay and stale investigation display — October 24, 2026

The screenshot's run is `request-8167bbace9624ea98698bdc16fbad681`, order
`order-quote-be0c166ad72841beae8c75c21a6fc046`. Its capture completed, but took
105.157 seconds after the reservation made on customer acceptance. Two separate
problems explain the experience: payment queue contention and incomplete canvas
step transitions.

## Evidence and timing

Read-only inspection of the running backend's SQLite database at
`order-to-cash-live/.local/orders.sqlite3` supplied the persisted events and payment
observations. No new RPC request or transaction was needed. Times below are
October 24 in America/Los_Angeles.

| Transition | Local time | Elapsed after capture reservation |
| --- | --- | --- |
| Investigation finding persisted: complaint contradicted | 19:43:53.067 | Before acceptance |
| Capture reserved | 19:44:04.498 | 0 s |
| Canvas receives `capture_pending` | 19:44:04.505 | 0.007 s |
| Durable submitted transition, immediately before broadcast | 19:45:05.997 | 61.499 s |
| First capture observation | 19:45:49.653 | 105.155 s |
| Capture confirmed, review closed and booking emitted | 19:45:49.655 | 105.157 s |

The first capture observation already had **187 confirmations**, while accepted
terms require **two**. This establishes delayed application observation; it does
not establish the exact inclusion or broadcast-return time. The durable submitted
timestamp precedes the network send and must not be described as its completion.

Initial funding in this same run also took 72.127 seconds: reserved at
19:42:23.181, submitted at 19:43:09.880, confirmed at 19:43:35.308.

## Primary bottleneck: completed-payment audits compete with active work

`backend/app/main.py` has one payment lane, calling `payments.work(limit=1)` and
waiting 0.25 seconds after each call. The interval is not an execution time limit.
`CatalogPayments.work` and `PaymentExecutor.run_one` select through
`PaymentJournal.pending(include_confirmed=True)`. The query sorts both unfinished
operations and confirmed non-mock receipts by `updated_at`, without an audit
cadence or active-operation priority.

After acceptance, confirmed-payment observations completed at 19:44:08.635,
:15.287, :21.723, :28.535, :36.587 and :42.583 before capture submission.
The first was the just-funded order's already-running funding audit; the others
were older payments. After submission, five older operations were audited again
at 19:45:15.360, :22.376, :29.559, :36.718 and :44.490 before the capture
observation at :49.653. These are persisted observations, not hypothetical queue
behavior. Typical audit completions in this interval were 6–8 seconds apart.

Submission returns without reconciling its receipt. Updating the submitted
operation's timestamp puts it behind the older confirmed receipts again. More
historical payments therefore increase user-facing delay on both sides of send.

There is also substantial transport work: action preflight, preparation and
reconciliation issue sequential RPC reads. Each `HttpRpc.request` starts a
disposable process and a fresh HTTP connection to enforce a hard elapsed bound.
The interval between the last preceding audit and capture submission is about
23 seconds. Historical records do not separate network, process/TLS, local
eligibility-check and signing time, so optimizing any one of those requires
method-level timing first.

## Display bug reproduced from the actual events

Replaying this run through the current `frontend/lib/run/fold.ts` reproduces:

| Canvas state | While capture pending | After confirmed capture |
| --- | --- | --- |
| Customer review | running | done |
| Investigate | running | **still running** |
| Finding | idle | **still idle** |
| Captured | idle | done |
| Orb location | investigate | captured |

The dataset assessment emits a `verdict` but no corresponding investigation or
finding completion events. The fold stores the verdict without changing those
step statuses. Payment-state changes update the money badge without moving the
orb or starting a settlement step. Review completion is emitted only on confirmed
capture. Consequently the screenshot's running investigation is stale even
though its explanation has already arrived and capture is pending.

The browser polls every approximately one second plus response time and refreshes
immediately following a successful acceptance command. There is no client-side
60-second payment delay in this path. The accepted 60-second review window also
does not cause this wait: the catalog capture gate accepts either current
explicit acceptance or review expiry, and this capture was reserved before the
original review deadline.

Local replay evidence: `.local/capture-delay-check/events.json` and
`.local/capture-delay-check/projection.json`. These are ignored local artifacts.

## How to shorten it

1. Prioritize unfinished funding/capture/void operations over routine confirmed
   receipt audits. Give audits an explicit due time and a bounded fair share so
   reorg detection remains active even under sustained new work. Preserve fair
   scheduling among active operations, including uncertain submissions. Simply
   increasing the batch limit still executes the selected operations serially.
2. Schedule the submitted operation's next receipt check promptly instead of
   placing it behind the entire audit backlog. Preserve the saved hash/nonce,
   lease fencing, current eligibility checks, two confirmations and atomic booking.
   Do not add concurrent signing or another ledger to solve scheduling.
3. Complete resolved investigation/finding steps and show settlement as pending
   as soon as capture is reserved. Pending must remain visibly distinct from
   confirmed payment. Historical event replay also needs a compatible projection
   fix; new backend events alone would not fix existing runs.
4. Record redacted RPC method/duration metrics before evaluating batching or
   connection reuse. Any transport optimization must retain hard cancellation,
   block consistency and canonical receipt checks.

The trace suggests queue scheduling can remove tens of seconds, potentially most
of the observed delay. Roughly 30 seconds plus any currently running operation
is a useful initial measurement target under similar conditions, **not a verified
post-fix latency or guarantee**. Review/dispute windows and accepted confirmation
requirements need not be shortened.

Validate a scheduling change offline with several confirmed historical payments,
one new capture, repeated pending/uncertain observations, sustained active traffic,
audit fairness, restart/lease recovery and duplicate-booking protection. Separately
verify the frontend projection for resolved findings, pending capture, confirmed
capture and genuinely unresolved evidence requests.

This investigation changes no application code, financial state or running process.
No paid model call, RPC request, broadcast, restart or deployment was initiated.
Existing teammate edits were preserved. The recommendations above are not yet
implemented or benchmarked.
