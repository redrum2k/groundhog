# Continue 09 — bound HTTP calls and discard late buyer authorizations

Continue `codex/payment-lease-renewal` in
`/Users/nikitaafanaskin/Documents/Developer/order-to-cash-payment-lease-renewal`.
The reviewed implementation is `9622fe0ecff1bcae01e4b7104f053c9d58e2e393` from
`62fe03542f18d9f7514550bcff25968ae2557c08`. Inspect status/history first and retain
any later work. Do not create another worktree, reset a branch or reimplement 09.

The review and original prompt are currently in the main checkout; read them
there without modifying that checkout:

- `/Users/nikitaafanaskin/Documents/Developer/order-to-cash/docs/reviews/09-results-review.md`
- `/Users/nikitaafanaskin/Documents/Developer/order-to-cash/docs/reviews/repro_09_lease_boundaries.py`
- `/Users/nikitaafanaskin/Documents/Developer/order-to-cash/docs/codex-prompts/09-payment-lease-renewal.md`

Read your worktree's AGENTS.md and applicable nested instructions, HACK.md,
docs/PAYMENT_SPIKE.md, docs/PAYMENT_RUNBOOK.md and
docs/workstreams/09-payment-lease-renewal.md. The latter's 695 passing tests and
two compiler expected failures were independently reproduced; the two review probes
expose additional gaps. No 09 implementation merge or push has occurred.

Remote main was `63ac21f68ca6adf4bec4863d86ce90f3fb713bdc` at review, with newer
Lucas frontend changes. Do not overwrite or rebase away those changes during later
integration. This implementation pass stays on your current worktree; integration
of newer main and Jeff's exact reviewed commit is a separate step.

## Ownership

This is Nikita's narrow completion of 09. You are not alone in the repository;
preserve teammates' edits. Own the shared HTTP/attempt boundary in
`backend/app/payments/base_rpc.py`, necessary `base.py`/`attempt.py`/executor hooks,
the initial authorization/reservation boundary in `spikes/payments/run.py`, focused
tests and the 09 handoff/runbook. Reuse existing journal, clocks and lease mechanism.
Jeff owns compiler R3/R4 and their semantic tests; Lucas owns the frontend. Do not
merge their unfinished branches or expand into transaction recovery, product
deadline changes, payment policy, UI redesign or new infrastructure.

## R9-A: a finite HTTP call, including a response that keeps streaming

The current Web3 HTTP timeout is not a total elapsed-time limit. The handoff claims
15 seconds maximum and derives a renewal margin from it, but `HttpRpc.request` can
remain inside the HTTP provider while a response continuously supplies bytes.
`BasePaymentTransport._rpc` cannot check its attempt again until that call returns.

First reproduce the saved loopback probe. It scales the configured timeout and RPC
reservation to 100 ms, enters a 250 ms attempt, and streams twenty whitespace bytes
30 ms apart before a JSON-RPC result. At 9622fe0 it takes about 670 ms before the
attempt reports exhaustion. No chain RPC, signing or broadcast is involved.

Implement an actual elapsed-time bound at the transport boundary. The default
per-call ceiling stays 15 seconds and the total submission/inspection budgets stay
300/180 seconds. Include connection/response handling and ensure continuous byte
arrival cannot defeat the limit. Account for the next call's permitted duration
against the remaining attempt and applicable immutable financial window. Do not
quietly start a fresh full timeout after consuming the remaining budget.

Choose the smallest synchronous-compatible implementation that can enforce and
test that guarantee. Explain the real timeout semantics and cleanup behavior.
Merely setting another inactivity timeout or checking elapsed time after reading
the entire response is not sufficient. A timed-out Future around an uncancellable
thread is also insufficient: no detached request may later sign/persist/send after
its caller has abandoned it. Any helper must have a bounded stop/drain lifecycle;
do not hold SQLite locks across HTTP, sleep or joins. Do not claim Python can kill
an arbitrary running thread. Keep diagnostics capability-free and retries disabled.

If a send has already started or may have reached the endpoint when it times out,
keep its durable identity unresolved and reconcile it later. A transport timeout
does not prove absence or authorize rollback, fresh nonce/salt, or rebroadcast.
Receipt inspection must remain possible after financial expiry. Preserve the
original workstream's strict token/lease checks even with the new HTTP boundary.

Add a real loopback HTTP regression through `HttpRpc` for a slow-streaming response,
alongside deterministic/injected-clock tests. Use scaled sub-second limits and
generous bounded scheduling tolerance, not 15-second or multi-minute sleeps.
Cover cleanup/cancellation, no late effects and ambiguous send behavior without
contacting a real endpoint. Do not replace the production HTTP boundary with an
unbounded fake and claim that verifies HTTP timeout behavior.

## R9-B: recheck after buyer signing and inside the reservation transaction

Initial funding currently checks before `buyer.sign_message`, then persists the
returned authorization without another checkpoint. The review advanced only the
injected monotonic clock by 301 seconds during the synthetic signer call. The CLI
correctly returned status 3 and never signed/sent a transaction, but a newly
reserved operation still held the late buyer signature.

Discard that late result before it crosses a durable boundary. Check cancellation,
the existing elapsed budget and applicable financial cutoff immediately after
signing and again after acquiring the reservation transaction. Time spent waiting
for a SQLite lock must count. Keep signing outside the transaction. Use a suitable
time/cancellation check inside an existing transaction; do not nest another
checkpoint transaction and create a self-deadlock.

On a newly attempted funding action stopped before reservation, create no new
operation and persist no new private authorization. Do not erase an earlier
durable operation/nonce/authorization or reset the accepted terms. Keep one budget
from preflight through buyer authorization, preparation, signing and submission.
Preserve structural nonzero CLI diagnostics without printing signatures or secrets.

Add regressions for late signer completion, cancellation during signing and expiry
or budget exhaustion while acquiring the write lock. Check both the no-new-write
case and preservation of preexisting durable state. Retain the successful slow
funding path and existing preparation/reclaim/inspection regressions.

## Invariants and completion

- Lease expiry is loss of worker authority, not an automatic payment void/return.
- Financial terms and review/dispute windows remain immutable; renewals cannot
  extend them. Current evidence/consent/binding/funding gates remain enforced.
- Signed transaction bytes/hash precede the durable submitted marker and send.
  Submitted operations remain unresolved on ambiguity; no automatic resend or
  recovery operation is added by this task.
- Retain the original 136-second success with renewal and expired-lease negative
  case, stale-owner/successor fences, nonce serialization and crash-before-send
  reproduction. Preserve 08b polling and historical/mock behavior.
- Leave Jeff's two strict expected failures unchanged unless a separately reviewed
  compiler fix has already been integrated; do not remove/weaken them for green CI.

Run focused new regressions and the original 09 focused/payment/runtime/dataset/API
checks, all 27 offline lab examples, full backend pytest, backend/tools/lab Ruff
lint and format, generated-contract freshness with Node 24, and `git diff --check`.
If public contracts/frontend change, explain why and run frontend tests/typecheck
and both production browser smokes; keeping this fix internal is preferred.

Update `docs/workstreams/09-payment-lease-renewal.md`, the payment runbook and
Nikita's handoff with both review causes, actual transport limits, checks/results
and remaining exact-byte-recovery/live-proof limitations. Correct claims that the
old HTTP inactivity setting was already an elapsed request bound; preserve the
historical results rather than rewriting them as if these fixes existed earlier.

Commit only task-owned changes locally and return the exact SHA and evidence.
No push, main merge, real chain RPC, private environment/wallet/database access,
paid model calls, broadcasts, deployment or transaction recovery implementation.
