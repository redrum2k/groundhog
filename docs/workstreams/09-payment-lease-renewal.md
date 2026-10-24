# 09 — Fenced lease renewal and bounded payment attempts

Owner: Nikita. Offline implementation only; no real RPC, private environment,
wallet/database access, broadcast, paid model call, deployment, push or main merge.

## Starting point and baseline

Continued the existing clean `codex/payment-lease-renewal` worktree at
`../order-to-cash-payment-lease-renewal`. Inspected status, history and all existing
worktrees before editing. A fresh `git fetch origin main` confirmed both HEAD and
reviewed origin/main at **62fe03542f18d9f7514550bcff25968ae2557c08**. No competing
checkout, reset or unfinished feature merge was needed. This includes 06/07/08/08b,
atomic artifact publication and Lucas's compatibility work. Jeff's R3/R4 strict
expected failures remain unmodified.

Read the root instructions, HACK, responsibilities, payment spike/runbook,
integration checkpoint, Nikita handoff, workstream 07, workstream 08's payment
limitations and main integration review. No nested payment/runtime instructions
apply. Compiler/evidence semantics and visual design were not changed.

After `uv sync --locked --project backend`, the unmodified readiness command
passed **9 tests in 0.33s**. The historical slow reproduction advances journal UTC
only: 34 sequential reads × 4 simulated seconds = 136 seconds against a 120-second
lease, leaving a reserved nonce and no durable signed bytes or send. It does not
demonstrate sufficient real financial time. The separate crash after durable
submitted but before send still remains pending without rebroadcast.

## Design and clocks

`PaymentAttempt` is a synchronous cooperative scope shared through a ContextVar;
it creates no thread, timer, worker, journal or ledger. Separate concurrent worker
contexts cannot overwrite each other's cancellation/claim. Every Base RPC checks
before and after the call. Immediately before signing and actual send it also
checks current eligibility; durable writes independently check ownership and
elapsed/financial bounds inside their existing transaction.

| Clock/boundary | Default and enforcement |
| --- | --- |
| Individual HTTP RPC | Existing 15-second request timeout, no retry. A new RPC requires strictly more than 15 seconds remaining in the attempt and any upper financial window. No shortened timeout is silently reset to 15. |
| Worker lease | Existing 120 seconds, journal UTC. Renew at the first cooperative checkpoint at least 30 monotonic seconds after acquisition/last renewal. |
| Submission attempt | 300 monotonic seconds maximum, shared by initial lab preflight/buyer authorization, reclaim staging, executor preparation/signing/persistence and send. The application starts its attempt at executor entry. |
| Receipt inspection | 180 monotonic seconds, including chain/receipt/event/state/canonical and balance reads. Reused outer lab attempts are capped from their original start, never restarted. |
| Application financial authority | Original 180-second funding deadline, capture expiry and accepted aggregate latest-safe-submission cutoff via existing `cutoff(order)`; guard still enforces evidence, consent, disputes, amount, binding and parent return. |
| Lab financial authority | Original 300-second fixture funding window (or shorter accepted lifetime), original capture expiry. No aggregate submission margin is imposed on the independent lab fixture. |
| Void/reclaim/inspection | No inherited funding/capture upper cutoff. Existing explicit void authority still applies; reclaim needs observed chain time at/after capture expiry and confirmed full custody. Inspection stays available after all financial deadlines. |

All budgets are internal constants; no public DTO/schema, configurable deadline,
accepted snapshot or product-policy change. Tests inject a monotonic clock and
independently advance journal UTC and synthetic chain time. Chain observations are
anchored to request-start monotonic time, conservatively including read latency;
later stale heads cannot move the estimate backward. Application UTC uses the
owner's clock, never the monotonic epoch. Final send also reads a fresh head and
checks the action window decoded from the durable bytes.

With bounded 15-second RPC and the existing 10-second SQLite contention timeout,
30 + 15 + 10 leaves 65 seconds of lease margin. Checkpoints before and after each
request prevent accumulating many successful reads past a lease. Renewal uses a
short independent transaction; no RPC, signing, sleep or join holds its write lock.
`renew_claim` compare-and-updates the same token with `lease_until > now`, uses MAX
to avoid moving expiry backward, and allows only states appropriate to prepare,
submitted-send or receipt inspection. Wrong/missing/expired tokens, including the
exact boundary, cannot revive ownership. A later acquisition gets a fresh token;
stale cleanup cannot release it.

