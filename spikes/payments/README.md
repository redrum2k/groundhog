# Isolated Base payment laboratory

Implemented and validated **offline only**. No real testnet receipt has been observed.
Uses the reusable `app.payments.base.BasePaymentTransport`, pinned Commerce Payments
v1.1.0, and the existing `PaymentJournal` / `PaymentExecutor`. No application wiring,
public DTO, catalog settlement rule, journal schema, or executor implementation changes.

Each fixture is **100000 atomic test USDC** with a synthetic settlement decision. It
is independent of a USD 15 catalog order (15000000 atomic USDC). Never fund a catalog
order using the laboratory amount. Offline fixtures cannot be promoted to live ones.

## Runnable offline examples

From the repository root, after `uv sync --locked --project backend`:

```sh
backend/.venv/bin/python spikes/payments/examples.py
```

This runs capture-a, void-b and expiry-c in separate CLI processes, with empty explicit
environments and temporary private journals. It uses public synthetic scalars, never
user credentials or a network provider. Its RPC double reconstructs synthetic receipts
from saved offline transactions across processes. It is not an EVM or deployment test.
Reports label the evidence synthetic and omit simulated transaction IDs/explorer links.

For a durable, manually inspectable offline fixture:

```sh
uv run --locked --directory backend python ../spikes/payments/run.py preflight --payment-id capture-a --offline
uv run --locked --directory backend python ../spikes/payments/run.py prepare --payment-id capture-a --offline --save-fixture
uv run --locked --directory backend python ../spikes/payments/run.py fund --payment-id capture-a --offline --dry-run
uv run --locked --directory backend python ../spikes/payments/run.py fund --payment-id capture-a --offline --simulate
uv run --locked --directory backend python ../spikes/payments/run.py status --payment-id capture-a --offline
uv run --locked --directory backend python ../spikes/payments/run.py reconcile --payment-id capture-a --offline
uv run --locked --directory backend python ../spikes/payments/run.py capture --payment-id capture-a --offline --simulate
uv run --locked --directory backend python ../spikes/payments/run.py reconcile --payment-id capture-a --offline
```

Use a distinct ID `void-b` for another prepare/fund/reconcile sequence, then `void
--simulate` and reconcile. Use `expiry-c` for a third fixture, then `reclaim --simulate
--offline-time 4600` after funding confirmation. Default offline creation time is 1000
and capture authority ends at 4600. The timestamps are synthetic; no waiting occurs.
Use the same timestamp for expiry-c's subsequent reconciliation. `examples.py` performs
all of these steps. Repeating a successful action reconciles its original operation.

## Commands and output

Every command takes `--payment-id`. Every subcommand has `--help` and examples.
Output is JSON. `--journal` selects a private SQLite file; offline defaults to the
repository's ignored `artifacts/payment-lab.offline.sqlite3`. Live defaults to
`PAYMENT_JOURNAL_PATH` (relative to the process working directory). Keep lab and catalog
journals separate. Private state is created with restrictive permissions and never
exported as a report.

| Command | Default behavior |
| --- | --- |
| preflight | Read-only chain, deployment/interface, domain and optional frozen payment inspection. |
| prepare | Preview; `--save-fixture` explicitly freezes/persists terms once. Existing ID always returns its original terms. |
| fund / capture / void / reclaim | Read-only inspection of the saved fixture. No operation reservation or signing. |
| status | Read-only local journal inspection; no RPC or signer loading. |
| reconcile | Read RPC and persist observations through the executor; never sign/send. `--dry-run` inspects local state only. |

`--dry-run` and signing flags are mutually exclusive. `--simulate` requires `--offline`.
Live submission requires **both** `--broadcast-testnet` and
`ENABLE_TESTNET_BROADCAST=true`, plus separate human authorization. This task did not
grant or perform live execution. Help/status/dry-run never load either signing key.

