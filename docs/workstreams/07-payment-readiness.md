# Workstream 07 — isolated Base payment readiness

Offline preparation is complete. **Public RPC preflight: not run. Observed testnet
transactions: none. Live execution remains unvalidated and separately authorized.**
No endpoint or public payer/operator/provider addresses were supplied for this task.
Missing configuration is not a successful preflight. No private `.env`, existing
wallet or existing database was opened. All executed journals were temporary and
all executed signing used public synthetic scalars with an injected RPC.

## Baseline, ownership and integration handoff

Continued the existing clean worktree `order-to-cash-payment-readiness` on
`codex/payment-readiness`, based exactly on
`39dd58602b3f8ac0a7906b4db4ddbbdb57b3d981`. The updated prompt was read after interruption;
the uncommitted lab work was retained. No other worktree was edited, no application
branch was merged, and no push, broadcast, funding transfer, wallet creation, paid
service or deployment occurred.

Read the root AGENTS.md, HACK.md, PAYMENT_SPIKE.md, PAYMENT_RUNBOOK.md,
INTEGRATION_CHECKPOINT.md, Nikita handoff, workstreams 02/04 and laboratory README.
There are no nested instructions under the owned paths. Read Jeff's HANDOFF.md and
POLICY_DELTA.md using `git show 5c8dc726326bb9e3539cdb51e5aec221868223bc:<file>`.
That merged broker profile uses mock/USDSIM, 600-second reviews and a 1,800-second
case bound. Its tests/authorizations are not Base evidence. Prompt 6 owns that
application merge, startup reconciliation and review/capture scheduling. This branch
does not substitute main for the integrated Base baseline or alter any policy.

The user relayed judges' option 2 guidance permitting direct Commerce Payments.
This is **relayed guidance**, not independently verified eligibility or full x402
compliance. No facilitator, CDP migration, custom contract or second ledger is added.

Owned changes only:

- `spikes/payments/run.py`: unfinished reserved/signed execution or reconciliation
  returns exit 3. Previously these paths returned 0 despite no submission/completion.
  Successful inspection still returns 0; a new submitted operation still returns 0
  with an explicitly pending state, never a confirmation claim.
- `backend/tests/payments/test_payment_readiness.py`: four targeted cases reproduce
  that exit-code defect and the documented lease/crash limitations; five more
  validate the read-only recipes with injected responses, including generic errors,
  wrong-sender errors and timeouts that must not count as provider rejection.
- Laboratory README and this handoff document the behavior and future run.

Shared implementation tested, unchanged from baseline:

| File | Git blob at tested baseline |
| --- | --- |
| `backend/app/payments/base.py` | `3255366ec8b96682d3725d67298e090d9ef3b9bf` |
| `backend/app/payments/base_config.py` | `d32b1ccf21c19a33f77411a0bc8ab8ca8cdab24a` |
| `backend/app/payments/base_rpc.py` | `1a4181e3b54776dd78bb5526157a75bf370f10c1` |
| `backend/app/payments/executor.py` | `a718b1369019b582a6157969e05b6fbbf51b90cd` |
| `backend/app/payments/journal.py` | `3e6d6422b6aff613eecd865eb370b63eeb55c3e1` |

Last modifying commits: transport/config/RPC workstream
`a23f999e855964ff094acde137f35a2148895b7b`; executor
`39dd58602b3f8ac0a7906b4db4ddbbdb57b3d981`; journal
`0326ae6f93e3dca204f83c1a44fe3d5502b83d1c`.

The commit containing this file is the lab-only integration commit; obtain its exact
SHA with `git rev-parse codex/payment-readiness` and use the completion-message SHA,
not a moving application tip. Prompt 6 should integrate that commit in its own tree.
No merge is performed by this task. If shared payment interfaces change, rerun the
entire `tests/payments` suite, the 27-process lab examples and both Ruff commands
below on the combined tree. In particular rerun `test_base_protocol.py`,
`test_base_transport.py`, `test_journal.py`, `test_payment_lab.py` and
`test_payment_readiness.py`; then Prompt 6 must run its application HTTP/lifespan
settlement and scheduling tests. This baseline pass does not certify changed code.

## Validation actually executed

Commands run from this repository root:

