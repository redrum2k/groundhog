# Architecture — catalog v0.3 / payment contracts v1

> Aggregate brokerage update (October 24): new default intake uses
> `aggregate-brokerage-v1`, funded CSV/JSON deliveries and the persisted `/runs` API.
> See [workstream 06](workstreams/06-data-broker.md) for current contracts, commands,
> compatibility boundaries and validation limitations. The catalog-specific details
> below remain historical compatibility guidance and do not set new dataset policy.


Python, uv, FastAPI, Pydantic and SQLite remain. The refactor adds a catalog domain alongside
read-only historical DTOs rather than changing the framework or rewriting old financial data.

## Execution path

`contracts/catalog.py` holds drafts, terms/requirements, quotes/snapshots, typed lifecycle
contexts, obligations/assessments, amendments, consent, jobs and financial/reviewer records.
`contracts/models.py` and `contracts/api.py` retain v0.2 deserialization and shared primitives.
The old invoice executor and HTTP mutations are retired. Current mutations use CatalogService
in `orders/catalog.py`; `orders/service.py` now contains shared errors and clock only.

`storage/catalog.py` adds schema migration 3, catalog_records, catalog_commands and
catalog_sources using the existing SQLite transaction foundation. Each transition uses
BEGIN IMMEDIATE; current binding/revision checks, state changes, mock ledger entries and exact
idempotent responses commit together. Model/PDF production work runs outside DB transactions.

Acceptance constructs a schema-4 immutable snapshot with `catalog-payments-v1` terms and
pending funding. Buyer signature or explicit mock simulation is a separate command; confirmed
funding enables exactly one job. A lease claim checks successful authorization before dispatch.
Jobs persist queued/running/done/failed/stale states, attempts, lease IDs/deadlines and errors.
Expired leases can be reclaimed after restart, at most three attempts. A former lease holder
cannot publish after another worker claims it, evidence changes, or deadlines expire.

CatalogWorker.run_once() automatically selects one draft/job attempt. Five independent thread
lanes handle catalog/invoice deadlines, catalog work, payments and invoice work. Sweeps run each
second; dispatch/payment turns wait 0.25 seconds after each call. Paid inference requires explicit
model opt-in. Trusted manual routes and the offline harness remain available. Graceful shutdown
drains calls before releasing the database worker lock; hard restart uses durable leases.
Compiler calls reserve a persisted revision/budget before calling the injectable compiler;
late results are rejected. A process interruption can leave a compiling draft: replay returns
the durable reservation, and a worker refetches/retries with a new key within the existing
call budget/deadline. No indefinite retry or deadline reset is permitted.

## Evidence and intelligence

ArtifactStore persists immutable content-addressed objects under an approved root. Every read
checks SHA-256 and root containment. Cached PDF layout is keyed by the actual immutable bytes,
not by unchecked paths. Sources are versioned provider registry entries with recorded authority
basis. Customer uploads are bounded PDFs (2 MB, 1–8 pages, bounded extractable characters),
accepted only against a current evidence request. No original source is overwritten.

The fixture parser extracts product identity, net/shipping weights, USD unit price, record index,
edition and effective date from actual PDF text. Decimal comparisons and unit conversion are
ordinary code. Source sidecars are generated from those extracted records. Output generation
and verification are separate passes; verification reconstructs expected records from sources
and parses the actual PDF. This supports the bounded synthetic layout, not arbitrary OCR.

Requirement IDs and obligations come from an allowlisted registry with mandatory global checks.
No model supplies executable verification code. Every assessment is PASS/FAIL/UNKNOWN/CONFLICT
with exact artifact/hash/page/text-span/normalized-line-region evidence and provenance. Materiality
traverses explicit dependencies from mandatory decision obligations. Excluded products need only
the decisive exclusion fact; irrelevant decorative uncertainty is not a blocker.

The compiler, CatalogInvestigator and SemanticAssessor interfaces are injectable. Claude uses
Messages structured output and supplies semantic input; offline implementations are explicitly
limited substitutes. Refusal, malformed output, provider failure and stale results fail closed.
Source authority comes from the registry, never a model score or second-model agreement.
Unstructured semantic findings that conflict with deterministic checks go to human review.

## Amendments and consent

A request-bound upload creates an immutable amendment and new evidence revision. Identity,
edition, record set and readable original fields are compared; the uploaded hash must match
an approved supplier publication/representative record to establish authority. A logo does not.

