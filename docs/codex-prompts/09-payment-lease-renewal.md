# 09 — Renew payment-worker leases without extending payment authority

Implement Nikita's next shared payment-runtime task: fenced lease renewal and
bounded operation attempts. This is offline implementation and validation, not
live payment execution. Do not implement transaction recovery or rebroadcast.

## Starting point and ownership

Use a new `codex/payment-lease-renewal` branch/worktree from current reviewed
`origin/main`, preferably `../order-to-cash-payment-lease-renewal`. The known
integrated baseline is `62fe03542f18d9f7514550bcff25968ae2557c08`, containing
06/07/08/08b, the atomic artifact-publication fix and Lucas's compatibility work.
Inspect status, history and existing worktrees first. If this task already has
a worktree, continue it; do not create a competing checkout or reset its edits.
Record the actual starting SHA and retain any newer reviewed main changes.

Read AGENTS.md and applicable nested instructions, HACK.md,
docs/responsibilities.md, docs/PAYMENT_SPIKE.md, docs/PAYMENT_RUNBOOK.md,
docs/INTEGRATION_CHECKPOINT.md, docs/handoffs/nikita.md,
docs/workstreams/07-payment-readiness.md, the payment-limitations section of
docs/workstreams/08-review-remediation.md and docs/reviews/main-integration.md.

You are not alone in the codebase. Preserve teammates' edits. Jeff independently
owns R3/R4 compiler semantics and related tests; Lucas owns visual design. Do not
edit their subsystems or merge an unfinished feature branch during this task.

Own the narrow shared payment changes in:

- `backend/app/payments/journal.py` and `executor.py`.
- A small shared lease/budget helper under `backend/app/payments/`, if useful.
- Necessary cancellation/deadline hooks in `base.py`, `base_rpc.py`,
  `base_config.py`, `catalog.py` and runtime wiring. Avoid unrelated rewrites.
- `spikes/payments/reclaim.py` and minimal lab call-site changes required to use
  the same mechanism, including preflight before executor entry.
- Relevant payment/runtime/API tests and a new
  `docs/workstreams/09-payment-lease-renewal.md` handoff. Update the payment
  runbook and Nikita handoff where behavior changes.

Prompt 07's files were previously retained unchanged as historical evidence.
This follow-up may narrowly adapt its readiness test and lab wiring to the new
shared behavior. Preserve meaningful failure coverage and historical reports;
do not rewrite the old evidence to claim renewal already existed.

## The distinction this implementation must preserve

Four different clocks govern this path:

| Clock | Meaning |
| --- | --- |
| Individual RPC timeout | Bounds one network request; currently 15 seconds. Many successful requests can exceed a lease in total. |
| Worker lease | Temporarily grants one worker ownership of an operation; currently 120 seconds. It is renewable only while ownership remains valid. |
| Attempt time budget | A finite elapsed-time bound on one attempt, even while its lease renews successfully. |
| Accepted financial deadlines and policy cutoffs | Immutable limits on what action is authorized. A worker heartbeat cannot extend them. |

**Lease expiry is not payment expiry and does not automatically void, refund,
capture or return funds.** It removes the worker's authority to commit its stale
result. At the current slow-preparation baseline, the operation remains reserved
with its original nonce and no persisted signed transaction or broadcast. A later
eligible attempt can reuse that reservation. Financial outcomes require their
existing explicit authorization and confirmed evidence.

## Establish the baseline

Inspect `PaymentJournal.claim`, `owns`, `release_claim` and `reserve_nonce`;
`PaymentExecutor.run_one`, `_process` and `_reconcile`; the Base preparation/send
boundaries; and `stage_reclaim` in the lab. Map every lease-owning path before
changing it. Account for preflight that happens before the executor is entered.

Reproduce these existing cases using temporary journals, synthetic signers and
injected RPC only:

```sh
uv sync --locked --project backend
uv run --locked --directory backend pytest tests/payments/test_payment_readiness.py --tb=short --show-capture=no
```

The slow-RPC case makes 34 sequential reads inside the leased section at four
simulated seconds each: 136 seconds exceeds 120, although no individual request
times out. Ownership fencing correctly prevents saving/sending the late result.
Its fake clock currently advances journal time, not chain time; do not mistake
that test for a demonstration that the real funding window remains sufficient.