```sh
uv sync --locked --project backend
uv run --locked --directory backend pytest tests/payments
backend/.venv/bin/python spikes/payments/examples.py
uv run --locked --directory backend pytest tests/payments/test_payment_readiness.py --tb=short --show-capture=no
uv run --locked --directory backend ruff check .
uv run --locked --directory backend ruff format --check .
backend/.venv/bin/ruff check --config backend/pyproject.toml spikes/payments
backend/.venv/bin/ruff format --check --config backend/pyproject.toml spikes/payments
git diff --check
```

| Evidence | Result |
| --- | --- |
| Locked environment | Passed, no dependency or lockfile changes. |
| Existing payment suite before changes | 160 passed in 11.91s. |
| Targeted baseline reproduction | 3 failed / 1 passed after correcting a test-fixture field reference; reserved/signed reconciliation and lease-expired submission returned 0 instead of 3. Crash limitation reproduced successfully. |
| Targeted tests after lab-only fix | Initial 4 passed in 0.26s; all 9 including recipe validation passed in 0.31s. |
| Payment suite with fix | Final: **169 passed in 12.43s**, including the recipe tests; earlier 164 passed in 10.85s. One upstream `websockets.legacy` deprecation warning. |
| Offline examples | 27 separate CLI processes: independent capture-a, void-b and expiry-c, fresh temporary journals and empty explicit environments. All passed. |
| Help | Root and all eight subcommands exercised by the existing subprocess help tests; preflight/prepare/capture help also inspected directly. Parsed all 35 README/handoff CLI invocations against argparse without executing them; flags match. |
| Ruff | Backend lint/format passed (108 Python files); lab lint/format passed (5 files). |
| Public-only and provider probe recipes | Executed only with injected responses: no key lookup, signing/send, journal mutation or leaked provider error. Expected InvalidSender succeeds; generic error/wrong sender/timeout fail closed. Not EVM evidence. |
| Real RPC, canonical deployed state, network latency, provider rejection | Not observed. |
| Testnet receipts, real hashes, provider receipt/buyer return | None. |

The existing tests cover exact retries, signature/term mismatches, pending receipts,
lost-response uncertainty, canonical conflicts/reorgs, preserved nonce/bytes on
restart, full capture/void and payer nonce separation for reclaim. No expected
outcomes were supplied to runtime models. This task ran no models.

OfflineRpc reconstructs synthetic receipts from saved submitted bytes in CLI examples.
It is not an EVM or a deployment test. The crash test deliberately disables that
reconstruction; otherwise it would hide the unsent-submission recovery limitation.
Offline reports suppress synthetic transaction hashes/explorer links.

## Reproduced lease and crash limits; shared follow-up proposals

Run the targeted test command above to reproduce both limits without waiting or
network access. A separate injected-RPC counter probe using the unchanged transport
observed these sequential request counts (not measured real latency):

| Stage | Requests |
| --- | ---: |
| Deployment-only preflight | 15 |
| Frozen-fixture preflight | 26 |
| Funding action preflight | 27 |
| Funding `prepare_transaction`, including action preflight/simulation/gas reads | 32 |
| Successful funding reconciliation | 13 |

The executor additionally makes two pending-nonce reads before preparation. At
four seconds per successful RPC, that leased section takes 34 × 4 = **136 simulated
seconds**, exceeding the 120-second lease although every request is below the
15-second per-request timeout. The CLI also does 27 funding-preflight reads before
the lease. The test advances only the journal clock, keeps synthetic chain time fixed,
and observes: reserved operation, nonce 0 retained, no durable signed bytes/hash,
no broadcast, unchanged payment terms. Signing can finish in memory after expiry;
the executor fences its persistence and submission. A subsequent faster attempt
reuses the original reservation/nonce. No lease renewal is implemented.

This fault injection isolates lease expiry; it does not advance chain time. On a
real chain, preparation and funding reads also consume the original 300-second
funding window. Measure the whole prepare-to-fund path, not just one RPC or the
leased section; an added preflight must fit the remaining time. Do not extend the
frozen window if RPC latency consumes it.

**Shared proposal for coordination, not implemented:** in `journal.py`, add
`renew_claim(db, operation_id, token, lease_seconds=120)` as a compare-and-update
requiring the same token and an unexpired lease. In `executor.py`, renew through
short independent transactions while leased RPC work runs, e.g. every 30 seconds,
stop renewal on completion, and preserve all ownership/eligibility checks before
persisting signed bytes and before the durable submission transition. A worker
that loses ownership cannot revive its lease or submit. Reclaim staging needs the
same treatment. Test slow reads, renewal failure, competing workers and stale
completion with an injected clock before integration. Separately bound total
preparation time/recheck deadlines before signing and submission: renewal alone
does not extend the funding or authorization window. Do not merely increase all
timeouts or remove fencing. The actual endpoint still needs measured latency.

