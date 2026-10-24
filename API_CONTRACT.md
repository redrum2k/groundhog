> This document describes the preserved `/api/jobflow` invoice workbench.
> Catalog/payment handoff status is in [docs/IMPLEMENTATION_STATUS.md](docs/IMPLEMENTATION_STATUS.md);
> catalog policy is HACK.md, and invoice policy is [archived separately](docs/jobflow/INVOICE_POLICY.md).

# Jobflow v1

Canonical job models: `backend/app/contracts/jobflow.py`; base financial contracts:
`backend/app/contracts/api.py` and `models.py`. Base policy is `invoice-review-v0.2`.
Existing `/orders`, `/internal/orders` and `/health` routes remain supported.
The integrator owns schema changes; backend and frontend consume the same generated schema.

## HTTP

All routes below use `/api/jobflow`. A bearer session maps to a server-side Actor.
Demo identities exist only with `JOBFLOW_DEMO=1`; deployed startup must fail closed
without configured authentication. No request-provided role grants authority.

| Method / route | Body | Result |
| --- | --- | --- |
| POST `/sessions` | `{actor_id}` (local demo only) | `{token,actor}` |
| GET `/actors` | — | `Actor[]` (local demo only) |
| GET `/orders` | — | `OrderView[]` authorized for actor |
| POST `/orders` | `OrderCreate` | `OrderView` |
| GET `/orders/{id}` | — | `OrderView` |
| POST `/orders/{id}/commands` | `Command` | `OrderView` |
| POST `/orders/{id}/documents` | `DocumentUpload` | `OrderView` |
| POST `/orders/{id}/investigations` | `InvestigationRequest` | HTTP 202 `{run_id}` |
| GET `/orders/{id}/events?after=0` | — | `Event[]` |
| GET `/orders/{id}/artifacts/{source_id}` | — | exact stored artifact bytes, Content-Type |

Mutations require an exact idempotency key and expected revision. Repeating an exact
request returns its prior result; changing its payload under that key fails. Effects,
events and idempotency receipts commit atomically. Model/provider I/O occurs outside
write transactions. Clients ignore snapshots older than their displayed revision.

## Ownership and limits

This branch's integration mission authorizes filling missing runtime and UI modules;
the original team ownership remains the handoff boundary. Main owns contracts,
dependency changes, investigation and integration; runtime worker owns API/runtime/
storage/provider and tests; UI worker owns frontend. No worker edits shared contracts.

One SQLite database. `orders` is the existing base-order/payment authority; `jf_orders`
stores its related unit-work aggregate, not a second base ledger. `base_order` is a
server projection of the existing order service view. Base and job changes use the
same transaction through optional `connection` parameters on OrderService.
SQLite also persists immutable evidence/artifacts,
attempt intents, sessions, events and balanced postings. Production has no coding CLI.
Anthropic mode requires explicit configuration and a nonzero authorized call limit.

## Commands and roles

- provider: `correct`, `amend_agreement` (provider signature), `fulfill_change`.
- customer: `accept_delivery`, `open_dispute`, `answer` to customer question,
  `amend_agreement` (customer signature), `accept_change`, `decline_change`,
  `accept_change_delivery`.
- customer: `accept_base`, `authorize_change`, `accept_processing_quote`.
- investigator: `verify_base`, using actual PDF/structured/source checks across all
  eight invoice criteria. The existing deterministic payment policy decides capture.
- controller: `quote_processing` with an explicit positive `amount_minor`; this
  proposes a fee, never charges it. The customer must accept the exact quote ID.
- investigator: investigate, request evidence; no approval or ledger authority.
- controller: `approve_action`, `decline_action`, `answer` to internal question,
  `handoff`. Cannot execute own approval.
- executor: `execute_action`, `receive_payment`, `reconcile`.

All actors may view authorized order state. Customer identities are scoped to their
customer ID. Uploads are PARTY_ASSERTION, never accepted authority. An amendment must
be signed independently by customer and provider; current effective scope is recomputed
at authorization and execution even when time changes without a revision change.

## Scenario and accounting

The demo opens a mock $100 base authorization for 100 $1 units, not a prepayment. Eighty
outputs are validated and separately recorded as accepted; twenty have actual
machine-verifiable missing-field failures. Original progress counts ORIGINAL jobs
only. Required scope is derived from accepted terms, not complaint text.

One bounded correction per failed unit creates new artifact bytes from the source,
then independent validation decides success. All affected IDs, attempt IDs, cost and
retry stage are durable. Unknown outcomes must reconcile the same intent. Permanent
failures are handed off. Existing valid outputs are not reprocessed. The automatic
operational authorization does not authorize additional customer charges.

Base booking follows HACK.md v0.2: ten-minute delivered/dispute review, early cited
compliant verdict or undisputed customer acceptance, and undisputed cutoff. Disputes,
operational failure, effective unfulfilled scope and expired authorization block capture.
Authorization expiry is independent. Unit acceptance never books the base payment.
The base ledger is projected into demonstration balances, never reposted in jf_postings.
The demo recognizes policy-booked base revenue. Correction expense/compute payable is
one cent per executed unit, within the $1 cap and one free regeneration per order.

The $8 four-field/100-document quote is separate: acceptance, separate authorize_change,
executor reservation, confirmed simulated receipt, new artifacts and customer acceptance
precede recognition. The worker rechecks payment authority at execution. UNKNOWN never
posts; reconciliation retains its original intent. Refuted complaints use the existing
agreed fee or a separately accepted and authorized processing quote. No live adapter is
introduced. Legacy initial_receipt input cannot create a base receipt or grant authority.