Cancellation is cooperative. An already-running synchronous request or local
signer cannot be forcibly killed by Python; after it returns its late result is
discarded. No detached work can sign, persist or send later. Process suspension,
unbounded injected transports or delays beyond the RPC timeout are not promises
of timely completion: strict lease/budget checks fail closed on return. Lifespan
signals the payment executor before draining active runtime calls; process death
still permits takeover after ordinary lease expiry. Normal/error/interruption
unwinding clears the scope and releases only its own token. Cleanup failure leaves
the lease to expire and logs a nonsecret diagnostic.

## Path map and submission boundary

| Path | Ownership and budget coverage |
| --- | --- |
| `run_one` / preparation | Claim, pending signer nonce, all preflight/simulation/gas reads, immediate presign gate, signed-byte persistence, durable submitted marker, internal send reads and actual send. |
| `run_one` / reconciliation or audit | Same renewal/checkpoints with inspection budget, no financial cutoff; stale receipts cannot commit observations, confirmation or bookings. |
| `stage_reclaim` | Same attempt/claim helper, current funded guard, payer nonce, full preflight/transaction reads, presign check and fenced byte persistence. Scope continues into executor submission without budget reset. |
| Lab funding preflight before executor | Starts inside the outer attempt; the initial 27 reads and buyer-signature gate count before operation reservation/claim. |
| Other lab inspection/preparation | Bounded outer read-only attempt; no ownership claim until an existing operation is actually worked. |
| Mock/historical | Existing journal/guard/completion and exact saved replies; no chain clock or live capability is invented. |

Ownership loss, renewal/database failure, shutdown and budget exhaustion preserve
unsubmitted operation identity, nonce and any saved bytes. A later eligible attempt
can use the same reservation. Domain ineligibility uses existing invalidation and
safe-tail nonce release rules. Neither case invents a capture, void, refund or
return. **Lease expiry is loss of worker commit authority, not payment expiry or
confirmed void.** Financial expiry also is not evidence of returned money.

Signed bytes/hash are still durable before `submitted`, and `submitted` remains
the point of no return. A stop after that marker keeps the operation unresolved,
including when cancellation occurs before the actual send. A possibly-sent timeout
must reconcile the same identity. No automatic resend, replacement nonce, rollback
to reserved, cancellation, exact-byte recovery or new salt was added. Confirmed
evidence and one-time booking retain their atomic transaction. Live funding still
precedes fulfillment; a heartbeat grants no capture authority.

Diagnostics contain operation ID and bounded reason only. Renewal is debug logging,
not customer events. CLI reports stops/pending with nonzero status even if a lost
worker cannot persist its diagnostic; a submitted marker alone is not a successful
send exit. Submitted/confirmed progress comes from the existing explicit evidence.

## Regression evidence

New tests exercise real journal connections, executor and Base transport with
synthetic signers/RPC, injected independent clocks and synchronization barriers:

- The original preparation is 128 seconds plus 8 seconds of nonce reads; it
  submits once at 148 seconds with renewal. With the extra initial lab preflight,
  the full attempt is 256 seconds and advances real simulated chain time inside
  its unchanged 300-second window. A shorter overall budget stops despite renewal.
- Wrong/expired/exact-boundary token renewal, nondecreasing expiry, inactive states,
  successor cleanup fencing, two workers and competing signer nonce reservations.
- Renewal rejection/database failure, cancellation, process interruption, shutdown
  draining and late RPC/receipt completion preserve identity and prevent effects.
- Funding/capture deadlines and aggregate cutoff reached inside transport block
  signing/send, including after submitted. Accepted terms never change; no void is
  created. Ordinary domain invalidation also fences preparation.
- Slow inspection renews beyond 120 seconds after financial expiry; exhausted
  inspection remains pending and a later observation books once. Slow payer reclaim
  renews after capture expiry and retains its independent payer nonce on budget stop.