The crash test interrupts after signed bytes/hash and `submitted` are committed,
before the transport sends anything. After restart, repeated reconcile/action
requests preserve the same ID, terms, bytes, hash and nonce, leave funding pending,
make zero sends and book zero effects. This is safe against duplicate submission
but can remain pending forever. It is not evidence that money was sent or returned.

**Shared proposal for coordination, not implemented:** a dedicated, explicitly
authorized recovery operation in `PaymentExecutor`/`PaymentJournal` should audit
the original operation and serialize access to its signer. Inspect the saved hash,
canonical transaction/receipt/event/state, latest and pending signer nonce, original
deadline and exact signed-byte hash. A matching receipt follows normal reconciliation.
Missing receipt/transaction alone cannot prove absence. A nonce consumed by another
transaction, conflicting state, expiry or reorg requires manual resolution. If an
owner authorizes rebroadcast, it must be an idempotent audited resend of **exactly
the persisted bytes**, never a fresh signature/salt/payment ID/nonce or fee bump.
Keep submission irrevocable to application input. Test crashes on both sides of
send and dropped responses. No recovery command currently exists in the lab.

Stop on uncertain/orphaned evidence, stale lease, an unresolved signer nonce, or
inconsistent balances/state. Inspect `status`, then reconcile the same operation.
Do not reset journals or rewrite states to clear a hold. The shared executor may
reconfirm a recovered receipt without automatically clearing the lab account's
audit hold; owner review must reconcile account and journal deliberately.

## Names-only setup checklist and missing observations

No values or credentials are requested in chat. Supply public inputs explicitly
for a later read-only run; provision secrets privately only for an authorized
disposable live run. The normal app uses buyer-wallet signatures; buyer private
keys belong only to this isolated laboratory.

| Configuration name | Role / requirement |
| --- | --- |
| `BASE_SEPOLIA_RPC_URL` | Missing; explicit Base Sepolia endpoint, historical calls/code/balances and EIP-1898 canonical block hashes. Never print an endpoint credential. |
| `BASE_CHAIN_ID` | Pinned 84532; no other chain. |
| `BASE_ESCROW_ADDRESS`, `BASE_ERC3009_COLLECTOR_ADDRESS`, `BASE_USDC_ADDRESS` | Keep the existing pinned defaults in PAYMENT_SPIKE.md; no overrides to another deployment/token. |
| `SPIKE_BUYER_ADDRESS` or `prepare --payer` | Missing public payer EOA. |
| `BASE_OPERATOR_ADDRESS` | Missing dedicated public operator EOA, distinct from payer/provider. |
| `BASE_PROVIDER_ADDRESS` | Missing public receiver, distinct from payer/operator. Provider needs no signing key. |
| `BASE_OPERATOR_PRIVATE_KEY` | Future private operator signer for fund/capture/void; never used by read-only checks. |
| `SPIKE_BUYER_PRIVATE_KEY` | Future isolated payer signer for ERC-3009 funding authorization and payer reclaim. Never an app-server buyer key. |
| `PAYMENT_JOURNAL_PATH` / `--journal` | New private ignored lab SQLite; absolute path recommended. Never catalog ORDER_DB_PATH, an existing wallet DB or an offline fixture promoted to live. |
| `PAYMENT_CONFIRMATIONS` | Default/minimum 2, maximum 100, frozen at preparation; not L1 finality. |
| `BASE_MAX_GAS` | 21000–1000000; default 1000000, transaction gas ceiling. |
| `BASE_MAX_FEE_PER_GAS` | 1–10000000000 wei; default 10000000000, fee ceiling. |
| `ENABLE_TESTNET_BROADCAST` | Must remain false for readiness/read-only checks. Later live execution needs explicit instruction plus this gate and the CLI flag. |

Payer needs at least 200000 atomic test USDC for two independent 100000 fixtures
if funded without relying on returns, plus another 100000 for optional C. Operator
needs Base Sepolia ETH for A/B funding and terminal transactions. Payer also needs
ETH for C reclaim; provider needs no gas for receipt. Gas sufficiency is measured,
not inferred from these token amounts. The builder requires estimated gas +20%
within the gas ceiling, `2*baseFee + priority` within the fee ceiling, and signer ETH
at least twice gas × max fee for a conservative L1-fee margin. This is not an exact
fee quote. No faucet request, transfer or wallet creation was performed.

