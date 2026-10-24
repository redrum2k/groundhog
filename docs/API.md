# Local catalog API — catalog v0.3 / payments v1

Run as in README.md. `/docs` and `/openapi.json` are the exact Pydantic/OpenAPI contracts.
Local demo only: customer authentication and tenancy are unimplemented. Automatic dispatch and
asynchronous Base settlement are integrated and tested offline; no successful live Base transaction is claimed.
New accepted snapshots use schema 4 and `catalog-payments-v1`; old schema-3 mock records
remain readable and never become live obligations.
The current API does **not** accept a manufactured accepted snapshot or client price.

API metadata version is 0.4.0; `/health` identifies `catalog-api-v1` and `catalog-payments-v1`.
Health reports implemented but unselected Base as `disabled`, selected but unconfigured/failed
preflight as `unavailable`, and configured signer plus successful startup preflight as `ready`.
`live_settlement_enabled` additionally requires explicit broadcast opt-in. This is startup
capability, not proof of funding or settlement. See PAYMENT_RUNBOOK.md.

## Request and acceptance

| Method/path | Body/result |
| --- | --- |
| GET `/corpora` | Available provider-owned source manifests. |
| POST `/requests` | RequestCommand: prompt, corpus_id, idempotency_key -> compiling RequestDraft. |
| GET `/requests/{id}` | Persisted draft, clarification, specification and deadline. |
| POST `/requests/{id}/answers` | ClarifyCommand: expected_revision, key, question_id, text. |
| POST `/internal/requests/{id}/compile` | RevisionCommand -> one clarification or typed specification; worker credential required. |
| POST `/requests/{id}/quotes` | QuoteRequest: current revision/key, optional payer -> server quote with frozen specification/manifest/price/policy/payment terms/expiry. Base requires payer. |
| POST `/quote-acceptance` | AcceptQuoteCommand: quote_id, customer_actor, idempotency_key -> OrderView. |

```json
{"prompt":"Find storage products under 2 kg and unit price no more than USD 40.","corpus_id":"storage-2026","idempotency_key":"customer-request-1"}
```

The automatic worker invokes compile, then the customer answers the resulting `question_id` with, for
example, `Use net unit weight`. After another compile, request a server quote and display its
complete terms, limitations and source manifest. Only the quote ID and explicit customer
acceptance create an order. The compiler cannot choose the price or remove mandatory checks.
There is no POST `/orders` and no invoice/fee-only acceptance route.

## Order commands

| Method/path | Body / effect |
| --- | --- |
| GET `/orders/{id}` | OrderView, ETag revision, no-store header. |
| POST `/orders/{id}/acceptance` | OrderCommand; requests capture only if all verification/authority gates pass; submission is not completion. |
| POST `/orders/{id}/disputes` | DisputeCommand adds targeted Complaint. |
| POST `/orders/{id}/answers` | AnswerCommand adds text for the pending question. |
| POST `/orders/{id}/amendments` | UploadCommand adds request ID, actor/reason/relationship and bounded base64 PDF. |
| POST `/orders/{id}/approvals` | ApprovalCommand: approval_id, actor, accept boolean. Customer approval only. |
| GET `/orders/{id}/artifacts/{artifact_id}` | Exact historical/current order artifact bytes after hash verification. |

Every OrderCommand contains:

```json
{
  "expected_revision": 7,
  "expected_binding": {
    "snapshot_id": "snapshot-from-current-view",
    "evidence_revision": 3,
    "delivery_version": 1
  },
  "idempotency_key": "customer-action-unique-key"
}
```

Always use actual IDs/revisions from GET. `delivery_version=0` means no delivery yet, not a fake
artifact. A dispute adds `complaint` with `text`, `product_id`, `field` (weight/unit_price/
completeness/provenance/pdf), `requirement_id`, current `artifact_id`, and `intent`
(dispute_fact or change_scope). An answer does not change the PDF version or reset the deadline.

Uploads use `evidence_request_id`, `actor`, `reason`, `relationship` (replacement_page or
supplement), and `pdf_base64`. Only current unexpired requests allow uploads. Maximum 2 MB,
1–8 PDF pages; no arbitrary path/URL/storage key is accepted. Assessment runs as durable work.
The original source remains available. Evidence-only repairs can require both customer and
provider approval under the accepted policy. Substantive amendments require a new offered
agreement and quote acceptance, not a generic approval click.

