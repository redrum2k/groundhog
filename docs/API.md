# Local polling API — v0.2

Run the backend as in README.md. `/docs` and `/openapi.json` expose the exact Pydantic
schemas. The API is a **local mock demo**, with no customer authentication or real money.
Use localhost. Customer routes and trusted worker routes are deliberately separate.

## Customer routes

| Method | Path | Purpose |
| --- | --- | --- |
| POST | `/orders` | Freeze an accepted invoice snapshot and immediately open mock base authorization. |
| GET | `/orders/{id}` | Poll state, evidence, deadline, actions and mock ledger. |
| POST | `/orders/{id}/acceptance` | Accept the current undisputed delivery. |
| POST | `/orders/{id}/disputes` | Submit complaint/refund request and start a ten-minute evidence review. |
| POST | `/orders/{id}/answers` | Answer the current agent question; update evidence/proposal binding. |
| POST | `/orders/{id}/quote-acceptance` | Accept the current additional-processing quote. |
| GET | `/orders/{id}/evidence/{evidence_id}/content?version=N` | Retrieve exact registered evidence bytes with hash validation. |

`CreateOrder` contains `snapshot`, `authorization_expires_at`, and `idempotency_key`.
Invoice snapshots require source PDF and structured-data references. `snapshot.price`
is the base amount; `snapshot.policy.additional_processing_price` is an optional agreed
extra fee in the same currency/precision. No fee is inferred when omitted. `Money`
uses a positive strict integer `amount_minor` plus `currency` and `decimals`.

Other mutations require all three concurrency fields:

```json
{
  "expected_revision": 2,
  "expected_binding": {
    "order_id": "order-1",
    "snapshot_id": "snapshot-1",
    "delivery_version": 1,
    "evidence_version": 1,
    "proposal_version": 1
  },
  "idempotency_key": "customer-dispute-1",
  "complaint": "Invoice INV-1 is missing from the delivered register.",
  "refund_requested": true
}
```

This is an example dispute body; obtain actual revisions/bindings from GET. Before
initial delivery `expected_binding` is explicitly null. `answers` adds `question_id`
and `text`; `quote-acceptance` adds `quote_id`; `acceptance` adds no extra fields.
Unknown fields are rejected. There is one dispute case per delivered version.

A refund request starts investigation; no refund is executed by this API. Supported
claims get one free regeneration; a refuted claim gets the accepted processing fee,
or a separately accepted quote if no fee exists. An early booked base is never booked
a second time when a later in-window dispute is resolved.

## Polling and conflict handling

The GET response is `OrderView`:

- `order`: accepted snapshot, monotonic revision, separate lifecycle states, current
  binding, delivery history, evidence, review deadline, questions/answers, latest
  verdict, quote state and mock ledger.
- `server_time`: timezone-aware backend time; use with `order.review_deadline` for countdowns.
- `poll_after_ms`: 2000. Poll every two seconds; stop on component unmount.
- `available_actions`: customer actions currently permitted by the application.
- `display_status`: processing, correct, needs_review, operational_failure or human_review.

Responses include `Cache-Control: no-store` and an ETag containing the order revision.
Conditional GET/304 is not implemented. The revision and full binding in each mutation
are the concurrency contract. Red is only `operational_failure`; an unchecked PDF can
be booked at an undisputed cutoff while still showing `needs_review`.

A stale revision/binding or a conflicting transition returns **409** with `detail`.
Refetch the view and ask the customer to act on the current version; do not silently
resubmit stale approval. Retry a lost response with the **identical payload and key**:
it replays the persisted command result, even after restart. Reusing a key with a
changed payload returns 409. A replay may contain an older view; GET returns current state.
Malformed contracts/evidence return 422, unknown resources 404. Mutation checks,
transitions and simulated bookings are atomic in SQLite.

## Trusted producer / investigator routes

These routes require the backend-only `X-Internal-Token` matching `INTERNAL_API_TOKEN`.
Missing configuration returns 503; a missing/wrong token returns 403. Never expose the
token in a frontend bundle or NEXT_PUBLIC variable. The frontend must not submit agent verdicts.

| Method | Path | Additional body / result |
| --- | --- | --- |
| POST | `/internal/orders/{id}/deliveries` | `artifacts`, `structured_data`; backend allocates version and delivered_at. |
| POST | `/internal/orders/{id}/failures` | `error_code`, `message`; marks an active provider job operationally failed. |
| GET | `/internal/orders/{id}/investigation-input` | Current InvestigationInput, including complaint, answers and budget. |
| POST | `/internal/orders/{id}/investigations` | `result`: current InvestigationResult. |
| POST | `/internal/orders/{id}/quotes` | `amount`, `expires_at`; quote allowed only after a refuted unpriced complaint. |

All POST routes above also require the mutation concurrency fields. Publication
requires a PDF and retained structured-data references. It is allowed for initial
output, operational retry, or the single reserved free regeneration; arbitrary PDF
replacement is rejected. Failures without output do not create artifact versions.

The investigator returns all eight cited passed checks for `compliant`, a cited failed
check for `provider_defect`, or `insufficient_evidence`. Claim assessment must match the
disputed verdict. Actual output PDF evidence is required for the final-delivery check.
A complete compliant verdict can close and book immediately without waiting for cutoff.

For missing disputed evidence, include one question with `question_id`, `prompt`, and
`missing_evidence`. After its answer, GET a new InvestigationInput; the answer has a
versioned evidence reference. At most two questions total are permitted. After the
second answer, a conclusive verdict resolves the case; an inconclusive verdict without
another question escalates. A third question is invalid. An unresolved deadline also
escalates and holds payment. Answers do not extend the ten-minute review deadline.

## Timing, ledger and artifact boundaries

A lifespan worker sweeps persisted deadlines every second and at restart. Correctness
does not depend on browser polling. Delivery/dispute reviews last 600 seconds. At an
undisputed cutoff the base is booked; unresolved disputes/human review hold it. Separate
authorization expiry prevents capture and requires human intervention.

`payment_state` and every receipt remain `mock`; `payment_phase=booked` means a simulated
ledger entry exists, not confirmed live settlement. The extra fee is charged once per
refuted case. Quotes require customer acceptance and must remain within authorization expiry.

Artifact files must already exist under ARTIFACT_ROOT with matching frozen SHA-256.
Uploads and PDF generation are not implemented. Only current registered evidence is
served; path escape and hash mismatch are rejected. Customer answer/claim JSON is
served from persisted data. Runtime never receives evals/expected or mutation labels.

The workflow tests in `backend/tests/api/test_orders.py` are executable examples of
creation, publication, verdicts, disputes, answers, quotes, retries and cutoff recovery.
They use synthetic references/fake verdicts; they do not claim actual PDF verification.