Outstanding public observations: chain/deployed code and collector linkage,
token-store implementation/custody, six-decimal USDC and verified EIP-712 domain,
party identity and EOA checks, balances, canonical historical reads, RPC latency,
and provider non-authority. Selector/read compatibility is not full deployed
bytecode attestation; compare with the pinned v1.1.0 deployment/source before live
execution. All remain unobserved, including full bytecode verification.

## Later read-only preflight recipe (not executed against a network)

From the root, after explicitly supplying the public configuration above. These
commands do not load `.env` files. Set the journal path once for the authorized run;
if that path/ID already exists, inspect and reuse it rather than resetting it.

```sh
umask 077
export PAYMENT_JOURNAL_PATH="$PWD/private/payment-readiness/live-20261024.sqlite3"
export ENABLE_TESTNET_BROADCAST=false
time backend/.venv/bin/python spikes/payments/run.py preflight --payment-id live-capture-a-20261024 --journal "$PAYMENT_JOURNAL_PATH"
```

Before preparation, that CLI command checks deployment/domain only. It does not
claim configured party balances were checked. The following public-only probe
checks parties and historical reads without creating payment terms or a journal.
Run it three times serially, recording elapsed time and block identity. It imports
only existing packages; the names in the output are public. An exception is a failed
probe, never a reason to fall back to latest or enable signing.

```sh
backend/.venv/bin/python - <<'PY'
import json, os, time
from dataclasses import replace
from spikes.payments import run as lab
from app.payments.base import BasePaymentTransport
from app.payments.base_config import BasePaymentConfig
from app.payments.base_rpc import hex_bytes, quantity
from eth_utils import is_address, to_checksum_address

try:
    config = replace(BasePaymentConfig.from_env(include_signer=False), enable_testnet_broadcast=False)
    parties = [os.environ[name] for name in ('BASE_OPERATOR_ADDRESS', 'SPIKE_BUYER_ADDRESS', 'BASE_PROVIDER_ADDRESS')]
    assert all(is_address(p) and int(p, 16) for p in parties)
    parties = [to_checksum_address(p) for p in parties]
    assert len({p.lower() for p in parties}) == 3
    transport = BasePaymentTransport(config)
    started = time.monotonic()
    result = transport.preflight()
    rpc = transport.rpc
    block = rpc.request('eth_getBlockByNumber', [hex(result['block_number'] - 2), False])
    at = {'blockHash': block['hash'], 'requireCanonical': True}
    def call(abi, address, method, args=()):
        return abi.decode(method, rpc.request('eth_call', [{'to': address, 'data': abi.encode(method, args)}, at]))
    assert quantity(block['number']) == result['block_number'] - 2
    assert len(hex_bytes(block['hash'])) == 32
    for party in parties:
        assert rpc.request('eth_getCode', [party, at]) == '0x'
    assert hex_bytes(rpc.request('eth_getCode', [config.usdc_address, at]))
    assert call(transport.token, config.usdc_address, 'decimals') == (6,)
    store = call(transport.escrow, config.escrow_address, 'getTokenStore', (parties[0],))[0]
    assert int(store, 16)
    balances = {p: str(call(transport.token, config.usdc_address, 'balanceOf', (p,))[0]) for p in [*parties, store]}
    gas = {p: str(quantity(rpc.request('eth_getBalance', [p, at]))) for p in parties[:2]}
    assert rpc.request('eth_getBlockByNumber', [block['number'], False])['hash'].lower() == block['hash'].lower()
    print(json.dumps({'evidence': 'read-only RPC observation', 'deployment': result,
        'historical_block': block['number'], 'historical_hash': block['hash'],
        'usdc_balances': balances, 'gas_wei': gas, 'elapsed_seconds': round(time.monotonic() - started, 3)}))
except Exception:
    raise SystemExit('Public preflight failed; inspect configuration/RPC without exposing credentials.') from None
PY
```

No universal latency guarantee follows from three samples. Compare full fixture
preflight timing after preparation and receipt reconciliation timing after funding.
Stop if the measured preparation path risks the 120-second lease or remaining
funding window. The four-second/read failure above demonstrates why individual
successful requests are insufficient. Resolve with the shared owner before live use.