## Trusted work and human review

Provider routes require `X-Internal-Token` matching INTERNAL_API_TOKEN. Reviewer routes require
`X-Reviewer-Token` matching a different REVIEWER_API_TOKEN. Unconfigured credentials return 503;
wrong/missing credentials return 403. These are backend routes, never browser tokens. The
investigation model receives neither token nor payment/storage tools.

| Method/path | Meaning |
| --- | --- |
| POST `/internal/orders/{id}/work` | Claim/recover and execute one durable queued job. Empty body. Repeat calls never create work. |
| POST `/internal/orders/{id}/retry` | Current OrderCommand reserves an initial operational retry. |
| POST `/internal/orders/{id}/approvals` | Provider side of a required evidence-repair approval. Trusted actor recorded. |
| POST `/internal/orders/{id}/offers` | OfferCommand: current binding, work_description, Terms, optional amendment_id -> priced server Quote. |
| POST `/reviewer/orders/{id}/decisions` | ReviewCommand: current binding, permitted action, reason, supporting_evidence. Trusted reviewer actor is server-derived. |
| GET `/reviewer/legacy/orders/{id}` | Exact historical v0.2 JSON; read-only. |
| GET `/reviewer/legacy/orders/{id}/commands/{key}` | Exact historical idempotent response; read-only. |

An offer cannot supply arbitrary prices. Accepted additional work creates exactly one child
order/job and distinct authorization. A substantive-amendment child binds the proposed sources
and terms, preserves parent history and reserves parent void. Child funding/work waits for
confirmed parent return; failure/uncertainty leaves it blocked. No rejected
complaint fee exists.

Reviewer actions: `request_evidence`, `release_authorization`, `propose_exception`. Supporting
spans must resolve against order evidence. Requesting evidence cannot override attempt/deadline
limits. Negotiation preserves factual findings and still needs customer consent to a new offer.
No capture override or refund endpoint exists. Release is rejected after captured money.

## Polling, evidence and state

OrderView has `order`, `server_time`, `poll_after_ms=2000`, `available_actions`, `human_review`
and dynamic `payment_mode` plus payment account/operations. Separate order/delivery/authority/authorization/case/job states remain
visible. Red is operational_failure; waiting_evidence, pending_approval and human_review are
not operational success or failure. Use server time and persisted deadlines for countdowns.

Each Verification includes requirement-bound obligations and their assessments. Results are
PASS/FAIL/UNKNOWN/CONFLICT, with dependencies, material blockers, reason codes, exact citations
and deterministic/model provenance. Citation spans include artifact_id, SHA-256, one-based page,
start/end offsets in extracted page text, quote and normalized top-left rectangle. Fixture
highlights cover the visible text line. Actual crop/rotation examples still need UI testing.

Human review rows contain requirement/accepted wording, product/field, issue, source fact and
citation, delivered value/citation when present, result, amendment status, missing/contradictory
fact, remedy, financial effect and required authority. Decisions and old evidence are retained.

Stale revision/binding or changed payload under an existing idempotency key returns **409**.
Refetch before another action. An identical retry returns the saved command result, even after
restart; it may be older than the current view. Malformed contracts are 422, missing resources
404. Mutations, bookings and replay records commit atomically. Worker result commits also check
current evidence and the unexpired lease token. Uploaded data never authorizes tools.

## Timing and settlement

Review: 60 seconds per published delivery. Dispute: 60 seconds per newly opened case, with no
reset on answers/model calls; unresolved cases escalate at cutoff. Resolved disputes use the
original delivery-review cutoff. Repair: two attempts/order and 120 seconds per active episode,
capped by dispute and authorization deadlines. Clarification: 300 seconds/three questions/four
compiler calls. Authorization: 3,600 seconds, independent of all review windows.

Capture requires current mandatory checks (including actual PDF), no material uncertainty,
unresolved dispute or pending consent, current customer acceptance or expired undisputed review,
valid exact-amount authorization and no earlier capture. A passing report does not book early;
missing verification never books at timeout. Model amounts/payment flags are not API fields.

Mock receipts contain no live transaction ID or explorer link. Mock `ledger.kind=capture` is a
simulated booking. Base capture/void remain pending until authoritative confirmation; expired
capture is not returned funds. No observed live settlement is claimed in this handoff.