Exit codes: 0 = successful inspection, confirmed reconciliation, or newly accepted
submission (inspect the state; submission is not confirmation); 2 = usage/configuration/
precondition error; 3 = unfinished reserved/signed operation or pending/uncertain/orphaned
reconciliation; 4 = failed/invalidated operation. A lease-expired submission attempt
that remains reserved is unfinished, even if no transaction hash exists. Inspection
commands (`status`/`--dry-run`) still return 0 on successful inspection regardless of
the displayed payment state. There is no automatic polling or hidden retry.

## Future live setup (not executed)

No `.env` is loaded. Supply explicit environment values for a newly authorized disposable
setup; do not borrow another wallet's existing credentials. Public configuration:

- `BASE_SEPOLIA_RPC_URL`: HTTP(S) endpoint for chain 84532, with EIP-1898 canonical
  block-hash reads and historical `eth_call`/balance/code support.
- `BASE_OPERATOR_ADDRESS`, `BASE_PROVIDER_ADDRESS`, `SPIKE_BUYER_ADDRESS` (or `prepare
  --payer`): distinct public parties. Provider needs no private key.
- Deployment/token defaults remain exactly those in [PAYMENT_SPIKE.md](../../docs/PAYMENT_SPIKE.md).
  Overrides to other deployments/chains/tokens fail closed.
- `PAYMENT_CONFIRMATIONS`: 2–100, frozen in the fixture; two is a receipt threshold,
  not Ethereum/L1 finality.
- Optional `BASE_MAX_GAS` (21000–1000000), `BASE_MAX_FEE_PER_GAS` (1–10000000000 wei).
  Defaults are 1000000 and 10000000000. These are transaction safety ceilings.

Only explicit submission reads `BASE_OPERATOR_PRIVATE_KEY` for fund/capture/void and
`SPIKE_BUYER_PRIVATE_KEY` for fund/reclaim. Fund uses the buyer's raw ERC-3009 signature
and the operator's transaction. Reclaim signs the payer transaction in the isolated lab.
The transport never generates a catalog user's buyer signature. Buyer needs sufficient
USDC; operator needs gas ETH; buyer also needs gas ETH for reclaim. The builder checks
estimated execution gas with 20% headroom and an additional ETH balance margin for L1
fees; that margin is not an exact L1/operator fee quote.

`prepare --save-fixture` freezes fresh salt, parties, amount and deadlines. The default
preapproval lifetime is 300 seconds, authorization lifetime 3600 seconds, and refund
expiry a further 3600 seconds. `--authorization-seconds` may shorten a NEW fixture
(1–3600); rerunning prepare never extends any deadline or replaces the original salt.
Run read-only preflight again before separately authorized submission.

## Recovery

Use the same journal and payment ID after restart. Signed bytes/hash are committed
before broadcast. A timeout or missing receipt is **not failure** and never permits a
fresh salt, payment, nonce, or action with the same effect. Reconcile the saved operation.
The journal serializes signer nonces and permits only one active terminal operation.

There is deliberately **no rebroadcast or replacement command**. A crash after marking
submitted but before sending may remain pending indefinitely. An RPC that does not
support pinned historical reads yields uncertainty. Do not delete the journal to retry.
Resolve ambiguous/orphaned cases manually with the owner of the durable executor. Expiry
allows payer reclaim; it never proves return. Confirmed effects are not undone when a
receipt disappears; the account is held for explicit recovery. After an audit hold, a
recovered receipt alone does not clear the laboratory's account hold automatically.

The lab's reclaim helper claims the existing operation, reserves the **payer's** nonce
using `PaymentJournal.reserve_nonce`, persists `SignedTransaction`, then delegates to
the unchanged executor for submission and reconciliation. A preparation interruption
keeps that reservation; an already saved signature is reused. It never pretends that
the payer is the operator. See [workstream handoff](../../docs/workstreams/02-base.md).

The [payment-readiness handoff](../../docs/workstreams/07-payment-readiness.md) records
the tested shared revision, injected lease/crash evidence, missing public configuration,
and exact commands/evidence gates for a later separately authorized testnet run.