## Later bounded testnet execution (not authorized or executed here)

A and B are separate **100000 atomic test-USDC** payment-mechanics fixtures. They
are not funding for the migration's **$120 dataset order**, nor the earlier USD 15
catalog order. Each has its own salt/payment hash/authorization nonce and operation
IDs. Use the same absolute journal across processes and restarts. Freeze live terms
only immediately before its funding action; do not prepare A and B in advance.
Default funding window is 300 seconds, authorization 3600 seconds. Rerunning
prepare never extends the saved deadlines. Review emitted terms before proceeding.

Only after a later explicit instruction authorizes the actual live run and private
disposable signers have been provisioned, execute these commands **one at a time**.
The opt-in environment below applies only to its individual submission command.
They are documented commands, not commands run by this readiness task.

```sh
# A: prepare now, inspect terms, fund once; confirm before continuing.
backend/.venv/bin/python spikes/payments/run.py prepare --payment-id live-capture-a-20261024 --journal "$PAYMENT_JOURNAL_PATH" --save-fixture
backend/.venv/bin/python spikes/payments/run.py preflight --payment-id live-capture-a-20261024 --journal "$PAYMENT_JOURNAL_PATH"
env ENABLE_TESTNET_BROADCAST=true backend/.venv/bin/python spikes/payments/run.py fund --payment-id live-capture-a-20261024 --journal "$PAYMENT_JOURNAL_PATH" --broadcast-testnet
backend/.venv/bin/python spikes/payments/run.py reconcile --payment-id live-capture-a-20261024 --journal "$PAYMENT_JOURNAL_PATH"
# Start a fresh process/shell with the same explicit public configuration and journal.
backend/.venv/bin/python spikes/payments/run.py status --payment-id live-capture-a-20261024 --journal "$PAYMENT_JOURNAL_PATH"
time backend/.venv/bin/python spikes/payments/run.py preflight --payment-id live-capture-a-20261024 --journal "$PAYMENT_JOURNAL_PATH"
# Perform the provider-authority read-only probe below while A is held, then capture.
env ENABLE_TESTNET_BROADCAST=true backend/.venv/bin/python spikes/payments/run.py capture --payment-id live-capture-a-20261024 --journal "$PAYMENT_JOURNAL_PATH" --broadcast-testnet
backend/.venv/bin/python spikes/payments/run.py reconcile --payment-id live-capture-a-20261024 --journal "$PAYMENT_JOURNAL_PATH"
backend/.venv/bin/python spikes/payments/run.py status --payment-id live-capture-a-20261024 --journal "$PAYMENT_JOURNAL_PATH"
backend/.venv/bin/python spikes/payments/run.py preflight --payment-id live-capture-a-20261024 --journal "$PAYMENT_JOURNAL_PATH"

# B: only after A is resolved, prepare a distinct fixture and fund/void it.
backend/.venv/bin/python spikes/payments/run.py prepare --payment-id live-void-b-20261024 --journal "$PAYMENT_JOURNAL_PATH" --save-fixture
backend/.venv/bin/python spikes/payments/run.py preflight --payment-id live-void-b-20261024 --journal "$PAYMENT_JOURNAL_PATH"
env ENABLE_TESTNET_BROADCAST=true backend/.venv/bin/python spikes/payments/run.py fund --payment-id live-void-b-20261024 --journal "$PAYMENT_JOURNAL_PATH" --broadcast-testnet
backend/.venv/bin/python spikes/payments/run.py reconcile --payment-id live-void-b-20261024 --journal "$PAYMENT_JOURNAL_PATH"
backend/.venv/bin/python spikes/payments/run.py preflight --payment-id live-void-b-20261024 --journal "$PAYMENT_JOURNAL_PATH"
env ENABLE_TESTNET_BROADCAST=true backend/.venv/bin/python spikes/payments/run.py void --payment-id live-void-b-20261024 --journal "$PAYMENT_JOURNAL_PATH" --broadcast-testnet
backend/.venv/bin/python spikes/payments/run.py reconcile --payment-id live-void-b-20261024 --journal "$PAYMENT_JOURNAL_PATH"
backend/.venv/bin/python spikes/payments/run.py status --payment-id live-void-b-20261024 --journal "$PAYMENT_JOURNAL_PATH"
backend/.venv/bin/python spikes/payments/run.py preflight --payment-id live-void-b-20261024 --journal "$PAYMENT_JOURNAL_PATH"
```

