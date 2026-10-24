> Preserved policy for the existing /api/jobflow invoice demo only.
> Catalog orders follow root HACK.md and catalog-payments-v1.

# Cal Hacks: invoice register and evidence-based settlement

Policy v0.2 records the user's annotated corrections and subsequent answers. It
supersedes the original 60-second / no-additional-charge scaffold. Deadline and
sponsor requirements still need team input; no live payment spike has run.

## Product

Process source invoice PDFs into an invoice register and exceptions section delivered
as a PDF. Source and delivery inspection uses linked evidence highlights. Retain
structured records internally for reproducible checks and PDF-region mappings.

## Explicit acceptance criteria

| Requirement | Concrete check |
| --- | --- |
| Complete coverage | Every unique invoice appears in the register or exceptions section. |
| No double counting | Each invoice ID contributes to totals at most once. |
| Accurate extraction | Invoice ID, vendor, date, currency and total match the cited source. |
| Correct arithmetic | Vendor subtotals and grand total equal the included invoice amounts. |
| Traceable evidence | Each row points to the correct document and page; displayed highlights match the cited text. |
| Honest uncertainty | Conflicting versions are flagged, with neither silently treated as authoritative. |
| Correct final delivery | The actual PDF contains the required rows and figures, not just the intermediate JSON. |
| Defined scope | No currency conversion, payment-status determination or unsupported category inference. |

The first fixture uses one currency. If later fixtures mix currencies, keep separate
currency totals; never add them into a converted or mixed-currency total.

## Accepted payment/review policy

- Freeze the accepted brief, input versions, base price, policy and optional additional
  processing fee. Open base authorization as soon as the accepted order is created.
- Each delivered version and each newly opened dispute gets a ten-minute review.
  Answers remain within that review deadline; they do not reset the clock.
- A compliant agent verdict backed by citations for all eight criteria can close the
  work and book the base payment immediately. Undisputed customer acceptance also closes it.
- At cutoff an undisputed delivered job closes and books the base payment, even if a
  complete agent verdict has not arrived. Unknown evidence is not labeled verified.
- The user explicitly confirmed: unresolved disputes hold payment and escalate to
  human review at cutoff. Engine failure, known defects and human review do not auto-capture.
- Supported customer claim/provider defect: reserve one free regeneration. If the
  free regeneration fails operationally or still has a supported defect, escalate.
- Refuted customer claim: display the cited evidence and charge additional processing.
  The user explicitly confirmed: use the fee agreed in the accepted order; if none
  exists, obtain a quote and customer acceptance before charging it. Do not invent a fee.
- Agent questions target missing evidence. Use at most two questions total, one per
  round. After two answered rounds, decide or escalate; missing answers at cutoff also
  escalate. This follows the user's later two-round clarification over the earlier one-round wording.
- A refund request opens evidence gathering; it is not an automatic refund. The supported
  remedy is free regeneration. Human refund/release execution remains to be specified.
- Authorization expiry is independent. Expired authority requires human intervention.
- A dispute raised during the remaining review window after an early base booking can
  still be investigated. Already booked base funds are not automatically reversed or
  charged twice; any free regeneration remains free.

## Version and display semantics

Keep order, delivery, case and payment states separate. Red means operational failure
(e.g. engine failed). A delivered PDF lacking complete evidence is `needs_review`, not
an operational failure. A complete compliant verdict is `correct`; ambiguity requiring
human feedback has its own status. Timeout booking does not falsely label an unchecked
PDF correct.

A replacement delivery is published after an operational retry or supported defect /
rightful dispute. Failures without a file do not fabricate a PDF version. Answers and
new customer claims increment evidence/proposal versions and invalidate old verdicts;
they do not increment the PDF delivery version. Clients must use current revisions/bindings.

## Team handoff

Jeff owns corpus generation, extraction and PDF coordinates. Nikita owns provider jobs,
persistence and settlement execution. Lucas displays PDFs/highlights and visually
classifies generated cases as correct, operationally failed, disputed or ambiguous.
Rehan maintains independent answer keys and acceptance evaluation. Review labels and
mutation recipes never enter the investigator's evidence.

## Stack and current scope

Python, uv, FastAPI, Pydantic, SQLite, LangGraph and Anthropic SDK; Next.js/TypeScript/
shadcn UI; Railway planned. CDP/Base escrow remain subject to PAYMENT_SPIKE.md.
This feature branch adds the job/check/evidence workbench, actual source/register PDFs,
source-backed investigation, bounded corrections and separately authorized additions
to the durable local mock workflow. The base keeps v0.2 and the existing payment
architecture. Local demo sessions do not replace production customer authentication.
See root IMPLEMENTATION_STATUS.md and API_CONTRACT.md for the integrated branch;
docs/API.md remains the original runtime interface. No live money or deployment is run.

## Remaining decisions

- Nikita's payment spike: asset/network/precision, escrow authorization/renewal, live
  extra-fee allowance, reconciliation/finality, and human refund/release operations.
- Jeff + Lucas: crop/rotation transform and real-page bounds for normalized highlights.
- Jeff + Nikita: actual PDF/structured verification tools and provider integration;
  contract validation proves citation binding, not truth of a worker's assessment.
- Team: first fixture review and integration checkpoint in docs/INTEGRATION_CHECKPOINT.md.
