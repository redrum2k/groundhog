# Nikita payment runbook

> Aggregate brokerage update (October 24): new default intake uses
> `aggregate-brokerage-v1`, funded CSV/JSON deliveries and the persisted `/runs` API.
> See [workstream 06](workstreams/06-data-broker.md) for current contracts, commands,
> compatibility boundaries and validation limitations. The catalog-specific details
> below remain historical compatibility guidance and do not set new dataset policy.


Runtime, Base transport and asynchronous catalog settlement are integrated and validated offline.
**No real testnet RPC result or receipt is claimed; no broadcast or deployment is authorized.**
Do not inspect existing secrets to fill setup. Use fresh disposable configuration only for a
separately authorized live milestone. [Integration evidence](workstreams/04-integration.md).

## Run offline now

From the repository root:

```sh
uv sync --locked --project backend
uv run --locked --directory backend pytest
uv run --locked --directory backend python ../tools/offline_journey.py --scenario repaired --output artifacts/catalog-repaired
uv run --locked --directory backend python ../tools/offline_journey.py --scenario unresolved --output artifacts/catalog-unresolved
uv run --locked --directory backend python ../spikes/payments/examples.py
```

Use fresh output directories: completed journey replays return their saved summaries. The
catalog harness explicitly simulates funding and uses CatalogWorker selection with an injected
clock. The lab examples run 27 independent subprocess commands with synthetic RPC/public test
scalars and temporary journals: capture, void and expiry/reclaim. Neither executes EVM bytecode
or establishes deployed-contract success. The combined HTTP/lifespan tests use actual Base
transport encoding/signing/reconciliation with injected RPC and synthetic accepted catalog terms.

`uv run --locked --directory backend python ../tools/frontend_mock.py --port 4173` serves all
12 simulated payment states at `/orders/demo/payment?state=funding_pending` and `/__mock/states`.
It is not a wallet runner. Start the main API as in README after seeding a local corpus. Default
mock funding needs explicit simulate authorization; background workers then run automatically.

## Configuration and capabilities

`.env.example` contains key=value entries. The app never auto-loads a private .env; use explicit
shell configuration or uv --env-file only when separately appropriate. Imports and OpenAPI
export do not initialize adapters, read signer configuration, start workers or call RPC.
Base selection/preflight occurs in application lifespan; failures never select mock instead.

| Variable | Purpose |
| --- | --- |
| PAYMENT_ADAPTER | `mock` default; `base_sepolia` explicitly selects the implemented transport. |
| ORDER_DB_PATH / ARTIFACT_ROOT | Catalog/invoice store and approved evidence root. Catalog payment journal uses this same database for atomic financial effects. |
| INTERNAL_API_TOKEN / REVIEWER_API_TOKEN | Different server-only worker/provider and reviewer credentials. Never NEXT_PUBLIC/browser/model inputs. |
| BASE_SEPOLIA_RPC_URL | Explicit HTTP(S) RPC supporting Base Sepolia and EIP-1898 historical block-hash reads. |
| BASE_CHAIN_ID | 84532 only. |
| BASE_USDC_ADDRESS / BASE_ESCROW_ADDRESS / BASE_ERC3009_COLLECTOR_ADDRESS | Pinned addresses in PAYMENT_SPIKE.md. Startup read probes do not attest full deployed bytecode. |
| BASE_OPERATOR_ADDRESS | Optional public address for key-free preparation/inspection; must match the signer if both supplied. |
| BASE_OPERATOR_PRIVATE_KEY | Dedicated disposable operator EOA, backend only; needs test ETH for gas. Never a buyer key. |
| BASE_PROVIDER_ADDRESS | Receiver; provider private key is not required. |
| SPIKE_BUYER_PRIVATE_KEY | Isolated lab only; buyer needs test USDC and test ETH only for payer reclaim. |
| PAYMENT_CONFIRMATIONS | 2 minimum/default, at most 100; receipt threshold is not L1 finality. |
| BASE_MAX_GAS / BASE_MAX_FEE_PER_GAS | Defaults 1000000 / 10000000000 wei; conservative ceilings, not a gas quote. |
| ENABLE_TESTNET_BROADCAST | false by default. App requires ready startup plus this opt-in. Lab additionally requires --broadcast-testnet. Separate human authorization is still required. |
| PAYMENT_JOURNAL_PATH | Private lab SQLite only. Catalog deliberately ignores this path and journals with ORDER_DB_PATH. |

A CDP API key alone does not sign these operations. The app never selects an existing wallet
implicitly. Config syntax/invalid chain/address/signer mismatches fail startup with redacted
errors; missing configuration leaves selected Base unavailable. Malformed configuration is not
silently repaired. Preparation with a configured public operator can work without a signer;
automatic submission stays disabled until signer/preflight configuration is repaired and restarted.

Existing `/health` shape:

| live_adapter | Meaning |
| --- | --- |
| disabled | Base implementation present, not selected; current mode mock. |
| unavailable | Base selected but missing usable RPC/parties/signer, or read-only startup preflight failed. |
| ready | Configured signer/parties and successful read-only startup preflight. |
| planned | Historical enum retained for compatibility; current startup does not emit it. |

`live_settlement_enabled` is true only for ready Base with explicit broadcast opt-in. This
reports startup readiness, not ongoing RPC health, balance sufficiency or chain success. Every
transaction repeats term/action-specific preflight. Failed startup disables signing until restart;
available transport still inspects submitted receipts. Missing receipts remain pending. A reserved
operation that cannot submit yields its bounded turn so another payment can reconcile.

## Automatic and protected operations

