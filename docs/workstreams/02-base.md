# Conversation 2 — reusable Base transport and payment laboratory

Status: offline implementation and validation complete. **No live RPC, real testnet
transaction/receipt, deployment, token purchase, existing wallet credential access, or
paid model call was performed.** No push or merge. Work began on clean branch
`codex/base-transport` at `ac385a1abf1ce66dfd1f792cac021cfa5286d7ae` in the assigned worktree.
The local commit containing this handoff is the final workstream commit (reported to the
user; use `git log -1` on this branch). No protocol migration or ABI/source correction
was necessary. Existing pinned file hashes remain unchanged.

## Owned changes

- `backend/app/payments/base.py`: reusable synchronous transport.
- `backend/app/payments/base_rpc.py`: explicit single-request HTTP RPC and minimal ABI
  codec driven by the existing pinned JSON. Provider retries are disabled.
- `backend/app/payments/base_config.py`: public operator address for key-free inspection,
  optional signer loading, redacted numeric errors, bounded gas/fee settings.
- `spikes/payments/run.py`, `reclaim.py`, `offline.py`, `examples.py`, `README.md`:
  terminal client, isolated payer staging, synthetic RPC double and runnable examples.
- `backend/tests/payments/test_base_transport.py`, `test_payment_lab.py`: dedicated
  encoding/signature, reconciliation, restart, CLI and redaction tests.

No dependency or lockfile change: installed web3/eth-account/eth-abi/rlp dependencies
suffice. No changes to executor.py, journal.py, catalog.py, startup, public DTOs/endpoints,
frontend, shared payment runbook, or application adapter selection.

## Shared interface and injection

```python
from app.payments.base import BasePaymentTransport
from app.payments.base_config import BasePaymentConfig

config = BasePaymentConfig.from_env(explicit_environment, include_signer=False)
transport = BasePaymentTransport(config, rpc=my_rpc_double)
domain = transport.verified_usdc_domain()
```

Injected RPC implements `request(method: str, params: list) -> JSON-RPC result` (not the
outer response envelope). Without injection, the explicit HTTP provider contacts only
the supplied URL when a method is called. Imports and construction perform no network,
environment loading, or worker startup. The constructor reads local pinned ABI files.
An absent URL without injection fails with a redacted configuration error. No automatic
provider detection or `.env` loading. `BaseTransportError` has capability-free messages;
untrusted RPC exception messages/causes are suppressed.

Existing `PaymentTransport` methods and dataclasses are unchanged:

- `pending_nonce(operator)` checks chain and returns the RPC pending nonce. Allocation
  and reuse belong to the journal; the transport never chooses a fresh nonce.
- `prepare_transaction(action, terms, nonce, buyer_signature=None)` implements operator
  fund/capture/void: exact frozen PaymentInfo/hash/nonce validation; preflight; raw
  ERC-3009 authorization verification; pending simulation; bounded EIP-1559 gas/fee
  estimate; signing. Returns existing `SignedTransaction`, never sends or journals it.
  Signing requires enabled testnet configuration and a dedicated operator key.
- `broadcast(raw_transaction, explicit_testnet_broadcast=False)` requires both gates,
  checks chain, sender, destination, transaction type/value/fee bounds and allowlisted
  selector, sends once, and requires the returned hash to match the saved bytes.
- `reconcile(action, terms, transaction_hash)` returns existing `ChainObservation` for
  all four actions. Checks canonical receipt inclusion, full transaction input/sender,
  exact payment event/amount/zero capture fee, state at receipt AND observed head,
  token-store balances, and a final canonical-block recheck. Missing receipt is pending;
  conflicting/unavailable evidence is uncertain; noncanonical receipt is orphaned.
  A reverted receipt is failed only at the accepted confirmation threshold.

Extra APIs:

- `verified_usdc_domain() -> dict`: chain/code/decimals/name/typehash/separator reads at
  one canonical block. Computes Circle version-2 domain and compares actual observed
  `DOMAIN_SEPARATOR`. No cached guessed domain and no mock fallback.
- `preflight(terms=None, *, action=None) -> dict`: read-only pinned deployment selectors,
  PaymentInfo typehash, collector binding/type, token-store implementation code, USDC
  domain/decimals, frozen real-payer and zero-payer hashes, EOA parties, balances/state.
  With an action also requires exact starting custody, unused funding authorization,
  valid deadline and positive signer gas balance. Without terms it checks deployment
  compatibility only; without action it reports balances without requiring unused funds.