The separate crash-after-submitted-before-send case must retain its current
safe pending behavior. This task does not fix or conceal that recovery gap.

## Required behavior

### 1. Renew only a current claim

Add an atomic journal renewal operation taking operation ID and ownership token.
Use compare-and-update against the same token and a strictly unexpired lease.
Wrong tokens, missing claims and expiry at the exact boundary must fail without
mutation. An expired worker cannot revive its claim, even if no successor has
claimed it yet. Renewal must not move expiry backward or resurrect an operation
that is no longer eligible for the activity being performed.

Keep tokens stable during renewal. A later acquisition gets its own token; the
previous worker's renewal or cleanup cannot modify the successor's claim. Preserve
the existing signer-wide nonce serialization and terminal-action exclusivity.

### 2. Keep ownership alive during bounded work

Use one shared mechanism for executor preparation/submission, receipt inspection
and isolated payer-reclaim staging. Do not duplicate a second lease manager in
the lab or create a second journal/ledger. Short independent SQLite transactions
perform renewal; no RPC, signing, sleep or thread join occurs under a write lock.

Choose and document a renewal strategy suited to the synchronous transport. It
may use cooperative checkpoints or a managed heartbeat, provided it renews before
expiry during legitimate slow calls and fails closed when it cannot do so. Keep
the 120-second lease and existing per-call upper bound; merely enlarging either
does not solve this task. Any interval must leave a justified margin for bounded
RPC and database contention.

Renewal failure, ownership loss, cancellation or an expired attempt budget must
prevent new preparation/signing/submission work. An already-running synchronous
call may take time to return: do not claim Python threads can be forcibly killed.
Bound the call, signal cancellation and discard late results. Do not let a timed-out
background task later persist or send after its caller has given up.

Keep ownership and eligibility checks at the durable write boundaries. Check the
appropriate cancellation/deadline conditions immediately before signing and the
actual send, including any reads performed inside the transport after executor
checks. Do not rely solely on a check taken before several slow RPCs.

Stop/join any helper on normal completion, errors and shutdown without holding a
database lock. Cleanup must not keep renewing indefinitely or release another
worker's lease. Process death must still allow ordinary takeover after expiry.

### 3. Bound attempts without changing the accepted agreement

Define finite, documented attempt budgets, with deterministic clock/scheduler
injection for tests. Use a monotonic source for elapsed time and appropriate UTC/
chain evidence for absolute accepted deadlines; do not mix their time domains.
Budget checks must cover all preparation reads belonging to the attempt, including
an initial lab preflight outside `run_one`, rather than resetting at each layer.
Account for the next RPC's maximum duration when allocating the remaining budget;
do not silently reset a full timeout after the budget is exhausted.

Derive action-specific eligibility from the existing immutable terms and current
policy: funding window, capture authorization and latest-safe-submission cutoff,
void rules, and payer-reclaim eligibility. Preserve application versus lab deadline
differences. Renewal cannot change PaymentInfo, salt, payment ID, amount, parties,
source versions, review/dispute clocks or any authorization deadline. Reclaim's
eligibility and post-submission reconciliation must not accidentally inherit a
funding/capture cutoff that makes them impossible after that cutoff.

Receipt reconciliation remains available after financial deadlines, under its own
finite inspection budget. Late/stale observations cannot be committed by a worker
that lost its claim. One exhausted inspection is not proof of failure or return.

Keep transient ownership loss distinct from domain ineligibility. Preserve the
original operation, nonce and saved bytes wherever the existing recovery rules
require them. Do not release/reassign a nonce unless the existing unsubmitted,
safe-tail rules establish that it is safe. Report bounded failure/pending status
honestly; do not fabricate a terminal financial result or successful CLI exit.

### 4. Preserve the submission boundary

Signed bytes/hash remain durable before broadcast. Once `submitted` is durable,
the operation remains subject to existing reconciliation rules even if the lease,
attempt budget or financial deadline subsequently expires. Do not roll it back to
reserved, cancel it, allocate a replacement nonce or automatically resend it.
If cancellation is noticed before the actual send but after that durable marker,
leave an explicitly unresolved operation for the separate recovery task. If a send
may have happened, reconcile its saved identity; never infer absence from timeout.

