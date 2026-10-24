# Aggregate brokerage migration handoff

Current primary product: `aggregate-brokerage-v1`; historical profiles retain their
accepted policy. Start with [workstream 06](../workstreams/06-data-broker.md): complete
migration map, route/examples, demo commands, mock signing boundary and validation.

The canvas at `/` now defaults to the live backend. Run the production frontend with
`BROKER_LOCAL_DEMO=1`, loopback BACKEND_URL, and distinct server-only worker/reviewer
tokens. `lib/run/live.ts` resumes and polls persisted events; `contract.ts` reexports
Pydantic-generated types. `live-run.tsx` reuses your Canvas/checklist/styles, with real
agreement, funding, review and evidence controls. Recorded rehearsal is separate.
UI prices, deadlines, permissions and bindings come from the server. 409 refreshes
without retrying consent. Unknown costs stay unavailable. The production build and
unit tests pass; actual browser validation is blocked by sandbox port binding and
must not be advertised as passed. Use `scripts/brokerage-smoke.cjs`, not invoice smoke.

## Historical catalog handoff

# Lucas — frontend handoff

The existing invoice workbench from main is preserved at `/api/jobflow`; it has
its own schema at `/api/jobflow/openapi.json`. This handoff describes the catalog
API at the root paths below. The merge does not connect the existing UI to catalog
orders or change invoice payment policy. Generated types for both remain separate.


Own the complete React/TypeScript frontend and buyer-wallet UI. No UI framework or wallet
library is imposed by this handoff. Start with mock/fake fixtures; live testnet observations
are **none**. Nikita owns payment signing infrastructure, operator execution and reconciliation.

## Integrated backend recipe

Automatic by default: compilation after request/answer, eligible fulfillment and evidence
rechecks after confirmed funding, deadline sweeps, and bounded payment processing. Five
independent lanes separate catalog/invoice deadlines, catalog work, payments and invoice work.
No browser call to a work endpoint is needed for ordinary progress. The default compiler is
offline and payments are mock. Run the README repaired journey to seed a fresh local corpus;
start the API with ORDER_DB_PATH and ARTIFACT_ROOT pointing to its database/evidence directory.
The harness uses an injected historical clock: create a new request for an interactive demo.
Keep PAYMENT_ADAPTER=mock, ENABLE_PAID_MODELS=false and ENABLE_TESTNET_BROADCAST=false.

The Base transport and asynchronous settlement are implemented and exercised with synthetic
RPC, including fund → restart → repair → capture and independent fund → human review → void.
**Observed real testnet transactions: none.** Mock capture/release remains synchronous and atomic.

`/health` retains API 0.4.0, `catalog-api-v1` and `catalog-payments-v1`. Existing capability values
now describe actual startup selection: `disabled` = implemented Base adapter unselected (mock);
`unavailable` = selected Base missing configuration/signer or failed read-only preflight;
`ready` = configured, signer present, startup preflight passed. `live_settlement_enabled` is
true only for ready Base plus explicit broadcast opt-in. Read these as startup capabilities,
never transaction evidence. Restart after correcting unavailable configuration. Every submission
still preflights the accepted terms; a later failure remains failed/uncertain, never mock success.
No DTO field, route or enum was added; the health default changed from planned to disabled.

Trusted server-side callers still handle these existing routes:

| Credential / caller | Operations |
| --- | --- |
| INTERNAL_API_TOKEN via X-Internal-Token | Provider offers (`/internal/orders/{id}/offers`), provider amendment approvals (`/internal/orders/{id}/approvals`), explicit failed-job retry (`/internal/orders/{id}/retry`). Manual compile/work/payment-work endpoints remain useful for diagnostics or a `run_worker=False` test app. |
| REVIEWER_API_TOKEN via X-Reviewer-Token | Cited, bound decisions at `/reviewer/orders/{id}/decisions`; protected historical inspection. Must differ from the internal token. |
| Buyer wallet | Exact prepared ERC-3009 typed-data signature, submitted through the public funding route; no operator key. Mock flow uses explicit simulate instead. |
| Backend operator | BASE_OPERATOR_PRIVATE_KEY, RPC and opt-in config; no API caller can supply operator authority. |

Lucas owns the authenticated frontend/server bridge and its role checks. Forward only the
specific authorized protected request server-side; do not expose a credential-forwarding proxy.
Catalog customer routes still lack authentication/tenant isolation: localhost demo only. The
invoice session/token policy remains isolated at `/api/jobflow`.

Minimal customer requests (replace IDs and revisions with the current server response):

```http
POST /requests
Content-Type: application/json

{"prompt":"Find storage products under 2 kg and unit price at most USD 40.","corpus_id":"storage-2026","idempotency_key":"request-1"}
```

Poll `/requests/{id}` until clarification or ready. Answer the returned question ID, poll until
ready, then `POST /requests/{id}/quotes` with `{expected_revision, idempotency_key, payer}`.
`payer` is optional only in mock mode. Accept using the route table below. For mock funding:

```json
{
  "expected_revision": 1,
  "expected_binding": {"snapshot_id": "snapshot-from-order", "evidence_revision": 1, "delivery_version": 0},
  "idempotency_key": "fund-1",
  "funding_attempt_id": "attempt-from-preparation",
  "payment_hash": "hash-from-preparation",
  "simulate": true
}
```

Send this to `/orders/{id}/funding-authorizations` after preparation. The initial saved response
may still be funding_pending; poll until funding is confirmed/simulated, then follow
available_actions for evidence and review. Protected manual payment work has no request body:

```http
POST /internal/payments/work
X-Internal-Token: <server-only internal credential>
```

Response: `{processed: number, simulated: boolean}`; processed counts attempted/audited
operations, not confirmed transfers. It is bounded to 20, while automatic turns use limit 1.

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
request input. `/internal/payments/work` accepts no body and returns `{processed, simulated}`. The boolean
reflects the selected service mode; inspect each payment's frozen terms when reading older orders.
Payment turns run independently every 0.25 seconds after the preceding bounded call finishes.

Keep document scope: prompt/clarification, quote approval, progress, PDF/source highlights,
targeted complaints, request-bound evidence upload/approval, explicit additional-work acceptance
and reviewer evidence table/controls. Source uncertainty, consent and human review are not
operational failure (red). Unsupported complaints have no fee; substantive replacements wait
for confirmed parent return before their funding/work. Negotiated exceptions do not rewrite facts.

Completion: all state fixtures render distinctly; stale/replayed responses and wallet rejection
are handled; privileged credentials stay server-side; a buyer can approve work, inspect citations,
answer a repair request and follow payment status without any live-payment success claim.

## Recovery and limits

Exact response-loss replay keeps the same key and payload; it can return an older immutable
response, so refetch current order/payment before offering another action. 409 requires refetch
and renewed explicit action. Restart recovers durable leases and reconciles the saved transaction
hash/nonce without another signature/send. Submission disabled or missing signer does not block
inspection of other submitted payments when a transport is available. Startup does not load .env.

Uncertain/reorg-held funds stay held. A submitted capture cannot be cancelled by a late complaint;
the complaint goes to human review while confirmation may still book once. An orphaned receipt
or crash after persisting submitted but before sending needs Nikita's manual recovery: there is
no automatic rebroadcast, replacement, nonce reset or refund route. Replacement child signing/work
waits for confirmed parent void and its own fixed funding deadline; waiting never extends it.
Payer reclaim is available only in the separately authorized lab, not a catalog route.

[Integration validation and exact merged SHAs](../workstreams/04-integration.md).
