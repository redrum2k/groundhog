# Architecture and contracts — v0.2

Product rules: [HACK.md](../HACK.md). HTTP contract: [API.md](API.md).
The user's annotated corrections supersede the earlier scaffold rules.

## Components

- `contracts/models.py`: immutable accepted snapshots, evidence/citation/provenance,
  all eight invoice criteria, verdicts, questions/answers and payment intents.
- `contracts/api.py`: versioned commands, persisted order record and polling view.
- `orders/service.py`: deterministic application transitions from trusted worker
  verdicts, customer commands and deadlines. Model verdicts can authorize early closure.
- `storage/orders.py`: SQLite order snapshots and exact idempotent command responses.
  Each mutation checks revision/binding, changes state and records simulated bookings
  under `BEGIN IMMEDIATE`. Competing commands cannot both consume the same revision.
- `runtime/policy.py`: amount/version/expiry/capture/extra-fee validation and remedy rules.
- `main.py`: FastAPI lifespan starts deadline recovery and a one-second sweep independent
  of browser polling. Deadlines also advance on reads/mutations; a stale command cannot
  undo a cutoff transition.
- `payments/`: mock authorization and receipts; no live adapter. The standalone mock
  adapter retains its own durable journal. The workflow stores mock bookings in the
  same order transaction, avoiding an external payment side effect during a DB lock.
- Jeff's investigator/provider integration and Lucas's frontend remain to be built.

## Evidence authority

A trusted investigator returns `compliant`, `provider_defect` or `insufficient_evidence`.
A compliant verdict requires passed, cited assessments of every `InvoiceCriterion`,
with no unresolved issues or questions. Final-delivery assessment must cite the actual
output PDF. A defect requires a cited failed criterion. Disputed results must classify
the claim as refuted, supported or unresolved consistently with the verdict.

The result is checked against the exact `InvestigationInput`; its citations must match
supplied IDs/versions/hashes. PDF citations need highlight rectangles. Runtime then
checks the current binding, fee, authorization expiry and operation history. It acts
on the evidence verdict, not an arbitrary `payment_authorized` field or agent amount.
These checks validate the evidence contract; Jeff's tools still have to substantiate
factual coverage, extraction, arithmetic and actual PDF content.

`Investigator.investigate(input)` remains Jeff's async implementation boundary. The
runtime provides complaints and prior customer answers as evidence. Customers cannot
submit verdicts: `/internal` producer routes require the backend worker token.

## PDF and structured data

Customer inspection uses source/delivery PDFs. Structured sidecars preserve internal
records and exact source ID/version/hash provenance. The invoice API requires both
PDF and structured references, while the general artifact models remain format-independent.
Jeff supplies coordinates; Lucas renders the PDF and overlays rectangles. Coordinates
are one-based pages and normalized top-left x0/y0/x1/y1 on the displayed page. Real
crop/rotation mapping and page bounds still need the shared-fixture check.

`GET /orders/{id}/evidence/{evidence_id}/content?version=N` resolves only registered
current-order evidence under ARTIFACT_ROOT, checks its SHA-256 and returns those bytes.
It rejects path escape and mismatched content. Customer claim/answer JSON is reconstructed
from persisted data and checked against its registered hash. No evaluation-key reader
or arbitrary repository browsing tool is supplied. Runtime workspaces must exclude
answer keys/mutation recipes; serving root must contain approved evidence only.

## State and time

Order, delivery, case and payment state are separate. `display_status` distinguishes
processing, correct, needs_review, operational_failure (red), and human_review.
`payment_state=mock` never becomes live captured. `payment_phase` records open, held,
booked or expired simulation state; ledger receipts remain explicitly mock.

An initial delivery or new dispute starts 600 seconds of review. Questions/answers do
not extend it. Complete evidence can close early; otherwise an undisputed delivered
job closes at cutoff. Unknown checks are not mislabeled passed. Unresolved disputes
at cutoff enter human review with payment held. Authorization expiry has its own clock.
A base booking that occurred before a later dispute is retained and never duplicated.

One free regeneration is reserved before dispatch. Supported defects authorize it;
repeated defect or engine failure during that regeneration escalates. A failed initial
engine attempt has no artifact version until a successful retry publishes output.
A replacement is allowed only after failure or a supported defect. Delivery/evidence/
proposal bindings change on replacement. Customer claims/answers change evidence and
proposal versions only. Old actions return 409; idempotent exact retries return the
stored command result. Refetch after a replay if a newer current view is needed.

The investigator asks one targeted question per round, at most two total. Answers are
stored as cited evidence; a final evaluation after the second answer must decide or
escalate. Exhausted budget, unanswered questions at deadline or an inconclusive result
without a useful question go to human feedback. No human-decision API is implemented yet.

## Charges and ledger

Order creation records mock base authorization immediately. Evidence closure, acceptance
or undisputed cutoff produces one mock base booking. A refuted complaint additionally
books the exact fee frozen in the accepted policy. If missing, `requires_quote=true`;
a trusted operator quotes a fee and the customer accepts that bound quote before any
extra booking. New quotes are limited to the original currency/precision and unexpired
authorization. There is at most one additional-processing booking per disputed review.
Neither a supported defect nor an unresolved complaint gets an extra charge.

Live authorization, outbox/dispatch, nonces and authoritative reconciliation are pending
the payment spike. The current workflow cannot move funds. Submitted/uncertain live
operations must be reconciled before retries and must not be shown as confirmed.

## Local demo boundary

Customer authentication, production tenancy, uploads, model/provider execution, PDF
rendering and deployment are absent. Bind the development server to localhost. Only
local frontend origins are enabled for CORS; the internal token is server-only. The
backend wheel contains app code, not evals/expected. Isolate the investigator's filesystem
when wiring it; package exclusion alone is not a sandbox.

FastAPI uses its documented [lifespan mechanism](https://fastapi.tiangolo.com/advanced/events/)
for the mock deadline worker. No additional queue or infrastructure is introduced.
