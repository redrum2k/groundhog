# Team responsibilities — catalog v0.3 / payments v1

> Aggregate brokerage update (October 24): new default intake uses
> `aggregate-brokerage-v1`, funded CSV/JSON deliveries and the persisted `/runs` API.
> See [workstream 06](workstreams/06-data-broker.md) for current contracts, commands,
> compatibility boundaries and validation limitations. The catalog-specific details
> below remain historical compatibility guidance and do not set new dataset policy.


This replaces all earlier ownership assignments. The product refactor is authorized; do not
wait for teammate permission to implement it. Nikita and Jeff jointly own shared contracts;
Lucas joins decisions affecting API/display behavior. Preserve each other's working changes.

## Current integration status — October 24

The [frontend/payment integration](reviews/frontend-payment-integration.md) merges
reviewed `593e02f` with published main `04756e1`; implementation merge `4a24c9f`
passed combined offline validation. Nikita's 09b boundary work is complete.
Exact-byte transaction recovery and live proof remain separate future work.
Jeff's published compiler/intake branch advanced from `e774495` to `849e98a`
at the final fetch, including `706f41e`; it remains available but unreviewed/unmerged;
R3/R4 remain two strict expected failures on this main baseline. Prompt 10 may
review audit tooling at `ef8c99a`; no evaluator implementation is included here.
Lucas's `/` retained-broker canvas and `/live` aggregate intake both remain intact.

## Historical jobs after the 09 review — October 24

The [09 review](reviews/09-results-review.md) independently reproduced 695 passing
backend tests and the two known compiler failures, but found two untested attempt
boundaries. Commit `9622fe0` is **not approved for integration yet**.

| Owner | Current job | Completion / next dependency |
| --- | --- | --- |
| Nikita | Finish [09b](codex-prompts/09b-payment-attempt-boundaries.md) in the existing `codex/payment-lease-renewal` worktree: bound slow-streaming HTTP calls and discard late buyer authorizations before reservation. | Exact reviewed commit and boundary regressions; then integrate with current remote main. Scope exact-byte recovery afterward; no live execution is authorized. |
| Jeff | Continue R3/R4 in the existing compiler branch: yoga exclusion/negation and explicit question-bound cohort/geography corrections. | Preserve original cases/history/budgets; remove strict expected-failure markers only after the fixes pass; return an exact independently tested commit. See [handoff](handoffs/jeff.md). |

These jobs can proceed independently. Jeff does not need the unfinished payment
branch; Nikita must preserve the compiler cases. Keep Lucas's newer frontend main
commits during eventual integration. No 09 merge or remote push occurred in this
review. Earlier first-deliverable paragraphs below are historical scope, not a
request to restart completed workstreams.

## Nikita — runtime, agent infrastructure and financial execution

Own `app/orders/catalog.py`, `app/storage/`, `app/runtime/`, `app/payments/`,
`app/api/`, `app/main.py`, `app/catalog/artifacts.py`, `app/catalog/sources.py`,
and `app/agents/gateway.py` transport/budget handling.
Own API/persistence/lifecycle/jobs, retries/concurrency/idempotency, clocks/budgets/leases,
harness/tools/observability, acceptance and amendment gates/version invalidation,
end-to-end payments: current DTOs/configuration/signers, pinned ABI, buyer authorization
verification, dedicated operator transactions, outbox/nonces/ledger/reconciliation, catalog
settlement gates, provider dispatch and backend deployment.

Input: typed drafts, source registry entries, resolved semantic assessments and tool reports.
Output: immutable snapshots, durable jobs, current evidence bindings, waiting/review states,
versioned deliveries, durable payment operations/confirmed bookings and polling views.

First deliverable: draft -> accepted contract -> mock authorization -> durable work -> verified
delivery -> gated mock settlement. It is implemented by the offline repaired journey.
Integrated offline: automatic catalog runtime, reusable Base adapter and terminal payment
laboratory using synthetic accepted terms and a fixture settlement decision, not an AI verdict.
See workstreams/04-integration.md. The next separately authorized milestone is observed live
proof: preflight → prepare/sign →
confirmed funding → restart → full capture; separately fund → full void, 0.10 test USDC each.
Offline/mock/fake implementation does not depend on Jeff's prompts or Lucas's UI. The same
adapter is integrated with the compiler/verification journey and validated through
injected RPC; actual chain evidence remains outstanding. Broadcasts need separate human
authorization. Customer authentication/production isolation precede deployment.
Complete when restart/concurrent retries cannot duplicate acceptance, jobs or capture and
failed/stale/expired work remains blocked. Run tests/catalog, tests/api and tests/payments.

## Jeff — requirements and fulfillment intelligence

Own `app/agents/compiler.py`, `app/catalog/requirements.py`, `app/catalog/documents.py`,
`app/catalog/verification.py`, `app/catalog/amendments.py`, `app/investigation/`,
and `tools/corpus/`. Own gateway prompt/assessment semantics jointly at the narrow transport
boundary; Nikita owns provider credentials, timeouts, budgets and execution enforcement.
Own corpus/extraction/normalization/provenance/PDF coordinates, fulfillment content/document
generation, verification semantics and independent-from-producer checks, investigation
planning/evidence/questions/findings, amendment classification and revalidation, model/prompt
strategy and quality evaluation. He has autonomy over this implementation, not just prompts.

