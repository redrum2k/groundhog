# Nikita payment runbook

Phase 1 is executable offline. Live RPC execution and the isolated runner are the next
independent milestone; no testnet transaction is claimed or authorized here. Do not inspect
existing secrets to fill setup. No Jeff prompts or Lucas UI are required for the payment lab.

## Run now

From the repository root:

```sh
uv sync --locked --project backend
uv run --locked --directory backend pytest tests/payments tests/api tests/catalog tests/legacy
uv run --locked --directory backend python ../tools/frontend_mock.py --port 4173
```

The last command serves all-state frontend fixtures; it is not a wallet runner. Inspect
`http://127.0.0.1:4173/orders/demo/payment?state=funding_pending` and `/__mock/states`.
Run the main API with the README command to exercise quote acceptance → funding preparation
→ explicit `simulate: true` authorization → bounded mock worker → fulfillment → gated mock
capture. `docs/handoffs/lucas.md` gives exact request/response contracts. Keep `PAYMENT_ADAPTER=mock`.

## Future local configuration

`.env.example` contains actual key=value entries; copy only into an ignored private local file.
The app does not auto-load `.env`. Use explicit shell configuration or uv `--env-file` only
when appropriate; do not silently select another existing account's key.

| Variable | Purpose |
| --- | --- |
| PAYMENT_ADAPTER | `mock` now; `base_sepolia` is planned opt-in execution. |
| BASE_SEPOLIA_RPC_URL | RPC for chain 84532; validate chain before signing/submission. |
| BASE_CHAIN_ID | `84532` only. |
| BASE_USDC_ADDRESS / BASE_ESCROW_ADDRESS / BASE_ERC3009_COLLECTOR_ADDRESS | Pinned values in PAYMENT_SPIKE.md; verify live deployment before use. |
| BASE_OPERATOR_PRIVATE_KEY | Dedicated disposable test EOA, backend only. Operator needs Base Sepolia ETH for gas. |
| BASE_PROVIDER_ADDRESS | Receiver; provider private key is not required. |
| SPIKE_BUYER_PRIVATE_KEY | Isolated runner only; buyer needs test USDC and ETH only for payer reclaim. |
| PAYMENT_CONFIRMATIONS | `2` minimum/default; receipt threshold is not L1 finality. |
| ENABLE_TESTNET_BROADCAST | `false`; future execution also requires explicit CLI opt-in. |
| PAYMENT_JOURNAL_PATH | Private durable SQLite state; authorization capabilities/raw transactions are not reports. |

A CDP key alone does not sign these operations. CDP faucet/wallet alternatives are optional
for the direct RPC/local signer path. Missing credentials do not block offline tests.

## Next executable runner contract — not implemented in Phase 1

Implement `spikes/payments/run.py` as a thin wrapper over the reusable adapter. Required
commands are `preflight`, `prepare`, `fund`, `status`, `capture`, `void`, `reconcile`, `reclaim`.
Each accepts a durable `--payment-id`; default is inspection/dry-run. Actual testnet submission
requires `--broadcast-testnet` plus ENABLE_TESTNET_BROADCAST=true and separate human authorization.

Planned invocation shape (these commands do not exist yet):

```text
uv run --locked --directory backend python ../spikes/payments/run.py preflight --payment-id capture-a
uv run --locked --directory backend python ../spikes/payments/run.py prepare --payment-id capture-a
uv run --locked --directory backend python ../spikes/payments/run.py fund --payment-id capture-a
uv run --locked --directory backend python ../spikes/payments/run.py status --payment-id capture-a
uv run --locked --directory backend python ../spikes/payments/run.py capture --payment-id capture-a
uv run --locked --directory backend python ../spikes/payments/run.py reconcile --payment-id capture-a
uv run --locked --directory backend python ../spikes/payments/run.py void --payment-id void-b
uv run --locked --directory backend python ../spikes/payments/run.py reclaim --payment-id expiry-c
```

Use distinct accepted fixture IDs/salts for capture-a, void-b and expiry-c, each exactly 100000
atomic USDC. Before each submission, inspect frozen parties/amount/deadlines and live preflight.
Do not treat the 0.10 laboratory amount as settlement of a USD 15 catalog order. Keep JSON
reports redacted; never print private keys, authorization signatures or signed transaction bytes.

## Recovery requirements

After timeout/restart, inspect/reconcile the same durable operation. Missing receipt is not
proof of failure; do not make a new payment, salt or nonce. The future runner must explicitly
implement and document identical-byte rebroadcast, or leave submission unresolved for manual
recovery. Until implemented, no automatic rebroadcast is claimed. Expiry blocks capture but
funds remain held until void/reclaim evidence. Changed/orphaned block observations require a
hold and manual recovery; never rerun work or reissue a transfer automatically.

Completion evidence is the two independent scenarios in PAYMENT_SPIKE.md, with matching events,
state, canonical block evidence, token-store balances and observed explorer links. Current
receipt threshold/reorg handling is a demo limitation, not production settlement assurance.