scope_obligations extends the existing order with signed effective-dated obligations.
The original deadline sweep and capture gate enforce them. Existing expected-binding
checks, exact idempotency receipts and authorization expiry checks remain in force.

## Investigator integration

`app.investigation.jobflow.investigate(order: OrderView, issue_id: str, *, mode: str)`
is async and returns `InvestigationOutcome`. It has no store/payment/credential tools.
`app.investigation.documents.extract_document(raw, filename, media_type)` returns
bounded extracted text and per-page location data. The runtime stores raw bytes and
immutable metadata. Only supplied case sources enter the model; exact cited text/hash
and version are checked before persistence. Runtime creates Action proposals itself
from validated findings; a model recommendation cannot establish authority.

`NO_REMEDY` is available when the disputed required field is already correct against
the exact input and delivery lineage. It closes only that issue after independent
approval/execution; it never authorizes payment, another generation, or a new charge.

## UI projection

An active dispute is orange, with a failure badge if processing also failed.
Undisputed verified processing failures are red. Validated, undisputed jobs are green;
pending/running/unknown states remain neutral blue. Finance is labeled separately.
Events drive the courier; replay/zoom/focus are read-only. Manual interaction pauses
opt-in auto-follow. Every open issue displays owner and next action. Compact finance
drawer shows actual postings and balances, not a duplicate full reconciliation table.

Authenticated GET `/orders/{id}/artifacts/{source_id}/pages/{page_number}` returns a
bounded PNG rendition with X-Source-SHA256. Exact source field citations carry normalized
rectangles. The browser verifies original bytes, renders the page and overlays its
cited region. Page inspection and courier replay are read-only.

## V5 broker and improvement interfaces

These are additive routes on the same FastAPI app/DB. They use the existing Bearer
session/registered actor boundary. The original unauthenticated invoice routes deny
broker records; they cannot bypass broker consent or tenant checks.

| Route | Contract / purpose |
| --- | --- |
| POST `/api/broker/drafts` | `DraftCreate`; original intent and pinned active template; no payment |
| GET `/api/broker/drafts/{id}` | `IntakeDraft`; actual questions, missing fields, capability, digest |
| POST `/api/broker/drafts/{id}/sources` | Provider-only immutable `SourceUpload` |
| POST `/api/broker/drafts/{id}/commands` | Customer answers/accepts/declines, provider offers, controller clarifies |
| GET `/api/broker/orders[/{id}]` | `BrokerRecord`; separate authoritative `base_order`, colour, owner, tasks |
| POST `/api/broker/orders/{id}/commands` | Produce, accept, dispute, investigate, answer, amend, resolve human task |
| POST `/api/broker/orders/{id}/sources` | New evidence version, not automatic replacement of accepted sources |
| GET `/api/broker/entities/{id}/events` | Existing `Event` schema, monotonic sequence, optional `after` |
| GET `/api/broker/entities/{id}/artifacts/{artifact_id}` | Exact bounded bytes and SHA256 ETag |
| POST `/api/improvements/commands` | `ImprovementCommand`: propose, probe, approve, activate, revoke |
| GET `/api/improvements?customer_id=...` | Scoped incidents/outcomes, candidates, probes, versions, experience |
| GET `/api/improvements/records/{id}` | Immutable full evidence, including probe traces |
| GET `/api/improvements/jobs/{id}` | Durable COMPLETE/BLOCKED/FAILED/UNKNOWN status; no automatic retry |
| GET `/api/improvements/entities/{id}/events` | Reviewer/job lifecycle events without mutation |

Every broker mutation carries an idempotency key and the broker/draft's
`expected_revision`, not its nested base revision. Customer acceptance also supplies
the displayed `digest` and an explicit `authorization_expires_at`; a provider must
already have accepted that exact complete specification/price/policy. Intake
`value` is a typed field answer, never an authenticated source fact.

The default profile is `aggregate_regional_market_intelligence`; source inputs use
the bounded `SourceSnapshot` JSON schema. Units, geography/revision, period, entity
unit, coverage denominator, missingness and date basis/age/as-of must be explicit.
Data citations contain source ID/version/hash, locator/value and actual artifact ID.
The server serializes the derived aggregate verification verdict; clients do not
decide financial eligibility from colour or model prose.

Human decisions require the exact current task/revision. RESUME rechecks evidence,
effective amendments, authority and bounds. A successful overdue resume without new
delivery requires explicit customer acceptance. An answer resumes the same issue
once without changing its PDF version or review deadline.

Improvement generation defaults to the configured application model; unavailable
access returns a persisted BLOCKED job. Explicit simulated infrastructure mode is
available only in demo mode. Approval and activation are distinct controller
commands; candidate/baseline/probe/backend hashes are rechecked. Revocation moves
only the future-template pointer. No command can submit a raw arbitrary template,
generated code, changed accepted amount or new payment permission.

Generated DTOs: `frontend/lib/{jobflow,broker,improvement}.generated.ts`.
Client helpers: `frontend/lib/broker-api.ts`. Stable prepared mutations are explicit;
polling/replay/focus never dispatch a POST. Lucas can consume these without a new UI
stack. `POLICY_DELTA.md` defines the versioned financial semantics.