Interfaces:

| Interface | Input | Output / invariant |
| --- | --- | --- |
| ContractCompiler.compile | PrecontractContext: draft, selected registered sources, source observations | CompilerOutput: one clarification or Terms plus summary/limitations. No price or check-removal permissions. |
| extract_source | Registered Source and approved ArtifactStore | ExtractedSource/products with exact spans from actual PDF bytes. No generator truth. |
| produce | Extracted sources and accepted Terms | PDF + JSON artifacts with source hashes/provenance. |
| verify | FulfillmentContext, artifacts, clock, optional actual output PDF | Obligations/assessments/dependencies and Verification; re-extracts source/output independently. |
| SemanticAssessor.assess_obligation | Obligation, claim, bounded resolved EvidencePassages | Pydantic Assessment; citations must resolve; scores are not authority. |
| CatalogInvestigator.investigate | Typed DisputeContext, current report, restricted evidence store | Bounded semantic finding/question suggestion. Cannot execute money operations. |
| assess_amendment | Request-bound amendment, target version and registry | Evidence-only/substantive/unresolved classification, cited assessments, optional registered candidate. Runtime applies consent/version gates. |

First deliverable: prompt -> typed requirements -> cited output -> detected source issue ->
assessed repair. The 48-product synthetic fixture and offline journey supply an executable
foundation. Next: improve semantic planning and document interpretation beyond the bounded
layout; evaluate with Rehan's independent labels; supply real crop/rotation examples to Lucas.
Complete when actual PDFs, citations, exclusions and material unresolved facts agree with
independent review. Run tests/catalog/test_verification.py and tests/investigation.

## Lucas — complete frontend

Own `frontend/`, including the preserved invoice UI, planned catalog React/TypeScript UI and
frontend deployment. Cover prompt
intake/clarification, specification/quote approval, work/delivery/financial status, PDF viewer
and source highlights, targeted complaints, evidence-request answers and amendment upload/
status/approval, additional-work acceptance, reviewer table/controls, polling, stale versions
and server-based timers. Own buyer-wallet signing, exact payment quote/terms, rejected signatures,
held/pending/captured/returned/uncertain/expired displays and observed transaction links. Backend
work intentionally supplies contracts/fixtures without scaffolding the full UI.

Input: OpenAPI, docs/API.md, frontend/contracts.ts, polling views, PDF bytes and normalized
citation rectangles. Output: explicit customer actions bound to current revisions, readable
simulated versus real payment status and cited evidence inspection. Consume the exact funding
typed-data endpoint and submit buyer signatures; never receive operator secrets. Privileged
reviewer/provider/payment-worker routes require a
server-side bridge; never place worker/reviewer credentials in browser code.

First deliverable: request and approve an order, inspect its cited output, answer an evidence
request. Next: implement those screens against the saved fixture DB and add frontend run/test
commands. Complete when 409 triggers refetch, timers use server time, old PDFs remain visible,
and missing evidence/human review/operational failure/payment outcomes are distinct states.
Start now from [Lucas handoff](handoffs/lucas.md) and all-state validated JSON fixtures.

## Rehan — validation, independent evaluation and demo

Own `evals/`, independent expected outcomes and acceptance scenarios, customer examples,
sponsor requirements, usefulness measures/failure analysis, pitch/demo script/backup recording
and judge questions. Jeff owns assessment semantics/evaluation tooling; Rehan supplies the
independent reference judgments. Lucas's visual inspection is useful additional evidence.

Input: source and delivered PDFs and runtime outcomes, inspected independently. Output:
labeled clean, defective, repaired, substantively amended and unresolved cases outside runtime.
First deliverable: those five labeled scenarios, checked from the actual PDFs. Next: verify
Hyphenate/Coinbase/Microsoft requirements from official event material and rehearse both offline
journeys before Sunday, October 25, 2026, 9 a.m. America/Los_Angeles.
Complete when independent labels identify false passes, missed contradictions and useful
abstentions without entering runtime manifests/prompts. No independent gold set is claimed yet. Verify provider receives nothing while held, capture
pays once, void returns funds, provider cannot capture, and uncertainty is never shown as success.
Base Commerce Payments is not x402; actual sponsor eligibility remains unverified.

## Dependencies and handoff

Nikita's state/authority contracts bound Jeff's compiler/checks; Jeff's PDFs/spans feed Lucas's
viewer; all three feed Rehan's independent acceptance review. Shared schema changes need
compatible examples and tests, not a teammate-approval blocking step for this authorized task.
Use docs/INTEGRATION_CHECKPOINT.md. No paid calls, broadcasts or deployment are authorized.

Scoped handoffs: [Nikita](handoffs/nikita.md), [Jeff](handoffs/jeff.md), [Lucas](handoffs/lucas.md), [Rehan](handoffs/rehan.md).