- `calldata(action, terms, buyer_signature=None) -> str`: pure pinned-ABI encoding;
  funding callers must verify the supplied signature first. Treat funding calldata as
  private because it contains the buyer capability.
- `transaction_request(action, terms, nonce, buyer_signature=None) -> dict`: unsigned
  preflight/simulation/fee-estimated type-2 transaction. Reclaim uses the payer as sender.
- `broadcast_reclaim(raw, terms, *, explicit_testnet_broadcast=False)`: validates exact
  reclaim calldata and accepted payer, sends only pre-signed bytes, never loads buyer keys.

`SignedTransaction.raw_transaction`, funding calldata, buyer signatures and private
journal rows are capabilities. Never send them to logs, public DTOs, agents or reports.
Public chain data and transaction hashes are not funding evidence without reconciliation.

## Protocol evidence and deliberate limits

The reviewed [official pinned AuthCaptureEscrow source](https://github.com/base/commerce-payments/blob/b748fdd7a830a655a19a530edcf2a94b9dc7d25f/src/AuthCaptureEscrow.sol)
and local collector/source copies establish the interface: `authorize` collects exactly
maxAmount through ERC-3009; capture uses absolute feeAmount=0; void is operator-only;
reclaim is payer-only after authorization expiry; refundableAmount is captured accounting.
The payer-agnostic authorization nonce and real-payer payment hash use existing helpers.
Existing provenance tests verify the unchanged pinned source/interface hashes.

Preflight checks pinned addresses, required selector presence and read behavior. **It is
not full runtime bytecode attestation**: the repository has interface transcriptions,
not compiler deployment artifacts/runtime hashes. Independently compare deployed code
and immutable/linkage details with the official pinned deployment before live proof.
No version change, proxy fallback, unpinned token, mainnet, fees, partial capture or refund
path was introduced.

State/balance calls use EIP-1898 `{blockHash, requireCanonical: true}`. An endpoint without
those historical reads fails closed; there is no fallback to latest. Receipt and current
state disagreement remains held even if a past event was valid. A state change later in
the receipt's block may therefore conservatively require manual investigation. Balance
snapshots corroborate events/state; this transport does not infer settlement solely from
a wallet delta or claim an RPC response is a cryptographic light-client proof.

Gas uses estimate +20%, max fee `2*baseFee + priority`, configured ceilings, and a further
balance margin for L1/operator fees. This is a conservative demo allowance, not a precise
quote of all Base fees. The accepted two confirmations are not L1 finality.

## CLI and recovery

All commands require a durable `--payment-id`; all have help/examples. Defaults perform
inspection, with `prepare --save-fixture` explicitly persisting terms and `reconcile`
persisting observations. `--dry-run` never reserves/signs/sends. Reusing an ID returns
original terms, ignoring new fixture-creation flags. Salt/deadlines never regenerate.
Actual submission requires `--broadcast-testnet` plus `ENABLE_TESTNET_BROADCAST=true`;
this work did not exercise that path against any live endpoint.

The separate `--offline --simulate` path uses only public synthetic scalars and an
in-process RPC double. Its multi-process example reconstructs synthetic receipts from
saved offline bytes, with clearly labelled output and no simulated transaction IDs or
explorer URLs. This reconstruction is strictly a test fixture, never live reconciliation.
Offline journal entries are rejected by the live CLI path.

Exit codes: 0 successful inspection/confirmed reconciliation/new submission; 2 invalid
usage/configuration/precondition; 3 unresolved/pending/orphaned reconciliation; 4 failed
or invalidated operation. New submission with code 0 still means pending, not paid.

Missing receipt is not failure. The existing executor saves signed bytes/hash before
send and serializes signer nonces. After a timeout/restart, the same operation is
reconciled without another signature/send. **There is no rebroadcast, replacement,
fee bump or fresh-nonce recovery command.** A crash between durable submitted state and
actual send can remain pending forever. Manual executor-owner recovery is required;
never delete state, reset a nonce, or choose a new salt to escape ambiguity. Reorgs keep
holds and do not undo effects or rerun work. A previously confirmed account moved to an
audit hold is not automatically released by a recovered receipt; reconcile journal and
account state deliberately. Expiry does not return funds.

Payer reclaim is executable in the isolated lab: `stage_reclaim` claims the original
operation, reserves the payer's nonce via existing journal methods, simulates/signs with
the isolated buyer, and saves existing `SignedTransaction` before releasing the lease.
`ReclaimSubmission` routes only its broadcast to `broadcast_reclaim`; the unchanged
executor owns submission/reconciliation/confirmation. On an inspection/preparation
interruption the existing reservation remains; after saving bytes they are reused.
No server/operator code ever signs a catalog buyer transaction.

## Validation actually run

- `uv sync --locked --project backend` — passed; required sandbox approval for uv cache.
- `uv run --locked --directory backend pytest tests/payments` — **123 passed**; one upstream
  websockets deprecation warning. Includes all existing payment tests and 74 new tests.
- `uv run --locked --directory backend ruff check .` — passed.
- `uv run --locked --directory backend ruff format --check .` — passed, 99 files.
- `backend/.venv/bin/ruff check --config backend/pyproject.toml spikes/payments` and
  corresponding `ruff format --check` — passed, 5 laboratory Python files.
- `backend/.venv/bin/python spikes/payments/examples.py` — 27 separate CLI subprocess
  commands completed: independent capture, void and expiry/reclaim journeys with
  temporary journals/empty explicit environments and synthetic RPC only.

Tests cover manually padded Solidity calldata, an independent Web3 ABI encoding,
fixed synthetic ERC-3009 and transaction vectors, manually constructed EIP-712 digest
and RLP/secp256k1 recovery, domain/chain/config mismatch, wrong sender/deployment/code,
expiry/gas bounds, full fund/capture/void/reclaim event/state/balance observations,
reverted/pending/missing/conflicting/orphaned evidence, mid-read reorg, exact-byte
outbox restart after lost response, payer nonce separation, all CLI help/missing-config/
dry-run paths, disabled broadcasts and redacted errors/output. Existing protocol,
journal and catalog-payment tests remain in the focused suite. Self-review checked signer/nonce identity, canonical evidence, capability redaction,
submission defaults and ownership boundaries; `git diff --check` passed. The RPC double does not
execute EVM bytecode; tests do not establish live deployment success.

## Requests to Conversation 3 and 4

Conversation 3:

1. Keep the current `PaymentTransport`, `SignedTransaction`, `ChainObservation` boundary.
   This transport returns evidence only; your guard/completion callbacks still own
   catalog eligibility, ledger atomicity, funding jobs, amendment gates and holds.
2. Consider a signer-selection/staging hook for payer reclaim. The current executor
   always reserves `terms.payment_info.operator`; do not send a reserved reclaim through
   the ordinary server preparation path. The isolated lab's staging wrapper is documented
   above and leaves your modules unchanged. Do not copy its buyer key handling into catalog.
3. Missing receipts, RPC failures and changing canonical evidence must retain holds.
   Any future identical-byte rebroadcast needs an explicit durable executor operation;
   the transport intentionally does not implement retries. Recovering a prior confirmed
   audit hold also needs an explicit account-state policy, not another money booking.
4. Preflight performs multiple bounded RPC calls. Ensure the executor lease comfortably
   covers configured RPC latency or add lease renewal under your ownership; each HTTP
   request has a 15-second timeout and no retries. Expired leases must still prevent send.

Conversation 4:

1. Select `BasePaymentTransport` only through your explicit base_sepolia opt-in wiring;
   preserve mock/historical behavior. No `main.py`/factory/startup changes were made here.
2. Pass `transport.verified_usdc_domain` to catalog funding preparation. It must be invoked
   before live typed-data issuance; do not substitute the mock domain on RPC failure.
3. Add/document public `BASE_OPERATOR_ADDRESS` for key-free preparation. Existing config
   construction remains supported. Keep operator and buyer keys server-side/lab-only,
   respectively; never expose capabilities in DTOs or frontend bundles.
4. Reconcile shared status/runbook documentation after integration: those files still
   describe the prior phase because shared docs are your ownership. This workstream and
   spikes/payments/README.md describe the newly implemented offline functionality.

## Remaining separately authorized live proof

Use a new disposable setup and distinct live fixture IDs/journal. Verify chain 84532,
actual pinned code/collector linkage, token domain/decimals, EOA parties, token-store
custody and gas/USDC balances; confirm endpoint historical/EIP-1898 support. Then observe
capture-a fund → restart → full capture and independent void-b fund → full void, each
100000 atomic test USDC with matching events, canonical receipt threshold, state and
balance deltas. Simulate capture from provider and establish rejection. Exercise lost
response/duplicate recovery and a separate expiry/reclaim fixture. Record only actually
observed transactions as live evidence, with real explorer links. None exists from this
workstream. Sponsor rules/eligibility remain unverified.