Do not continue from fund to a terminal action until fund is canonically confirmed
and state is funded. Exit 0 on submission is not confirmation. For ordinary submitted
receipt delay only, perform at most five read-only reconciliations, separated by
10 seconds, stopping after a three-minute observation budget. If any call exceeds
30 seconds, stop issuing more and investigate latency. These are operator stop
rules, not hard cancellation of the underlying per-request 15-second calls. Exit 2/4,
reserved/signed exit 3, uncertainty or orphaning stops the live sequence immediately.
No automatic submission retries, new fixture or nonce escape. Restart is already
exercised by the separate CLI processes; additionally restart the shell before A's
terminal step and compare its saved public identity.

Repeat a successful action with its **exact same ID/journal/flags** only as an
explicitly authorized duplicate demonstration: the existing operation is reconciled,
not newly sent. Compare operation count, nonce and hash and confirm no new transfer.
Always use `reconcile` for routine observation; no signing flag is needed.

### Provider cannot capture: read-only paired simulation

While A is confirmed held and unexpired, run this probe with broadcast disabled.
It uses the frozen capture calldata, exact full amount/zero fee and one canonical
block. Operator simulation must succeed; provider simulation must return exactly
the pinned `InvalidSender(provider, operator)` ABI error. A generic RPC error,
timeout, expired/empty payment or missing error data is inconclusive and fails the
probe. No provider key or transaction signing is involved. This direct read-only
response check is necessary because the shared HttpRpc intentionally redacts RPC
error data; treating its generic exception as proof of non-authority would be wrong.

```sh
backend/.venv/bin/python - <<'PY'
import os
from pathlib import Path
from dataclasses import replace
from spikes.payments import run as lab
from app.payments.base import BasePaymentTransport
from app.payments.base_config import BasePaymentConfig
from eth_abi import encode
from eth_utils import keccak
from web3 import HTTPProvider

try:
    config = replace(BasePaymentConfig.from_env(include_signer=False), enable_testnet_broadcast=False)
    payment, _ = lab.read_payment(Path(os.environ['PAYMENT_JOURNAL_PATH']), 'live-capture-a-20261024')
    assert payment and payment.state == 'funded'
    assert payment.terms.settlement_terms.startswith('LABORATORY TESTNET.')
    transport = BasePaymentTransport(config)
    report = transport.preflight(payment.terms, action='capture')
    info = payment.terms.payment_info
    assert info.receiver.lower() != info.operator.lower()
    at = {'blockHash': report['block_hash'], 'requireCanonical': True}
    tx = {'to': payment.terms.escrow_address, 'data': transport.calldata('capture', payment.terms), 'value': '0x0'}
    provider = HTTPProvider(config.rpc_url, request_kwargs={'timeout': 15}, exception_retry_configuration=None)
    control = provider.make_request('eth_call', [{**tx, 'from': info.operator}, at])
    assert 'error' not in control and control.get('result') == '0x'
    denied = provider.make_request('eth_call', [{**tx, 'from': info.receiver}, at])
    expected = '0x' + (keccak(text='InvalidSender(address,address)')[:4] + encode(['address', 'address'], [info.receiver, info.operator])).hex()
    data = denied.get('error', {}).get('data')
    assert 'result' not in denied and isinstance(data, str) and data.lower() == expected.lower()
    block = transport.rpc.request('eth_getBlockByNumber', [hex(report['block_number']), False])
    assert block['hash'].lower() == report['block_hash'].lower()
    print('Read-only operator capture succeeded; provider rejected with exact InvalidSender at block ' + report['block_hash'])
except Exception:
    raise SystemExit('Provider-authority probe inconclusive/failed; do not capture or expose RPC error payloads.') from None
PY
```

### C: independent expiry/reclaim fixture, optional later milestone

After A/B, separately authorize C. Use a fresh ID with a 600-second authorization
to leave time for funding, confirmation and inspection; no need to shorten the
funding window below its normal 300 seconds. Wait for the observed chain timestamp
to reach its saved authorization expiry; never edit timestamps or use offline flags
on a live fixture. Expiry alone must still show held custody/provider unchanged.

