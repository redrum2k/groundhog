# CalHacks: custom data deliverables, from request to cash

Catalog policy v0.3 plus Base escrow payment amendment (`catalog-payments-v1`), October 23, 2026. This supersedes the invoice-register product, ten-minute
reviews, immediate verdict capture, rejected-claim fees and previous ownership.
Deadline: **Sunday, October 25, 2026, 9 a.m. America/Los_Angeles**.
Tracks: **Hyphenate, Coinbase, Microsoft**. Sponsor eligibility and deliverables remain
unverified; Rehan must obtain the actual rules. No sponsor requirements are inferred.

## Preserved invoice compatibility

The existing invoice workbench remains available at `/api/jobflow` under its
[isolated invoice policy](docs/jobflow/INVOICE_POLICY.md). It is a separate mock demo,
not a catalog payment adapter. Its prior UI, tests and accepted policy are preserved
by the merge; catalog orders continue to follow the rules below. Historical invoice
rows outside active jobflow cases remain read-only.

## Product and bounded demo

Request -> agent draft -> clarification -> accepted specification/quote -> buyer signature
-> submitted funding -> confirmed funding -> fulfillment/verification -> delivery/review -> evidence repair/correction/dispute/human
review -> gated settlement/reconciliation. Investigation can start before delivery.

One job: select all qualifying storage products from a provider-owned supplier-catalog
corpus and deliver a cited PDF shortlist plus internal structured representation.
Example: net unit weight below 2 kg and USD unit price at most 40. Four synthetic supplier
PDFs contain 12 products each. The customer selects a corpus and supplies a prompt.
Unrestricted initial uploads, web acquisition and a general marketplace are out of scope.
Evidence-request-specific PDF uploads are implemented.

## Agreement

Persist the draft separately from orders. Clarify material ambiguities, including net
versus shipping weight and inclusive versus exclusive thresholds. Typed terms specify
corpus/category, weight concept/unit/operator/threshold, price basis/currency/operator/
threshold, required fields, completeness, unknown handling and source policy. Server-owned
stable requirement IDs and mandatory global checks accompany the readable summary.
Inspect sources and disclose limitations before quoting. The compiler cannot set prices.

Server pricing v1: initial work USD 15.00; separately offered additional work or substantive
amendment USD 5.00. These are demo rules, not externally researched market prices.
A quote freezes specification revision, manifest, amount, policy, work and expiry. New quotes
also bind payment mode, token/chain, parties, full PaymentInfo, salt/hashes, absolute funding/
authorization/refund deadlines and explicit conversion. Demo conversion v1 is 1 USD:1 USDC:
USD 15.00 settles 15000000 atomic USDC; USD 5.00 settles 5000000. Blockchain quantities use
exact integers internally and decimal strings in JSON. The isolated 0.10 test-USDC laboratory
uses separate synthetic accepted terms; it is not underpayment of a catalog order.
Explicit acceptance atomically records a schema-4 immutable snapshot and pending funding.
It does not supply the buyer signature. A reserved job remains blocked until confirmed funding
(or the explicitly simulated mock boundary); exactly one job becomes runnable. Initial quote lifetime is at most 180 seconds and within the draft deadline. A provider
offer lasts at most 120 seconds within the applicable authority/repair deadline.

Registered sources have IDs, versions, hashes, edition/effective date and approved storage
references. Frozen orders ignore later registry updates. Sidecars derive from PDF parsing.

## Verification and the grey zone

| Requirement | Mandatory outcome |
| --- | --- |
| R-CATEGORY | Products meet the agreed category. |
| R-WEIGHT | Correct weight concept and exact unit/operator threshold. |
| R-PRICE | Correct unit-price basis, USD currency and exact operator threshold. |
| R-FIELDS | Unique identity and required product/name/supplier/weight/price/citation fields. |
| R-COMPLETENESS | Every declared record is included, justifiably excluded or explicitly unresolved. |
| R-PROVENANCE | Frozen source identity/authority/edition, exact artifact hashes and resolving spans. |
| R-PDF | Actual delivered PDF records, amounts, exclusions and citations match source-derived results. |

Each obligation records its requirement, subject/field, dependencies and decision effect.
Each assessment records PASS/FAIL/UNKNOWN/CONFLICT, exact citations, missing/conflicting
facts, reason code, requested evidence and tool/model/version provenance. Optional model
scores are separate from factual outcomes. A failure to establish authenticity is UNKNOWN,
not proof of forgery. Initial blocker codes: SOURCE_AUTHORITY_UNVERIFIED,
EFFECTIVE_DATE_CONFLICT and REQUIRED_VALUE_UNREADABLE.

The runtime follows dependencies from mandatory decision checks. A product conclusively
excluded on weight need not have a readable price. Decorative uncertainty does not block
settlement. Authority/date -> applicable facts -> eligibility -> completeness makes relevant
uncertainty material. A model may be confident that evidence is insufficient; confidence
cannot supply the missing fact, permission or payment authority.

PASS routes to lifecycle review gates, established output defects to correction, material
missing evidence to a specific bounded request, exhausted uncertainty to human review, and
established facts requiring changed commercial terms to explicit consent.

## Repair and amendment policy

The default accepts a registered supplier publication or a registered authorized-representative
confirmation. A supplier logo or model agreement is insufficient. All authority attestations
in fixtures are explicitly synthetic provider registry records.

Uploads preserve actor, target source/version, answered request, reason, hash/media/storage,
relationship, classification/assessment and application/approval history. Never overwrite the
original. Compare identity, edition, records and all originally readable values.