Evidence requests opened during a dispute also consume its two-question budget; the separate
repair-attempt allowance never grants extra dispute rounds.


## Funding boundary and payment views

| Method/path | Body / response |
| --- | --- |
| POST `/orders/{id}/funding-preparation` | Current `OrderCommand` → `FundingPreparation`. |
| POST `/orders/{id}/funding-authorizations` | `FundingAuthorization` → `OrderView`. |
| GET `/orders/{id}/payment` | `PaymentView`, public/redacted state and operation evidence. |
| POST `/internal/payments/work` | No body → `{processed: number, simulated: boolean}`; internal token only. |

`FundingPreparation` contains `funding_attempt_id`, `payment_id`, `order_id`, current `binding`,
frozen `terms`, exact EIP-712 `typed_data`, `prepared_at` and `expires_at`. The buyer signs that
typed data after checking connected payer/chain. Do not reconstruct or replace amount, recipient,
nonce or deadlines. A wallet rejection leaves funding unconfirmed.

`FundingAuthorization` adds `funding_attempt_id`, `payment_hash` and either a 65-byte hex
`signature` or explicit `simulate: true` (signature omitted/null) to current revision/binding/key.
Simulation is mock-only. The mock EIP-712 domain is `Mock USDC (no onchain authorization)`,
so a test signature cannot authorize on-chain USDC. `domain.chainId` is numeric 84532;
uint message values serialize as decimal strings. The server validates the signature against the frozen payer,
terms and time window. Treat signatures as capabilities: never put them into public fixtures,
analytics, reports, model inputs or ordinary logs. Responses never echo signing capabilities.

`PaymentView` has `payment` (`PaymentAccount`), `operations`, `explorer_links`, `simulated` and
`finality_note`. The account contains its immutable `PaymentTerms`, state, optional parent-payment
block, latest observation and error. Operations retain intent/action/binding, idempotency key,
fingerprint, state, nonce/hash, block evidence, observation, error and reconciliation status;
signed raw transactions remain private.

States: `blocked_parent`, `awaiting_signature`, `funding_pending`, `funded`, `capture_pending`,
`captured`, `void_pending`, `voided`, `uncertain`, `failed`, `expired_not_returned`, `reorg_hold`.
An operation failure does not establish whether funds remain held. Do not call uncertain or
expired funds returned. The account and operation state serve different purposes.

New payment terms bind mode, chain 84532, USDC address/6 decimals, exact atomic amount, complete
PaymentInfo (payer/provider/operator/token/fee receiver/deadlines/salt), deployment/source pin,
escrow/collector, real-payer hash, payer-agnostic authorization nonce and explicit pricing rule.
Blockchain quantities serialize as decimal strings; Python uses exact integers internally.
USD 15.00 at accepted demo 1:1 conversion is 15000000 atomic USDC. The isolated 0.10 test-USDC
profile is a separate accepted-payment fixture, not an undisclosed catalog discount.

Acceptance does not fund an order. Funding submission does not permit fulfillment. Confirmed
funding enables exactly one job; current acceptance/review gates reserve capture, and confirmed
capture closes payment. Void competes with capture. Late inputs cannot cancel a submitted
capture; keep settlement pending and route late complaints to human review. A substantive child
waits for confirmed parent return. No general customer capture/void endpoint exists.

Two canonical receipt confirmations are the configured demo threshold, not Ethereum/L1 finality.
Use actual observed transaction links only in Base mode. [Lucas handoff](handoffs/lucas.md) and
[12 runnable payment fixtures](../frontend/fixtures/README.md) cover displays/errors/signing.

Mock capture/release completes atomically. Base capture/void stays pending until confirmed
evidence and booking commit together; pending/uncertain/reorg fixtures remain explicitly simulated.
Automatic payment turns process at most one operation; the protected manual route processes at most 20.
Processed means attempted/audited, not successful settlement. Domain errors, including invalid recovered signatures (422), use `{detail: string}`; schema validation (422) uses
`{detail: "request validation failed", issues: [{loc, msg, type}]}` without echoing sensitive input.

Current OrderView/order/payment/ETag are read from one database snapshot. Full HTTP mutation
responses are saved atomically for exact replay. Unfunded authorization expiry yields failed
payment/human review with no funding actions; only funded expiry is expired_not_returned.
Reviewer release without held funds returns 409 rather than fabricating a void.
