# Lucas — frontend handoff

The existing invoice workbench from main is preserved at `/api/jobflow`; it has
its own schema at `/api/jobflow/openapi.json`. This handoff describes the catalog
API at the root paths below. The merge does not connect the existing UI to catalog
orders or change invoice payment policy. Generated types for both remain separate.


Own the complete React/TypeScript frontend and buyer-wallet UI. No UI framework or wallet
library is imposed by this handoff. Start with mock/fake fixtures; live testnet observations
are **none**. Nikita owns payment signing infrastructure, operator execution and reconciliation.

## Works now, simulated, planned

Works now: versioned DTOs/OpenAPI/generated types, exact quote/acceptance/funding routes, EOA
signature validation, explicit mock simulation, payment polling and all-state fixture API.
The main mock capture/release completes atomically; terminal pending/reorg states are fixtures
for the future asynchronous adapter. Live RPC/operator execution and testnet observation are
planned after this handoff. `/health` reports `contract_version=catalog-api-v1`,
`payment_policy=catalog-payments-v1`, `live_adapter=planned` and live settlement disabled.

## Contract files and runnable fixtures

- [OpenAPI](../openapi.json) and [generated TypeScript API types](../../frontend/api.generated.ts) are authoritative for
  complete request/response shapes. [Focused helpers](../../frontend/contracts.ts) demonstrate
  quote acceptance, current binding, typed-data preparation and signature submission.
- [Payment fixtures](../../frontend/fixtures/README.md) cover all 12 `PaymentAccount.state`
  values and validate as `PaymentView`. Every fixture is simulated, without a real transaction
  hash, explorer link or signing capability. Run `uv run --locked --directory backend python ../tools/frontend_mock.py --port 4173`.
  `GET http://127.0.0.1:4173/orders/demo/payment?state=uncertain` loads a state;
  `GET /__mock/states` lists them. The mock API makes no external calls.
- New accepted snapshots use schema 4 and `catalog-payments-v1`; catalog evidence policy stays
  v0.3. Existing schema-3 mock snapshots/saved responses remain readable and never become live
  obligations. Do not treat absent historical payment terms as permission to fund a new payment.

## Customer routes and shapes

Use the current order/revision/binding returned by the server. `OrderCommand` is
`{expected_revision, expected_binding: {snapshot_id, evidence_revision, delivery_version},
idempotency_key}`. A zero delivery version means no published delivery yet.

| Route | Request → response |
| --- | --- |
| `GET /corpora` | Registered corpora/source manifests. |
| `POST /requests` | `{prompt, corpus_id, idempotency_key}` → `RequestDraft`. |
| `GET /requests/{id}` | Current `RequestDraft`, questions and persisted deadline. |
| `POST /requests/{id}/answers` | `{expected_revision, idempotency_key, question_id, text}` → draft. |
| `POST /requests/{id}/quotes` | `QuoteRequest`: current revision/key and optional `payer` → `Quote`; Base requires payer. |
| `POST /quote-acceptance` | `{quote_id, customer_actor, idempotency_key}` → `OrderView`. |
| `GET /orders/{id}` | `OrderView`: order, server time, actions, review table and payment view. |
| `POST /orders/{id}/funding-preparation` | `OrderCommand` → `FundingPreparation`. |
| `POST /orders/{id}/funding-authorizations` | `OrderCommand` plus `funding_attempt_id`, `payment_hash`, and either `signature` or `simulate: true` → `OrderView`. |
| `GET /orders/{id}/payment` | `PaymentView`: payment account/terms, operations, explorer links, simulated flag, finality note. |
| `POST /orders/{id}/acceptance` | `OrderCommand` → order; requests capture only through deterministic gates. |
| `POST /orders/{id}/disputes` | `OrderCommand` + targeted `complaint` → order. |
| `POST /orders/{id}/answers` | `OrderCommand` + `text` → order. |
| `POST /orders/{id}/amendments` | `OrderCommand` + current request, actor/reason/relationship and bounded `pdf_base64` → order. |
| `POST /orders/{id}/approvals` | `OrderCommand` + `approval_id`, `actor`, `accept` → order. |
| `GET /orders/{id}/artifacts/{artifact_id}` | Exact historical/current artifact bytes. |

Compilation/work/offers/provider approvals/payment workers use `/internal/...`; reviewer
decisions use `/reviewer/...`. They require separate server-only credentials and a trusted
server bridge. There is no browser/model capture or void endpoint. Do not put internal/reviewer
tokens or operator keys into a browser or `NEXT_PUBLIC` variable.

## Quote and signing flow

