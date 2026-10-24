# Jobflow v1

Canonical models: `backend/app/contracts/jobflow.py`. Existing contracts and `/health`
remain unchanged. This additive seller-prepayment flow uses `saas-unit-acceptance-v1`.
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

No second authoritative store. SQLite persists orders, immutable evidence/artifacts,
attempt intents, sessions, events and balanced postings. Production has no coding CLI.
Anthropic mode requires explicit configuration and a nonzero authorized call limit.

## Commands and roles

- provider: `correct`, `amend_agreement` (provider signature), `fulfill_change`.
- customer: `accept_delivery`, `open_dispute`, `answer` to customer question,
  `amend_agreement` (customer signature), `accept_change`, `decline_change`,
  `accept_change_delivery`.
- investigator: investigate, request evidence; no approval or ledger authority.
- controller: `approve_action`, `decline_action`, `answer` to internal question,
  `handoff`. Cannot execute own approval.
- executor: `execute_action`, `receive_payment`, `reconcile`.

All actors may view authorized order state. Customer identities are scoped to their
customer ID. Uploads are PARTY_ASSERTION, never accepted authority. An amendment must
be signed independently by customer and provider; current effective scope is recomputed
at authorization and execution even when time changes without a revision change.

## Scenario and accounting

The demo company receives a simulated $100 prepayment for 100 $1 units. Eighty
outputs are validated and separately recorded as accepted; twenty have actual
machine-verifiable missing-field failures. Original progress counts ORIGINAL jobs
only. Required scope is derived from accepted terms, not complaint text.

One bounded correction per failed unit creates new artifact bytes from the source,
then independent validation decides success. All affected IDs, attempt IDs, cost and
retry stage are durable. Unknown outcomes must reconcile the same intent. Permanent
failures are handed off. Existing valid outputs are not reprocessed. The automatic
operational authorization does not authorize additional customer charges.

Prepayment: debit cash, credit contract liability. Accepted original units: debit
contract liability, credit revenue. Correction: debit correction expense, credit
compute payable, one cent per executed corrected unit. The $8 four-field/100-document
quote is separate: acceptance is not payment, payment is not recognition; new artifacts
and customer acceptance precede recognition. No posting on UNKNOWN. Each business event
has one unique posting. No escrow semantics or real financial provider.

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