```sh
backend/.venv/bin/python spikes/payments/run.py prepare --payment-id live-expiry-c-20261024 --journal "$PAYMENT_JOURNAL_PATH" --authorization-seconds 600 --save-fixture
env ENABLE_TESTNET_BROADCAST=true backend/.venv/bin/python spikes/payments/run.py fund --payment-id live-expiry-c-20261024 --journal "$PAYMENT_JOURNAL_PATH" --broadcast-testnet
backend/.venv/bin/python spikes/payments/run.py reconcile --payment-id live-expiry-c-20261024 --journal "$PAYMENT_JOURNAL_PATH"
# After its original authorization_expiry, inspect before reclaiming.
backend/.venv/bin/python spikes/payments/run.py preflight --payment-id live-expiry-c-20261024 --journal "$PAYMENT_JOURNAL_PATH"
env ENABLE_TESTNET_BROADCAST=true backend/.venv/bin/python spikes/payments/run.py reclaim --payment-id live-expiry-c-20261024 --journal "$PAYMENT_JOURNAL_PATH" --broadcast-testnet
backend/.venv/bin/python spikes/payments/run.py reconcile --payment-id live-expiry-c-20261024 --journal "$PAYMENT_JOURNAL_PATH"
backend/.venv/bin/python spikes/payments/run.py preflight --payment-id live-expiry-c-20261024 --journal "$PAYMENT_JOURNAL_PATH"
```

The payer signs/pays reclaim gas and uses its own reserved nonce. Require matching
PaymentReclaimed and actual return; the CLI's final `voided` state covers this full
return but its operation action remains `reclaim`. No refund execution is implied.

## Public evidence checklist for the later run

For each step retain an allowlisted report: evidence class (read-only/live), UTC
observation time, code revision, chain/pinned deployment/token, payment ID/hash,
public parties, amount, original salt/deadlines, operation action/nonce/state,
canonical block number/hash, confirmations and matching event/state. Keep a locally
computed candidate transaction hash in private recovery notes until observed on
RPC; include it in the public report, with an explorer link, only after actual
network observation. The CLI's submitted hash alone does not meet that test. Never
publish signed bytes, buyer signatures, funding calldata, credentials, raw RPC
responses or private journal contents. Do not export a whole transaction object:
its input includes the funding signature. Do not commit generated reports/journals.

| Step | Required matching canonical evidence and balance corroboration |
| --- | --- |
| Before A/B fund | Public payer/provider/token-store balances at a recorded canonical block; distinct frozen parties, 100000 exact amount, unused ERC-3009 nonce, valid deadlines, adequate gas. |
| Submitted fund | Saved operation/hash/nonce; no fulfillment/receipt claim. A transaction hash alone is insufficient. |
| Confirmed fund | PaymentAuthorized for exact hash/PaymentInfo/collector/100000; `(collected, capturable, refundable) = (true, 100000, 0)` at receipt and current canonical head; buyer −100000, provider unchanged, token store +100000. |
| Restart A | Same journal/payment/salt/hash/amount/parties/deadlines and funding operation nonce/hash; no new operation or transfer. |
| Provider test | Operator eth_call succeeds; provider returns exact InvalidSender at the same canonical block, no send. |
| A capture | PaymentCaptured for 100000 and fee 0; state `(true, 0, 100000)`; provider +100000, token store −100000. Refundable here is captured accounting, not money still held. |
| B void | Independent PaymentVoided for 100000; state `(true, 0, 0)`; buyer +100000 relative to funded balance, provider unchanged, token store −100000. |
| Exact replay | Same operation/hash/nonce/identity, no second transfer or booking. |
| C expiry/reclaim | At expiry state still held; after confirmed PaymentReclaimed state `(true, 0, 0)`, payer +100000, provider unchanged; payer sender/nonce verified. |

Match every transaction/event to the original frozen terms, zero native value,
correct sender (operator except payer reclaim) and pinned escrow. Use
`getTokenStore(operator)` for custody, not the singleton escrow balance. Reconcile
at the frozen confirmation threshold and recheck canonical receipt/block/state;
two confirmations do not establish L1 finality. Take before/after balance snapshots
with the preflight recipe and account for unrelated transfers. Event/state matching
is primary; balance changes alone do not establish which payment settled.

Inspect the public receipt separately for block/event details, decoding with the
pinned ABI; the current CLI summary omits those details and is not by itself the
complete evidence report. Missing/reverted/conflicting/noncanonical observations
stay pending/failed/held as applicable and never establish receipt or return.
All rows in this live checklist are pending observation at this handoff.