1. Display specification, source limitations and exact commercial/payment terms before quote
   acceptance: chain 84532/Base Sepolia, USDC address/6 decimals, amount, payer, receiver,
   operator, escrow/collector, pricing rule and deadlines. USD 15 at the explicit 1:1 demo
   conversion is **15000000 atomic USDC**. The separate 0.10 test payment laboratory does not
   replace a USD 15 order's amount.
2. Accept the quote, then use current `OrderCommand` to prepare funding. The response freezes
   `funding_attempt_id`, `payment_id`, `order_id`, `binding`, `terms`, exact `typed_data`,
   `prepared_at` and `expires_at`. Acceptance is not a wallet signature or funded escrow.
3. Verify the connected chain and account match accepted terms. Ask the buyer wallet to sign
   exactly the supplied EIP-712 typed data. Never reconstruct or substitute recipient, amount,
   nonce or deadlines. A wallet rejection leaves the payment unfunded; show cancellation and
   allow a fresh server view. Do not invent a server-generated buyer signature.
4. Submit the 65-byte hex signature with the preparation's attempt ID/payment hash and current
   revision/binding/key. Never log/persist the signature in public fixtures, analytics or reports.
   A lost HTTP response should replay the exact same key/payload; do not automatically obtain
   a fresh signature/payment/salt. Signature validation or submission is not confirmed funding.
5. Poll the order and payment. Start progress only when server state allows; work waits for
   confirmed funding. Capture/void remain pending until confirmed evidence. Two canonical
   receipt confirmations are the demo threshold, not Ethereum/L1 finality.

For an offline flow, submit `simulate: true` with `signature` omitted/null instead of invoking
a wallet. It is explicitly mock-only. Real EOA signature validation is testable against the
mock typed-data domain `Mock USDC (no onchain authorization)`; such a signature cannot authorize
USDC on chain. Do not present this as live wallet funding. The typed-data domain `chainId` is
the numeric constant 84532; uint values in the message remain decimal strings.

All blockchain quantities (atomic amounts, salts, nonces, balances, block numbers and payment
timestamps) cross JSON as decimal strings. Do not coerce them through JavaScript `Number`.
Format USDC with six decimals; use `BigInt` internally where necessary and serialize strings.

## Displays, actions and errors

Use server `available_actions` for controls, including `prepare_funding` and
`submit_funding_authorization`; payment state alone does not grant authority.
Render order, delivery, source authority, dispute and payment state separately. The complete
state/display mapping is in the fixture README. Key distinctions: held funds have not paid the
provider; expired capture has not returned funds; failed operation does not prove empty escrow;
uncertain/reorg-held operations are not success. Unfunded authorization expiry becomes `failed`
with human review and no funding actions; `expired_not_returned` applies only to previously
funded payments. Reviewer release without held funds returns 409, not a fabricated void.
Only observed Base transactions get explorer
links; mock mode always displays **Simulated payment**.

Poll every `poll_after_ms` (currently 2000), stop on unmount, discard responses older than the
latest order revision and use `server_time` plus persisted deadlines. A current OrderView
reads order/payment/ETag coherently; do not merge its order with an older separate payment view. Delivery/dispute windows
are 60 seconds; answers do not reset them. An exact idempotent replay can return an older saved
response: refetch before presenting it as current.

| Status | UI handling |
| --- | --- |
| `409` | Stale revision/binding, changed payload/key or disallowed state: refetch; require renewed explicit action. |
| `422` | Schema errors: `{detail: "request validation failed", issues: [{loc, msg, type}]}`; semantic/signature errors: `{detail: string}`. |
| `404` | Missing request/order/artifact/payment: stop stale polling and show unavailable. |
| `403` | Invalid privileged credential: server bridge configuration/auth issue, never ask browser for token. |
| `503` | Capability/credential unavailable: show unavailable and keep fixture/mock path distinct. |
| Network timeout | Outcome unknown; retry identical request or refetch/reconcile. Never show paid/returned by inference. |

Domain errors use `{detail: string}`; validation errors never echo submitted signatures or
request input. `/internal/payments/work` accepts no body and returns `{processed, simulated: true}`;
the main app also advances bounded mock payment work in its one-second background loop.

Keep document scope: prompt/clarification, quote approval, progress, PDF/source highlights,
targeted complaints, request-bound evidence upload/approval, explicit additional-work acceptance
and reviewer evidence table/controls. Source uncertainty, consent and human review are not
operational failure (red). Unsupported complaints have no fee; substantive replacements wait
for confirmed parent return before their funding/work. Negotiated exceptions do not rewrite facts.

Completion: all state fixtures render distinctly; stale/replayed responses and wallet rejection
are handled; privileged credentials stay server-side; a buyer can approve work, inspect citations,
answer a repair request and follow payment status without any live-payment success claim.