Five independent lanes: catalog and invoice deadline sweeps (1 second), catalog dispatcher,
payment worker limit 1, invoice dispatcher (0.25 seconds after each completed call). Each lane
has a thread slot; model/PDF/RPC work does not monopolize deadline execution or the event loop.
SQLite transactions never span payment RPC/signing. One application worker owns a database lock;
graceful shutdown stops selection and drains calls before releasing it. Hard restart recovers
persisted leases (catalog 45 seconds; payment operation 120 seconds).

No normal browser work call is required. Provider offers/approvals, failed-job retry and reviewer
decisions still require the respective trusted server caller; manual compile/work/payment-work
routes remain protected and compatible. [Lucas handoff](handoffs/lucas.md) has exact paths,
headers, request examples, available_actions and replay/409 rules. Lucas owns the authenticated
bridge. No unauthenticated credential-forwarding proxy is provided.

## Isolated lab, implemented commands

See [laboratory README](../spikes/payments/README.md) for all flags and copyable offline examples.
Every command requires durable --payment-id. Inspection is the default; prepare --save-fixture
persists frozen terms and reconcile persists observations. --dry-run never reserves/signs/sends.

```sh
uv run --locked --directory backend python ../spikes/payments/run.py --help
uv run --locked --directory backend python ../spikes/payments/run.py preflight --payment-id capture-a
uv run --locked --directory backend python ../spikes/payments/run.py status --payment-id capture-a
uv run --locked --directory backend python ../spikes/payments/run.py reconcile --payment-id capture-a
```

These last three require explicit RPC configuration; do not run them as an offline test.
Other implemented commands: prepare, fund, capture, void and reclaim. Live submission requires
both --broadcast-testnet and ENABLE_TESTNET_BROADCAST=true; no such run was performed here.
Use distinct fixture IDs/salts capture-a, void-b and expiry-c, each exactly 100000 atomic USDC.
Do not treat this lab amount as funding a USD 15 catalog order (15000000 atomic USDC).
Reports redact private keys, buyer authorizations, funding calldata and signed transaction bytes.

## Recovery and remaining live proof

After timeout/restart, inspect/reconcile the same saved operation/hash/nonce/terms. Missing receipt
is not failure. No automatic rebroadcast, replacement, fee bump or fresh-nonce recovery exists.
A crash after durable submitted state but before actual send can remain unresolved indefinitely;
Nikita must investigate it manually. Never delete state or reset a salt/nonce to escape ambiguity.
RPC requests now have a 15-second **elapsed** allowance without retries. The old Web3
15-second inactivity setting did not bound a continuously streaming response (review R9-A).
Each request runs in one stdlib-only HTTP child process; startup, DNS/TLS, transmission and
response handling consume the allowance. The parent reserves 0.25 seconds inside it for
kill/reap, stops request work at 14.75 seconds, polls cancellation/time every at most 25 ms,
and closes pipes before returning. No request thread survives cancellation. OS suspension
or scheduling stalls can delay deadline observation; this is not a real-time OS guarantee.
There are no redirects, environment proxies, retries, inherited wallet environment or new
dependencies. Default verified TLS is used; responses larger than 4 MiB fail structurally.
The helper only posts HTTP and cannot sign or access the journal; all HTTP/cleanup happens
outside SQLite locks. A timeout may follow a send reaching the server: it proves no absence.

Shared cooperative checkpoints renew only a current 120-second claim, every 30 elapsed
seconds during bounded work. Submission attempts have a 300-second monotonic budget
including initial lab preflight and reclaim staging; receipt inspections have a separate
180-second budget after financial expiry. Each next RPC requires its full 15-second
allowance after any checkpoint lock wait. Original application funding
(180 seconds), lab funding (300 seconds or shorter accepted lifetime), capture and aggregate
latest-safe-submission cutoffs still apply. Renewal changes none of them; void/reclaim and
receipt inspection do not inherit an expired funding/capture upper cutoff.

Cancellation/ownership loss/budget exhaustion stops new work and discards late results.
Shutdown signals cancellation and drains the HTTP child with bounded cleanup. Local buyer
and transaction signers remain synchronous: checks discard late results on return. Initial
lab funding rechecks immediately after buyer signing and inside the reservation transaction
after acquiring its write lock (R9-B). A stopped new action saves neither an operation nor
a private authorization; time spent waiting for SQLite counts in the original attempt.
Existing durable operations/nonces/bytes remain intact. No detached payment helper continues
afterward. An unsubmitted transient stop retains
its reservation/nonce/bytes; after durable submitted, a stop leaves an unresolved operation
for reconciliation, including the existing crash-before-send gap. No automatic resend occurs.
Lease expiry removes worker commit authority; it is not payment expiry or evidence of returned
funds. Check actual latency before live use. See [workstream 09](workstreams/09-payment-lease-renewal.md)
for clock boundaries, margins, tests and remaining limitations. Deadlines continue in independent
lanes while the process runs.

Confirmed evidence and catalog bookings commit atomically, once. Submitted capture cannot be
cancelled by new evidence: late complaints remain in human review even if capture confirms.
Reorgs enter a hold without deleting historical bookings or rerunning work. Transient unchanged
canonical evidence can clear uncertainty without rebooking; orphaned operations need explicit
manual recovery. Human-review cases are not automatically dismissed. Expiry alone never returns
funds; a substantive replacement waits for confirmed parent void and its own funding deadline.

Separately authorized live evidence: verify actual pinned deployment/code/linkage, USDC domain/
decimals, EOA identities, test ETH/USDC, token-store custody, historical RPC support and latency.
Observe independent fund → restart → capture and fund → void fixtures, provider non-authority,
matching events/state/balance deltas and canonical threshold; then ambiguity/duplicate/reclaim
recovery. Only actually observed transactions get real explorer links. See PAYMENT_SPIKE.md.
Customer auth/tenancy, production settlement/finality, refunds and public deployment remain out of scope.