- Evidence-only repair restores the same information. Apply under preauthorized source
  policy, or obtain customer and provider approval if the accepted policy requires both.
  Increment evidence revision; invalidate findings, approvals and stale jobs; recheck all
  obligations including completeness. Do not create a new delivery merely for an answer.
- Substantive changes require a provider-issued new agreement and customer acceptance.
  The implementation uses a linked child order with the proposed manifest/specification
  and separate authorization. Reserve a full void of the uncaptured parent, retain its
  immutable snapshot/history, and wait for confirmed return before child funding/work. A
  failed or uncertain return leaves the parent pending and child blocked. No silent expansion.
- Unresolved authority, effective date or facts lead to a useful follow-up or human review.
  Source defects do not themselves prove provider fault or spend the free correction.

Rejected consent preserves the original contract and moves to human review. The reviewer can
request evidence within remaining limits, record a proposed negotiated exception for a new
offer, or release uncaptured authorization. Exceptions do not turn an original false claim true.

## Time, correction and money

Delivery review: 60 seconds/version. New dispute: 60 seconds from opening, without changing
the original delivery deadline. An unresolved dispute blocks payment at both deadlines and
escalates at its own cutoff. A resolved dispute returns to the original delivery review gate.
At most two questions, one per round. Answers, uploads and model calls never extend clocks.

Precontract clarification: 300 seconds, three rounds, four compiler calls. Evidence repair:
two requests total/order, 120 seconds per active repair episode, capped by any open dispute
and authorization deadline. Worker lease: 45 seconds, at most three attempts/job. Model
requests: 20-second SDK timeout, no SDK retries, 4,096 output-token limit, 50,000-character
input bound. Authorization: 3,600 seconds, independent of reviews.

Capture requires current mandatory verification, no material blocker/unresolved dispute or
pending consent, current customer acceptance or expired undisputed delivery review, exact
accepted amount under valid confirmed funding and no prior capture. Recheck eligibility before reserving submission;
only one capture/void can be active. A submitted capture is past the cancellation boundary:
late complaints enter human review while settlement stays pending. Missing verification never
becomes approval through timeout. A passing verdict alone never bypasses review.

One durable free-correction job per established provider defect. The correction publishes a
new version only after rechecking. Repeated defect or operational correction failure escalates.
Initial operational failures can be retried with version binding and a durable job. Red means
operational failure; a document needing evidence review has a separate state.

Unsupported complaints are free. Paid regeneration requires an explicit work/price/terms
offer; acceptance reserves a real child job and distinct authorization. Complaints are not
purchase consent. A release is a full on-chain void of uncaptured held funds (simulated in mock mode), not a
refund. Capture expiry permits payer reclaim; it does not prove money was returned. Refund
execution, partial capture and fees are outside this MVP. Mock receipts never claim confirmed
settlement, live transaction IDs or explorer links.

## Escrow and operator trust

Use deployed Base Commerce Payments v1.1 on Base Sepolia (84532), test USDC (6 decimals),
and a dedicated platform operator EOA. Main payment is customer → provider. The contract holds
funds; the backend enforces accepted settlement rules. Buyers and providers trust the operator
to apply those rules. Neither an AI finding nor the escrow contract verifies document quality.
No x402, separate verification fee, Coinbase Business Checkouts, hosted facilitator, custom
Solidity/operator contract, mainnet, arbitrary asset or account-abstraction work is in scope.

Buyer signs ERC-3009 ReceiveWithAuthorization for the collector; operator pays gas and submits
funding. Preparation, authorization, submission, held funds, capture/void pending, confirmed
outcome, uncertainty, failure and expired-but-not-returned are separate states. Full capture
pays exactly the accepted amount with zero fee; full void returns held funds. The contract's
refundableAmount describes captured accounting, not additional held cash.

The additive operation journal preserves canonical requests, idempotency, reserved nonces,
signed transactions and reconciliation evidence. A lost response never authorizes a fresh
payment/salt/nonce. Two canonical receipt confirmations are the configurable demo threshold,
not Ethereum/L1 finality. Reorgs require recovery; do not rerun fulfillment or value transfers.

The first separately authorized live milestone is two independent payments of 100000 atomic
test USDC: one fund → restart → full capture, one fund → full void. There are **no observed
real testnet receipts yet**. Offline fake-chain success must never be presented as chain proof.
Exact setup and commands: [payment runbook](docs/PAYMENT_RUNBOOK.md).

## Implementation boundaries

Python/uv/FastAPI/Pydantic/SQLite remain. ReportLab/pdfplumber implement actual fixture PDFs
and extraction. A Claude compiler/semantic assessor is injectable, explicitly opt-in, with
conservative offline substitutes. No paid calls ran. Jev is not required or implemented;
any future adapter must be evaluated against independent labels before adoption.

The PDF parser supports the documented synthetic catalog layout, not arbitrary supplier
scans/OCR. Source attestation is a trusted local registry, not a live supplier integration.
Customer authentication, production tenancy, frontend, deployment, refunds and production
settlement remain future work. No testnet broadcast, paid model call or deployment is authorized
by this amendment. Historical v0.2 data stays read-only; v0.3 mock snapshots/idempotent responses
remain readable and never become live obligations. No historical payment terms are rewritten. See docs/IMPLEMENTATION_STATUS.md.

Evidence requests opened during a dispute also consume its two-question budget; the separate
repair-attempt allowance never grants extra dispute rounds.