Evidence-only repair applies under the accepted source policy or after both required approvals.
Application invalidates findings, pending approvals and stale jobs, then reruns all checks.
A source problem does not spend the free-correction allowance. Substantive amendment creates
a proposed provider quote with a new manifest/specification; customer acceptance creates a
linked child order with independent authorization. Parent release gates the child; the current
mock release completes atomically, while integrated Base execution waits for confirmed void. Historical agreement, artifacts and ledger remain intact. Rejected/missing consent leads
to human review of the original agreement. No changed terms become effective by timeout.

Precontract, fulfillment, repair and dispute have separate typed contexts. Pre-delivery evidence
work never requires a fabricated delivery. Answers revise evidence, not PDFs. Published versions
change only through initial fulfillment, operational retry or an authorized free correction.

## Money and authority

Current capture policy is `runtime/catalog_policy.py`. It requires current mandatory verification
including actual PDF fidelity, no material blocker/unresolved dispute/pending consent, current
customer acceptance or undisputed delivery-review expiry, exact accepted amount, valid authorization
and no prior capture. A report alone cannot book early; missing reports cannot book at timeout.

One free correction is durably reserved for established provider defects. Repeated defects or
operational failure during correction escalate. Unsupported complaints have no charge. Additional
work needs an explicit offer whose acceptance creates a child job and authorization.

Reviewer credentials are distinct from provider/worker credentials. Decisions record the trusted
actor, reason, resolving citations, current binding and idempotency. Allowed actions: request evidence
within remaining limits, propose a negotiated exception, or release uncaptured authorization.
Reviewers cannot override expiry, mark original facts true by negotiation or execute unimplemented
refunds. Customer actor strings are local demo audit labels, not authenticated identities.

Current `contracts/payments.py` defines immutable PaymentInfo/terms, funding preparation and
authorization, payment accounts, operations and redacted views independently of historical v0.2
SettlementIntent. The additive payment journal and mock execution boundary preserve idempotency,
current binding and ledger consistency. Mock capture/release remains atomic. Funding preparation
uses a non-chain domain in mock mode; Base obtains a verified USDC domain outside database locks.
Explicit simulation never invents a buyer token signature and is rejected for Base.

The selected live integration is Base Commerce Payments v1.1 on Base Sepolia with a dedicated
platform operator EOA. The contract holds funds; buyers/providers trust the operator to apply
accepted settlement policy. AI findings do not confer wallet authority. The integrated Base transport is
validated with injected RPC only; there are no observed testnet receipts. Lifespan-only adapter
selection defaults to mock and fails closed on missing signer or preflight failure. Import/schema
export has no RPC/configuration side effects. The durable executor persists signed bytes/hash before broadcast, serializes nonces,
reconciles receipts/events/state and canonicality, and never retries uncertainty with a new
payment/salt/nonce. Confirmation and catalog booking share one transaction. Bounded disabled
reservations yield to other pending receipts; uncertainty/reorgs hold money and evidence.
Two canonical receipt confirmations are not Ethereum/L1 finality.

The frontend mock API supplies every pending/terminal/uncertain/expired/reorg account state
without pretending they are observed chain transitions. Mock receipts have no live transaction
ID or explorer link. This uses Base Commerce Payments, not x402 or a separate verification fee.
See PAYMENT_SPIKE.md and handoffs/lucas.md.

## Compatibility and deployment boundary

Existing orders/order_commands rows are neither deleted nor transformed. Trusted historical GETs
return exact stored JSON, including old policies and financial entries. Deadline recovery reads current catalog tables; schema-3 mock records remain readable
and never become live obligations. Legacy DTO tests preserve decoding; old behavioral tests were replaced with
catalog safety and journey tests. Resuming a historical order requires explicit human handling; no
implicit commercial-policy migration exists.

Runtime app code does not import corpus generators or evals/expected. Only the offline harness
creates synthetic inputs. Evaluation answers are not exposed through tools/prompts. Packaging
exclusion is not an OS sandbox: production filesystem/tenant isolation remains required. No customer
authentication, frontend, supplier network integration, deployment or live settlement is claimed.

## Integrated invoice compatibility surface

The existing invoice workbench is mounted as a separate FastAPI application at
`/api/jobflow`, with its own OpenAPI schema. This prevents duplicate model names
from changing the frozen catalog schema while retaining the workbench's paths.
Its `Jobflow` uses `orders/invoice_compat.py` and `runtime/invoice_policy.py`;
catalog execution continues to use `CatalogService` and `catalog_policy.py`.
Both retain their original tables in the shared SQLite file. Invoice deadline
sweeps join `jf_orders` and never advance unrelated historical invoice records.
A single advisory worker lock covers startup recovery; separate background tasks
keep catalog deadlines/payment processing independent of invoice model/document work.
The invoice UI remains implemented; catalog UI integration remains planned.