- Historical readiness fencing is retained with renewal explicitly unavailable;
  its original no-byte/no-send/nonce-reuse assertions remain. The crash-before-send
  reproduction and no-rebroadcast assertions are unchanged.

## Validation

All commands use temporary synthetic state and injected RPC. Node was 24.14.1;
locked Python/frontend dependencies were installed without lockfile changes.

```sh
uv sync --locked --project backend
uv run --locked --directory backend pytest tests/payments/test_payment_readiness.py --tb=short --show-capture=no
uv run --locked --directory backend pytest tests/payments/test_lease_renewal.py tests/payments/test_payment_readiness.py tests/dataset/test_payment_lease.py --tb=short --show-capture=no
uv run --locked --directory backend pytest tests/payments tests/runtime tests/dataset tests/api
backend/.venv/bin/python spikes/payments/examples.py
uv run --locked --directory backend pytest
uv run --locked --directory backend ruff check . ../tools/brokerage_acceptance.py
uv run --locked --directory backend ruff format --check . ../tools/brokerage_acceptance.py
backend/.venv/bin/ruff check --config backend/pyproject.toml spikes/payments
backend/.venv/bin/ruff format --check --config backend/pyproject.toml spikes/payments
git diff --check
# In frontend, with Node 24 and uv on PATH:
npm ci --cache /private/tmp/payment-lease-npm-cache
npm run generate:check
```

| Check | Observed result |
| --- | --- |
| Original readiness baseline | 9 passed, 0.33s |
| Focused renewal/readiness/cutoff regressions | 38 passed, 2.21s |
| Payment/runtime/dataset/API suites | 352 passed, 2 known compiler xfails, 44.89s |
| Full backend suite | **695 passed, 2 known compiler xfails, 92.02s** |
| Isolated laboratory | All 27 subprocess commands passed |
| Backend Ruff lint/format | Passed, 158 Python files formatted |
| Lab Ruff lint/format | Passed, 5 Python files formatted |
| Generated contracts | Node 24 freshness check passed, no public contract changes |
| Historical 07 reports, lab README/simulator/examples, R3/R4 test markers | Unchanged against starting SHA |
| Whitespace | Passed |

An initial full run exposed an HTTP test race: observing durable `submitted` was
immediately followed by asserting one send. The new final transport read made the
pre-existing distinction observable. `test_backend_integration.py` now waits on
an injected send-completion Event before restarting, retaining its exact-send-count
and no-fulfillment-before-confirmation assertions. Its 14 cases passed in 10.12s.
The unsent-submitted crash/cancellation reproductions still stay pending. A final
confirmation check also rolls back both evidence and booking when a callback
consumes the remaining lease; a later inspection confirms once.

The upstream websockets deprecation warning remains. Fetch/uv-cache and locked npm
installation needed sandbox escalation; npm's initial sandbox attempt failed and
the approved retry succeeded. No production browser rerun was required: frontend
and public contracts are unchanged. Existing HTTP/lifespan settlement, 08b polling,
aggregate scheduling, mock/historical and exact-replay cases are in the suites above.

## Prompt 07 compatibility and remaining work

Changed Prompt-07/lab files: `spikes/payments/run.py` shares the initial preflight
budget, passes it through staging/executor and reports bounded stops honestly;
`spikes/payments/reclaim.py` uses the shared claim/budget and presign/write fences;
`backend/tests/payments/test_payment_readiness.py` explicitly disables renewal in
the historical expiry reproduction. Its failure assertions remain intact.
No historical report, `docs/workstreams/07-payment-readiness.md`, lab README,
offline simulator or example generator was rewritten to claim earlier renewal.

The unsent-submitted gap remains unresolved, intentionally. No exact-byte recovery
or rebroadcast exists. Actual endpoint latency, deployed bytecode compatibility,
testnet receipts and independently observed financial outcomes remain unmeasured.
Before any separately authorized live use, retain workstream 07's read-only
preflight and recovery prerequisites. The 0.10 test-USDC fixture is not funding for
the $120 aggregate agreement. R3/R4 compiler failures remain Jeff-owned blockers.