Confirmed payment evidence and ledger booking still commit atomically and once.
No fulfillment before confirmed funding; no capture merely because a lease is
alive. Keep all current evidence, consent, dispute, expiry and parent-void gates.

Add only useful nonsecret diagnostics for ownership loss/budget exhaustion and
renewal lifecycle. No keys, signatures, raw signed bytes or credential-bearing RPC
URLs in reports. Do not flood customer event streams with heartbeat updates.

## Required regressions

Use injected clocks and synchronization barriers, not multi-minute sleeps. Test
the real journal/executor/transport paths and separate connections/workers.

1. The 136-second preparation completes once with renewal when both its attempt
   budget and immutable financial window genuinely allow it. Retain the original
   expired-lease fencing case with renewal unavailable/lost; do not simply delete
   its assertions. Advance elapsed time, lease time and chain/financial time
   deliberately in their respective tests.
2. Renewal rejects wrong/expired tokens and the exact expiry boundary. A stale
   worker cannot renew, persist a late result or release a successor's claim.
   Two workers cannot submit the same operation or allocate competing signer nonces.
3. Renewal/database failure and process interruption stop further effects; late
   RPC completion cannot save or send. Restart retains the original identity and
   nonce, and any helper terminates on success, exceptions and shutdown.
4. Successful renewal does not defeat the total attempt budget. Funding expiry,
   capture authorization expiry and the latest-safe-submission cutoff reached
   during preparation still block the unauthorized action, including at the final
   send boundary. No accepted deadline moves and no automatic void occurs.
5. Ordinary domain invalidation during preparation still fences submission.
   Already-submitted operations remain reconcilable after expiry/lease loss, with
   no automatic rebroadcast, fresh nonce, duplicate booking or cancellation.
6. Slow receipt inspection and payer-reclaim staging use the same ownership rules.
   Reclaim retains its payer signer/nonce boundary and correct temporal eligibility.
7. Mock and historical profiles, exact idempotent replies, HTTP/lifespan settlement,
   08b polling recovery and aggregate scheduling remain compatible.

Adapt limitation tests only to reflect the newly implemented behavior. Keep the
unfixed crash-before-send reproduction and its no-rebroadcast assertions. Jeff's
R3/R4 expected failures remain disclosed unless a reviewed compiler fix is already
in the starting baseline; never weaken or reinstate markers to force a green suite.

## Validation and handoff

Run focused new tests, then the following from the task worktree:

```sh
uv run --locked --directory backend pytest tests/payments tests/runtime tests/dataset tests/api
backend/.venv/bin/python spikes/payments/examples.py
uv run --locked --directory backend pytest
uv run --locked --directory backend ruff check . ../tools/brokerage_acceptance.py
uv run --locked --directory backend ruff format --check . ../tools/brokerage_acceptance.py
backend/.venv/bin/ruff check --config backend/pyproject.toml spikes/payments
backend/.venv/bin/ruff format --check --config backend/pyproject.toml spikes/payments
git diff --check
```

With Node 24 and uv available, run `npm run generate:check` from `frontend` after
installing locked dependencies if needed. If public contracts change, regenerate
them and run frontend tests/typecheck and both existing production browser smokes.
Prefer keeping the lease mechanism internal. All examples and tests use temporary
synthetic state and injected RPC, with no real broadcast or paid model calls.

Write `docs/workstreams/09-payment-lease-renewal.md` with the starting SHA, baseline
reproduction, chosen renewal/cancellation design, exact budget boundaries/defaults,
covered paths, commands/results actually observed, compatibility changes and
remaining recovery/live-proof limitations. Explain how lease expiry differs from
financial expiry and confirmed void. List any changed prompt-07-owned files and why.

Commit only task-owned changes locally; return the exact SHA, validation evidence
and remaining blockers. Do not push, merge main, implement exact-byte recovery,
increase product deadlines, add infrastructure, redesign the UI, access private
environments/wallets/databases, call real RPC, broadcast, deploy or invoke paid models.
