# Base escrow payment laboratory — integrated offline, live proof pending

Owner: Nikita. Main payment is customer → provider using Base Commerce Payments on Base
Sepolia and a dedicated platform operator EOA. The contract holds funds; buyers/providers
trust our operator to apply accepted settlement policy. Neither escrow nor an AI verdict
verifies document quality. No x402, separate verification fee, hosted facilitator, Coinbase
Business Checkouts, custom Solidity/operator contract, partial capture, fees, refunds,
mainnet, arbitrary assets or account abstraction is in scope.

**Observed real testnet transactions: none.** This amendment authorizes local code and offline
tests only. No broadcast, deployment, token purchase or paid model call is authorized.

## Implemented offline versus observed live

The integrated application supplies immutable schema-4 payment terms and public funding/payment
routes, explicit mock authorization, automatic catalog dispatch, asynchronous capture/void gates,
durable signed outbox/nonces, atomic confirmation/booking, EOA signature verification, verified
USDC domain lookup, pinned ABI encoding, operator signing and receipt/event/state/canonical-block
reconciliation. `BasePaymentTransport` is selected only by explicit Base startup configuration;
mock remains default. Import/schema export never loads a private .env or calls RPC.

The executable isolated runner supports preflight, prepare, fund, status, capture, void, reconcile
and payer reclaim. Offline examples use independent capture/void/reclaim fixtures. Combined
application tests exercise the actual transport through synthetic RPC, funding → restart →
automatic repair/PDF delivery → capture and independent funding → human review → void.
Mock receipts remain mock. Fake-chain observations are test evidence, not live confirmations.

Live deployment/balance checks, actual RPC latency and observed testnet settlement are **not yet
verified**. The source pin and reviewed configuration addresses remain unchanged:

| Item | Configuration |
| --- | --- |
| Chain | Base Sepolia, 84532 |
| USDC | `0x036CbD53842c5426634e7929541eC2318f3dCF7e`, 6 decimals |
| v1.1 AuthCaptureEscrow | `0xf96815976523E00e65Be8f34cA5e64b4f41EB19c` |
| v1.1 ERC3009PaymentCollector | `0x8612dfdc421f80336cd14E8EF9cb1E765dB5ab88` |
| Source | v1.1.0, `b748fdd7a830a655a19a530edcf2a94b9dc7d25f` |

[Official pinned source](https://github.com/base/commerce-payments/tree/b748fdd7a830a655a19a530edcf2a94b9dc7d25f)
and [Circle token addresses](https://developers.circle.com/stablecoins/usdc-contract-addresses)
support configuration research. [ABI provenance](../backend/app/payments/abi/README.md)
discloses minimal interfaces transcribed from pinned Solidity, not full compiler artifacts.
Startup/action preflight implements read probes; before any authorized live broadcast,
independently verify RPC chain ID, deployed code/version compatibility,
collector.authCaptureEscrow(), USDC decimals/domain and balances. None of those live checks
has run. v1.1 capture takes absolute `feeAmount`, not v1.0 `feeBps`.

## Required authorization and execution

ERC-3009 ReceiveWithAuthorization binds `to=collector`, `value=PaymentInfo.maxAmount`,
`validAfter=0`, `validBefore=preApprovalExpiry`, and nonce equal to escrow.getHash of PaymentInfo
with payer zeroed. The actual payment hash uses the real payer. The pinned EOA collector
encoding is raw 65-byte r||s||v. Verify the USDC EIP-712 domain against DOMAIN_SEPARATOR; a
symbol or guessed name is insufficient. No separate token approval is needed; a plain USDC
transfer is not payment funding.

Persist the complete original terms and ordered deadlines (preApproval ≤ authorization ≤
refund); never extend them on retry. Full capture uses amount_atomic, feeAmount=0 and the
accepted fee receiver; full return uses void(originalPaymentInfo). Expiry permits payer
reclaim but is not returned money. refundableAmount accounts for captured value, not held cash.

The integrated executor persists signed bytes/hash before broadcast, serializes operator
nonces, reserves only one terminal action and reconciles ambiguous receipt/event/state evidence.
Never create a fresh payment/salt/nonce after a lost response. Two canonical confirmations are
the configurable demo threshold, not Ethereum/L1 finality. Reorg recovery must not reissue
transfers or fulfillment automatically. Signed capabilities stay private; reports are redacted.

## Separately authorized live acceptance

Use independent synthetic accepted-payment terms, 100000 atomic test USDC each. This is a
payment mechanics decision fixture, not an AI verdict or payment for a USD 15 catalog order.

| Scenario | Required observed evidence |
| --- | --- |
| A: fund | Matching PaymentAuthorized; collected=true; capturable=100000; refundable=0; provider receives nothing. |
| A: restart | Same durable ID/salt/terms; held state remains. |
| A: full capture | Matching PaymentCaptured for 100000, fee 0; capturable=0; refundable=100000; provider +100000. |
| B: independent fund/void | New ID/salt; held state then PaymentVoided; capturable=0; refundable=0; buyer +100000; provider unchanged. |
| Provider cannot capture | Read-only simulation from provider address rejects capture. |
| Duplicate/timeout/restart | Exact replay never creates another transfer; reconcile the same operation. |
| Expiry/reclaim | Separate short-lived fixture/local chain; expired capture remains held until return evidence. |

Use getTokenStore(operator) for custody balances; funds need not sit at the escrow singleton.
Matching payment-specific events/state are primary; balance deltas corroborate and account
for unrelated transfers. Keep offline/fake evidence separate from real reports. Only actual
observed transactions receive explorer links. Follow [runbook](PAYMENT_RUNBOOK.md).
Rehan independently verifies these outcomes and actual sponsor eligibility; track rules remain
unverified. The project uses Base Commerce Payments, not x402.
