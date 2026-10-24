# Offline frontend fixtures

`payments/<state>.json` is a complete `PaymentView` response for each of the 12 payment
account states. All files validate against `app.contracts.payments.PaymentView`. They use
`mode: "mock"`, `simulated: true`, synthetic addresses/hashes, no transaction hashes and no
explorer links. They contain no signatures, signed transactions, keys or RPC credentials.

These are independent rendering fixtures, not a transaction history or evidence of chain
activity. Pending, failed, uncertain and reorg examples let the UI develop before a live
adapter is enabled; they do not claim the synchronous mock naturally emits every state.
The fixed timestamps are for deterministic rendering. Use an injected fixture clock; do
not infer current availability from these historical timestamps.

Run the fixture API from the repository root without a frontend framework:

```sh
uv run --locked --directory backend python ../tools/frontend_mock.py --port 4173
curl --fail 'http://127.0.0.1:4173/orders/demo/payment?state=funding_pending'
curl --fail http://127.0.0.1:4173/__mock/states
```

| Fixture/state | Display | Customer action |
| --- | --- | --- |
| `blocked_parent` | Replacement waiting for parent return | Wait/refetch; no child signature. |
| `awaiting_signature` | Accepted; wallet signature needed | Prepare/sign only when server action allows. |
| `funding_pending` | Funding submitted; awaiting confirmation | Poll; no fulfillment/paid claim. |
| `funded` | Funds held; provider not yet paid | Follow order/evidence/review actions. |
| `capture_pending` | Settlement pending | Poll; do not promise cancellation. |
| `captured` | Payment completed (simulated in these fixtures) | Inspect delivery/payment evidence. |
| `void_pending` | Return pending | Poll; do not show returned yet. |
| `voided` | Funds returned (simulated here) | Inspect final outcome. |
| `uncertain` | Outcome unknown; reconciliation needed | Poll/escalate; no automatic fresh signature. |
| `failed` | Payment action failed, or unfunded authorization expired | Show error; follow server actions, not guessed retries. |
| `expired_not_returned` | Capture expired; return available | Explain reclaim/recovery; never label returned. |
| `reorg_hold` | Chain evidence changed; human recovery needed | Hold and refetch; never rerun payment/work. |

The fixture API performs no wallet action. The main app's current mock capture/release completes
atomically; terminal pending/reorg fixtures exercise the integrated asynchronous Base states.
These files remain simulated and unchanged; they are not observed chain evidence.

`expired_not_returned` represents previously held funds; unfunded expiry is failed/human review.
A reviewer release without held funds returns 409.

Render the simulated badge for every file. Treat `amount_atomic`, `salt`, blockchain
timestamps, nonces, block numbers and balances as decimal strings; use `BigInt` only inside
formatting/wallet boundaries. The USD display quote is USD 15.00 and the explicit settlement
amount is 15000000 atomic USDC, not 1500 token units or the isolated 0.10 payment laboratory.

See [Lucas handoff](../../docs/handoffs/lucas.md) for routes, signing and error handling.
