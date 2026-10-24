# 09 results review — two attempt-boundary gaps

Reviewed October 24, 2026. Decision: **amend before merging**.

- Implementation: `9622fe0ecff1bcae01e4b7104f053c9d58e2e393`, clean worktree
  `../order-to-cash-payment-lease-renewal`, branch `codex/payment-lease-renewal`.
- Original prompt: [09-payment-lease-renewal.md](../codex-prompts/09-payment-lease-renewal.md).
- Starting/main integration baseline: `62fe03542f18d9f7514550bcff25968ae2557c08`.
- Fetched remote main: `63ac21f68ca6adf4bec4863d86ce90f3fb713bdc`. Its intervening
  changes are Lucas's frontend work; preserve them during eventual integration.
- No implementation merge or remote push was performed by this review.

## Alignment

The change stays within the assigned payment/runtime/lab scope. It implements
atomic token-preserving renewal, cooperative checkpoints, shared monotonic attempt
budgets, independent financial cutoffs, reclaim and inspection coverage, shutdown
signaling, stale-worker fencing and durable submitted-state preservation. The
historical expired-lease reproduction remains, with renewal disabled explicitly.
The crash-after-submitted-before-send gap remains disclosed and is not hidden by
automatic rebroadcast. Jeff's compiler code and strict R3/R4 markers are unchanged.

The handoff accurately reports the existing suite's results. However, the following
fresh reproductions contradict the claimed complete bounded-call/late-result coverage.
Neither reproduction moved funds, broadcast a transaction or used a private key
other than the existing public synthetic test fixture key.

## R9-A — HTTP inactivity timeout is not an elapsed request limit (P2)

`backend/app/payments/base_rpc.py:25` configures Web3's HTTP provider with
`request_kwargs={"timeout": 15}`. `base.py:48` reserves 15 seconds before entering
that provider; `attempt.py:102` notices budget exhaustion only at checkpoints.
The HTTP timeout does not impose the claimed maximum elapsed duration on a response
that continues delivering bytes. This transport setting predates 09; the new
finite-attempt design and its lease-margin calculation rely on an unproven bound.

A local HTTP server returned a JSON-RPC response preceded by twenty whitespace
bytes, one every 30 ms. Scaling both the configured RPC timeout and reservation to
100 ms, with a 250 ms attempt, the actual transport call returned after **672 ms**.
Only then did the attempt report exhaustion. Every byte arrived inside the read
timeout. This exercises `HttpRpc` and `BasePaymentTransport`, not a fake `request`
that ignores a timeout. With continuing bytes, the same mechanism can occupy the
payment worker and shutdown drain beyond the supposed finite bound.

The existing stale-result checks still fail closed after return. This finding is
about the missing liveness/time bound, not evidence of an unauthorized send.
Prompt 09 requires a bounded in-flight call, finite attempts and cleanup; checking
elapsed time after an unbounded response is insufficient. Preserve a real maximum
per-call duration, account for the remaining attempt/financial budget, and add a
slow-streaming local HTTP regression. Do not solve it with a detached thread that
can continue executing a send after its caller stops.

## R9-B — late buyer authorization is persisted after attempt expiry (P2)

`spikes/payments/run.py:490` checks before buyer signing, but lines 507–509 reserve
the new operation and save its private authorization without a post-signing check
or a check inside the reservation transaction.

In the real offline CLI path, a synthetic signer returned normally after advancing
only the injected monotonic clock by 301 seconds. The 300-second attempt then exited
with status 3, but the journal already contained a **new reserved operation with
the buyer signature persisted**. It had no nonce or signed transaction, and there
were zero broadcasts. The executor correctly refused further work; the late buyer
capability had nevertheless crossed the preceding durable boundary.

Prompt 09 explicitly includes initial lab buyer authorization in the same attempt
and requires discarding late results. Recheck immediately after signing and at the
durable reservation boundary, including time spent acquiring the SQLite lock.
Discard the late authorization without creating a new reservation. Preserve any
previously durable reservation/nonce/bytes and distinguish cancellation/budget stops
from domain ineligibility. Add cancellation and financial-expiry cases as well.

## Reproduce safely

The saved [review probe](repro_09_lease_boundaries.py) uses a loopback-only synthetic
HTTP server, a temporary journal and the existing offline signer fixture. Its JSON
reports booleans and state, never capability bytes. Run against the exact 09 worktree:

```sh
/Users/nikitaafanaskin/Documents/Developer/order-to-cash-payment-lease-renewal/backend/.venv/bin/python \
  /Users/nikitaafanaskin/Documents/Developer/order-to-cash/docs/reviews/repro_09_lease_boundaries.py \
  --worktree /Users/nikitaafanaskin/Documents/Developer/order-to-cash-payment-lease-renewal
```

The timing constants are scaled only inside this probe. It does not change
production timeouts, call a real chain endpoint or inspect existing databases.

## Independent validation observed

From the 09 worktree:

| Command/check | Result |
| --- | --- |
| Focused renewal/readiness/dataset-cutoff tests | 38 passed, 1.80 s |
| `uv run --locked --directory backend pytest --tb=short --show-capture=no` | 695 passed, 2 expected compiler failures, 91.05 s |
| `backend/.venv/bin/python spikes/payments/examples.py` | All 27 offline subprocess commands passed |
| Backend/tools Ruff lint and format | Passed; 158 files formatted |
| Payment-lab Ruff lint and format | Passed; 5 files formatted |
| Node 24 `npm run generate:check` | Passed |
| `git diff --check 62fe035..HEAD` | Passed |
| Local HTTP and late-signer probes | Reproduced R9-A and R9-B |

No frontend or public contract changes belong to 09. No live testnet success,
deployment, paid model call or recovery implementation is claimed.

## Next jobs

- **Nikita:** run [09b](../codex-prompts/09b-payment-attempt-boundaries.md) in the
  existing payment-lease worktree. Fix R9-A/R9-B, retain the passing coverage and
  return an exact tested local commit. Exact-byte recovery remains the following
  separately scoped task, not part of this amendment.
- **Jeff:** continue R3/R4 in the existing compiler branch/worktree. Keep semantic
  fixes independent of the payment files. Return the exact tested commit and remove
  strict expected-failure markers only when their original cases pass.
- **Integration:** independently review both results; preserve newer remote main,
  combine reviewed commits locally, validate and then push. Do not merge 09 as
  complete while the two findings remain open.
