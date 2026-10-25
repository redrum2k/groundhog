# Hackathon technical reference: Jeff, Nikita and Lucas

This is the ownership filter and study guide for `grill-me`. It describes **who implemented what**, distinguishes that from ongoing team responsibility, and supplies evidence for grading technical answers. It does not change product policy or engineering ownership.

## How the grilling agent must use this reference

1. Establish the participant: **Jeff, Nikita or Lucas**. Ask if their name is not given; do not infer it from the machine owner or Git configuration.
2. Default to **their implemented work in the current aggregate product**. Include their retained compatibility work only when labeled as such. Ask about branch-only experiments only when the participant requests historical work.
3. Select a topic from that person's section, then inspect its current implementation and relevant tests before asking. A random file from the skill's picker is only a candidate: reject it if its substantive behavior belongs to someone else. Do not use an entire directory as an ownership allowlist when this document lists exceptions.
4. For shared files, route by **symbol and mechanism**, not filename, last committer or merge author. Another person's surrounding code can supply context; it must not become the hidden subject of the question.
5. Ask one focused question at a time. Keep the grading anchors private until the participant answers. Test mechanisms, consequences, tradeoffs and failure handling, rather than commit hashes, incidental constants or syntax trivia.
6. Ask cross-owner questions only about the participant's side of a handoff. For example, Lucas can explain how an unresolved payment is displayed without explaining ERC-3009 encoding; Jeff can explain why evidence is insufficient without implementing the payment nonce journal.
7. If responsibility remains ambiguous, skip the question or explicitly ask whether they want a shared-boundary round. Never mark someone wrong for failing to describe a teammate's internals.
8. Recheck current code when grading. This document is a dated reference, not executable truth. Identify uncommitted behavior as work in progress, and do not infer its author.

Suggested invocation:

> Use grill-me with docs/GRILL_ME_REFERENCE.md. I am Jeff. Quiz me on my implemented work in the current aggregate workflow, one question at a time. Exclude other owners' internals and branch-only experiments. Inspect current code and tests before grading.

Replace Jeff with Nikita or Lucas. For broader rehearsal, explicitly request “shared-boundary questions” or “include historical compatibility work.”

## Audit scope and attribution rules

Audited October 24, 2026, America/Los_Angeles, in `order-to-cash` (not the separate `order-to-cash-live` worktree). Baseline: `c0a114755c6afbfeea4f4bc2df5dbee5a3f0defe`, branch `codex/ui-integration-20261024`. Fetched all configured remotes successfully. `origin/main` was `95d3281`; the current branch adds `c0a1147`.

The repository is not shallow. The audit covers **275 commits reachable through `git log --all`**, including **272 branch/remote commits and three stash objects**. HEAD contains 242 commits; origin/main contains 241. Reachable history begins October 23, 2026. This does not claim coverage of deleted, unreachable objects or private branches never published here.

Method: inspect all commit subjects, authors, parents, reachability and changed-file inventories; inspect implementation milestones, current code, targeted blame, tests and owner handoffs. Blame corroborates provenance; line counts and commit counts are not effort or quality scores. Merge commits integrate other people's work and do not transfer authorship. The complete commit index below includes merges, branch-only commits and stash objects.

| Identity normalized to | Git author identities | Branch commits: non-merge / merge | In HEAD | In origin/main |
| --- | --- | --- | --- | --- |
| Jeff | Jeff Vallyath, both personal and GitHub noreply addresses | 89 / 24 | 91 | 91 |
| Nikita | redrum2k; Nikita Afanaskin | 29 / 24 | 50 | 49 |
| Lucas | Lucasvngpl; Lucas | 55 / 44 | 99 | 99 |
| Rehan — excluded from the three quiz pools | Rehan Riyaz, both recorded addresses | 7 / 0 | 2 | 2 |

Nikita also has three stash objects, excluded from the branch-commit counts. Some original feature histories were imported as large single commits: Jeff's original jobflow sequence is represented on HEAD by `39538c0`, and the V5 broker/improvement sequence by `5c8dc72`. Their original branch commits remain in the index; they are not additional independent implementations. `31f6da6` and `f1a9011` are duplicate-titled Nikita UI integration changes on different histories.

Uncommitted changes already present when this audit began: `.env.example`, `backend/app/main.py`, `backend/app/orders/catalog.py`, `backend/app/payments/catalog.py`, `docs/RAILWAY.md`, `frontend/components/run/live-run.tsx`, `frontend/tests/accepted-delivery.test.tsx`, and untracked `backend/tests/dataset/test_mock_payment_pacing.py`. Do not assign those changes to anyone from filesystem state alone. Secrets and private environment files were not needed for this audit.

Authority: [root instructions](../AGENTS.md), [current product policy](../HACK.md), [team responsibilities](responsibilities.md), [frontend instructions](../frontend/AGENTS.md), [investigation instructions](../backend/app/investigation/AGENTS.md), and [evaluation exception](../evals/AGENTS.md). Older handoffs contain superseded route, test-status and implementation statements; check their revision before using them.

## Shared context: understand the story, then hand off the details

The current product is a bounded synthetic aggregate-data order-to-cash workflow. It freezes an agreement, requires explicit funding, produces CSV/JSON, independently checks the actual bytes, handles review and disputes, and gates financial execution. The model interprets language and evidence; application policy and accepted authority control financial effects.

| Surface/profile | What it is | Do not confuse it with |
| --- | --- | --- |
| `/` and `/live`; `aggregate-brokerage-v1` | Primary persisted aggregate request, Customer view, Run canvas and human review for one order | A recorded animation or the older broker policy |
| `/demo`; `/api/broker-run` frontend adapter; `/api/broker` backend | Retained broker canvas and recorded rehearsal fallback; backend `broker-review-v0.3` | Primary funded aggregate execution; retained broker has its own 600-second review / 1,800-second case bound and USDSIM authority |
| `/jobflow`; `/api/jobflow` | Preserved invoice/jobflow workbench and isolated invoice policy | New aggregate contracts or live Base obligations |
| Catalog v0.3 | PDF/sidecar contract workflow and historical payment profiles | The new CSV/JSON happy path |
| `/api/improvements` | Jeff's retained scoped proposal/probe/approval/activation/revoke workflow | Permission to rewrite aggregate scope or global financial policy |

Current aggregate policy is encoded in [contracts/dataset.py](../backend/app/contracts/dataset.py): ages 25–34, synthetic unique adults grouped by ZIP, accepted category meaning, independently pinned coverage, exactly one row per expected key, and columns `zip,area,count,status`. Released counts are integers at least 50. Suppressed counts are null with a distinct status; unknown is not a successful substitute for a count. This is a demo contract rule, not a general privacy guarantee.

Eight checks: **cohort, category, geography, schema, coverage, suppression, provenance, artifact agreement**. New quotes are $1 base, $0.50 Oakland, $0.25 separately offered yoga expansion, $1 replacement. Historical accepted pricing stays frozen. At the accepted demo conversion, $1 = 1,000,000 atomic USDC. Primary review/dispute windows are 60 seconds each; answers do not extend them. Intake allows two questions within 300 seconds. Sources, authority and acceptance are separate concepts.

The handoff chain is:

1. **Jeff:** interpret request/clarification, semantics and source knowledge → typed proposal/evidence.
2. **Nikita:** persist draft, issue server-priced quote, freeze accepted snapshot, confirm funding, dispatch durable work → current authority and state.
3. **Nikita's implemented verifier, Jeff's semantic responsibility:** produce/check bytes → requirement-level findings and resolvable citations.
4. **Jeff:** investigate the complaint and establish supported/unsupported/unresolved meaning → bounded finding/question.
5. **Nikita:** apply correction, consent, review, deadline and financial gates → durable operation and booking.
6. **Lucas:** present the run, evidence and decisions coherently; primary checkout/bridge additions were implemented by Nikita, and learning/financial-evidence panels by Jeff.

All three should know that acceptance, signature, submission, held funds and final settlement are distinct. Detailed internals below belong to their respective quiz pools.

## 1. Jeff owned

**Study focus:** semantic interpretation, evidence-grounded investigation, controlled institutional learning, model qualification, and the historical jobflow/broker/improvement subsystems he implemented.

**Ownership versus authorship:** Jeff is the assigned owner of compiler, fulfillment and verification semantics. The current deterministic CSV producer/verifier and initial catalog compiler/PDF verifier were implemented by Nikita. Quiz Jeff on their semantic contract and how his investigator consumes them; reserve their implementation internals for Nikita unless Jeff opts into the shared area. Conversely, Jeff implemented the model spend wrappers and several UI features despite broader Nikita/Lucas operational ownership.

### J1. Original evidence investigation and jobflow MVP — compatibility

Evidence: original sequence `b92b628` → `178becd`, imported as `39538c0`. Jeff implemented additive contracts, bounded PDF extraction, JSON-pointer/CSV-cell citations, scoped investigation, durable simulated jobflow, API integration, separately authorized change orders and the original React workbench.

Read [investigation/jobflow.py](../backend/app/investigation/jobflow.py), [investigation/documents.py](../backend/app/investigation/documents.py), [runtime/jobflow_commands.py](../backend/app/runtime/jobflow_commands.py), [runtime/jobflow_investigations.py](../backend/app/runtime/jobflow_investigations.py), [storage/jobflow.py](../backend/app/storage/jobflow.py), [components/workbench.tsx](../frontend/components/workbench.tsx), and [lib/use-workbench.ts](../frontend/lib/use-workbench.ts).

Know why a citation must resolve into actual evidence; why a resumed answer binds to the exact pending question; why a correct disputed delivery need not receive a remedy; and why a scope change needs its own authority. These are historical invoice/jobflow semantics, not evidence that new aggregate orders use invoice policy.

Tests: [jobflow investigation](../backend/tests/investigation/test_jobflow.py), [actual PDF evidence](../backend/tests/investigation/test_jobflow_pdf.py), [connected workflow](../backend/tests/jobflow_runtime/test_connected.py), [question resume](../backend/tests/jobflow_runtime/test_question_resume_v5.py).

### J2. Retained broker and bounded improvement loop — compatibility

Evidence: `4df1dab`, `8bcdc35`, `88459e8`, `49a4e82`, imported as `5c8dc72`; later guarded assessment `db7aab8`, recovery `36e9eb8` / `ba79817`.

Read [runtime/broker.py](../backend/app/runtime/broker.py), [runtime/dispute_assessment.py](../backend/app/runtime/dispute_assessment.py), [improvement/service.py](../backend/app/improvement/service.py), [improvement/probes.py](../backend/app/improvement/probes.py), and [contracts/improvement.py](../backend/app/contracts/improvement.py).

Know the difference between a scoped candidate, probe evidence, approval, activation and revocation. An improvement cannot approve itself or rewrite historical accepted policy. Acknowledged investigation work must survive restart; completed deterministic effects must not be re-executed merely because a receipt is being recovered. Accepted amendments must actually affect fulfillment rather than only the displayed terms.

Tests: [improvement](../backend/tests/broker/test_improvement.py), [assessment recovery](../backend/tests/broker/test_assessment_recovery.py), [model identity](../backend/tests/broker/test_improvement_model_identity.py). The V6 catalog-adaptation work at `f388fe3` / `0b1127f` is branch-only as a whole; do not present its entire API/UI as merged. Selected ideas were implemented later in current paths.

### J3. Aggregate compiler, explicit scope consent and bounded intake

Evidence: `de53450`, `ef8c99a`, `706f41e`, `b9476d9`, `43cb18c`, `3f90ad5` built on Nikita's migration `1956f18`.

Read [agents/dataset.py](../backend/app/agents/dataset.py): `compile_dataset`, `_cohort`, `_category`, `_yoga_policy`, `_affirmative`; [contracts/dataset_intake.py](../backend/app/contracts/dataset_intake.py); [agents/gateway.py](../backend/app/agents/gateway.py): `interpret_dataset`, `repair_dataset_clarification`.

The compiler preserves original prompt/history and applies answers to the field solicited by the current question. A model proposal is advisory: it cannot silently widen a gym-only request into the available gym-or-app union, invent cohort acceptance, set the price or remove mandatory checks. Affirmation of a supported cohort must bind to the actual offered question. “Yes, 65+” must not become plain “yes” by stripping digits and operators. Negation, intersection versus union, standalone yoga and unrelated-field corrections are separate semantic problems. Failed or ambiguous interpretation must remain bounded and visible.

Tests: [compiler blockers](../backend/tests/dataset/test_compiler_review_blockers.py), [intake conversation](../backend/tests/dataset/test_intake_conversation.py), [cohort confirmation](../backend/tests/dataset/test_cohort_confirmation.py), [numeric consent](../backend/tests/dataset/test_numeric_consent.py), [intake repair](../backend/tests/dataset/test_intake_repair.py).

### J4. Grounded dispute assessment and honest uncertainty

Evidence: `d2b6ba1`, `5946378`, `1b7ed75`, `60023de`, `3322c82`, `1245d58`, `6a6fe2a`, `0bb253a`.

Read [investigation/dataset.py](../backend/app/investigation/dataset.py): `investigate_dataset`, `independent_claim`, `guarded_dataset_assessment`, `review_dataset_claim`, `supports_candidate`, `supports_semantic_review`, `named_row_references`, `scope_inquiry`; [contracts/semantic.py](../backend/app/contracts/semantic.py).

The packet contains bounded, frozen, resolving evidence and the full complaint. Routing to an artifact does not erase a named ZIP's relevant source/delivery cells. The saved model candidate and raw response are distinct from the effective validated finding. PASS/FAIL describe the particular obligation/claim, not an unconditional payment verdict; a false complaint can produce FAIL while leaving a valid delivery payable through separate gates.

Narrow deterministic certificates can support familiar claims. Novel positive/negative semantic closure can require a blind second review over the same packet, without seeing the first answer. UNKNOWN/CONFLICT remain conservative outcomes. One bounded output-completeness repair is allowed under the existing time budget; disagreement is not permission to retry until models agree. Same-model review is not independent human ground truth.

“Does standalone yoga count?” can be an `answered` scope inquiry. That differs from alleging that owed rows are missing, asking to purchase extra scope, or asserting taxonomy authority. A buyer's willingness to expand scope does not prove that the source classifies yoga as gym membership. Already-owed yoga cannot be sold again.

Tests: [semantic primary](../backend/tests/dataset/test_semantic_primary.py), [blind review](../backend/tests/dataset/test_semantic_review.py), [named ZIP evidence](../backend/tests/dataset/test_named_zip_evidence.py), [scope inquiries](../backend/tests/dataset/test_scope_inquiries.py).

### J5. Durable semantic attempts and recovery — Jeff's narrow runtime contribution

Evidence: `36e9eb8`, `ba79817`, `7b97c2b` and the preceding failing regressions `30ddd34`, `c7f82dd`.

Read `semantic_key`, `semantic_attempt`, `stale_semantic_attempt` in [investigation/dataset.py](../backend/app/investigation/dataset.py), `reclaim_dataset_assessment` in [orders/dataset.py](../backend/app/orders/dataset.py), and their hook in `CatalogService.claim_job` in [orders/catalog.py](../backend/app/orders/catalog.py).

Persist an attempt before model dispatch. Polling must not make paid calls. An uncertain prior dispatch is not retried as if it never happened. A completed assessment can survive a pure job-lease reclaim even though claiming increments the application revision: the recovery must prove that only that claim changed, preserve original provenance, and reject changed evidence/complaint/answers, intervening revisions, expired cases or stale work. A superseded worker must not overwrite its successor's valid recovery.

Tests: [semantic recovery](../backend/tests/dataset/test_semantic_recovery.py), [broker recovery](../backend/tests/broker/test_assessment_recovery.py). Generic worker scheduling, payment leases and nonce recovery remain Nikita's deep-dive topics.

### J6. Model spend controls and audited provider calls

Evidence: `db7aab8`, `43cb18c`, `76b1da5`; current `budget.py` and `bounded_client.py` are Jeff's implementation despite the general runtime ownership assignment.

Read [agents/budget.py](../backend/app/agents/budget.py): `ModelBudget.reserve`, `finish`, `abort_before_dispatch`, `register_budget_authorization`; [agents/bounded_client.py](../backend/app/agents/bounded_client.py): `BoundedClient`, `BoundedAsyncClient`, `remaining_timeout`; [local_model_qualification.py](../backend/app/local_model_qualification.py).

The shared model-use ledger reserves bounded cost/concurrency before dispatch and records usage or uncertain failure afterward. Reopening a process or changing an authorization window must not erase cumulative spend. A failure before dispatch differs from an uncertain dispatched request. SDK retries are disabled; semantic repair is a separate counted action. Budget-only authorization still needs an explicitly registered grant, existing cumulative accounting and per-request timeouts. This ledger measures model usage; it is not a second customer-payment ledger.

Tests: [model budget](../backend/tests/investigation/test_model_budget.py), [authorized windows](../backend/tests/investigation/test_authorized_windows.py), [raw response](../backend/tests/investigation/test_raw_model_response.py), [qualification boundary](../backend/tests/source_learning/test_model_qualification_boundary.py). Do not quiz Jeff on payment HTTP subprocess cancellation merely because both features have timeouts.

### J7. Source-specific institutional knowledge and controlled activation

Evidence: `bb7edc1`, `c1de7f3`, `6defeb7`, `75eb252`, `072a58b`, `447a8f1`, `17d8e98`.

Read [agents/source_knowledge.py](../backend/app/agents/source_knowledge.py): `SourceKnowledge`, `InstitutionalMemory`; [agents/source_preparation.py](../backend/app/agents/source_preparation.py); [catalog/preparation.py](../backend/app/catalog/preparation.py); [learning/service.py](../backend/app/learning/service.py): `publish`, `compile`, `resolve`, `propose`, `qualify`, `transition`; [learning/qualification.py](../backend/app/learning/qualification.py); [source-learning UI](../frontend/components/run/source-learning.tsx).

An authorized, simulated source-owner explanation establishes a scoped convention, such as the unique-adult column or composition of disjoint partitions. The system records evidence, derives a typed procedure, qualifies it, and requires explicit controller approval/activation. Later independent orders read fresh bytes using that approved convention. This is stored institutional knowledge, not weight training, cached verdicts or arbitrary self-modifying code.

Applicability depends on publisher/source family, schema/version/hash, edition, scope/unit and current authority. Conflict, expiry, revocation and historical publication must block inappropriate reuse. An order-only resolution cannot silently become cross-order authority. Prepared sources are request-local, so overlapping intakes cannot overwrite each other's selected source edition. Clarification must retain that preparation; quote and acceptance still recheck authority. Owner correction and its durable effects must commit atomically.

Tests: [live learning](../backend/tests/source_learning/test_live_learning.py), [safety](../backend/tests/source_learning/test_learning_safety.py), [historical authority](../backend/tests/source_learning/test_historical_authority.py), [source knowledge](../evals/source_learning/test_source_knowledge.py), [learning UI](../frontend/tests/source-learning.test.tsx).

The [final qualification](HYPHENATE_FINAL_QUALIFICATION.md) reports two initial owner explanations and zero repeated owner questions on three later fresh orders, including after restart. That measures avoided repeated interventions in synthetic engineering cases; approval is extra governance work, and no labor-time or dollar-saving estimate follows automatically.

### J8. Financial explanations, fractional display and qualification evidence

Evidence: `c0aa7df`, `a52c642`, `368cb96`, `0bb253a`, `f80bc3a`, `b031cc1`, `c2ce32b`, `82dd93a`.

Read [orders/payment_justification.py](../backend/app/orders/payment_justification.py), [payment-justification panel](../frontend/components/run/payment-justification.tsx), [backend money formatting](../backend/app/money.py), [frontend money formatting](../frontend/lib/money.ts), [judge journey](../tools/judge_journey.py), [byte/record audit](../tools/audit_judge_journey.py), and [model audit](../tools/audit_model_journey.py).

The justification endpoint reads the accepted snapshot, current byte checks, source/delivery hashes, cases, decisions, payment operations and bookings. It queries the existing capture guard with an unpersisted intent. Reading cannot reserve a payment, dispatch a model or settle funds. “Eligible now” is not a reconstruction of why a historical booking was authorized. Fractional prices must survive narration and display; money calculations/signatures remain exact minor/atomic integers rather than floats.

The audit binds dispatched requests, raw provider responses, effective findings, citations, usage and financial identities. Preserve negative cohorts and disagreements; do not overwrite them with a later passing run. Engineering regression cases and same-model agreement do not establish independent held-out accuracy. Jeff's browser/launcher/qualification work is his own contribution even though most frontend ownership belongs to Lucas.

Tests: [payment justification](../backend/tests/dataset/test_payment_justification.py), [money narration](../backend/tests/dataset/test_money_narration.py), [model journey audit](../backend/tests/dataset/test_model_journey_audit.py), [financial panel](../frontend/tests/payment-justification.test.tsx), [money UI](../frontend/tests/money.test.tsx).

### Jeff question pool and grading anchors

| ID | Ask one question about | A sufficient answer must explain |
| --- | --- | --- |
| J-Q1 | Why “yes, 65+” cannot accept the supported cohort | Exact question-bound offer; qualifiers preserved; no silent widening or normalization into consent |
| J-Q2 | Difference between yoga scope and taxonomy authority | Accepted promise versus independently established category evidence; new purchase versus already-owed delivery |
| J-Q3 | Why a parsed model verdict may not become the effective finding | Resolving citations, claim support, deterministic certificate or bounded blind review, uncertainty fallback |
| J-Q4 | What the blind reviewer sees and what disagreement means | Same frozen complaint/evidence without first answer; valid disagreement holds, not retry-until-agreement |
| J-Q5 | Recovery after a pure assessment-job lease reclaim | Durable attempt identity, original provenance, restricted revision carry-forward and stale/deadline checks |
| J-Q6 | What happens to model spend after an uncertain call and restart | Persisted reservation/usage, no spend reset, no automatic uncertain retry |
| J-Q7 | Why learning does not copy an old dataset | Scoped approved procedure applies to new bytes; bindings and current authority checked |
| J-Q8 | Why simultaneous prepared intakes need request-local sources | One request cannot mutate another's selected edition; clarification and acceptance retain/revalidate pins |
| J-Q9 | Why reading payment justification cannot move money | Projection plus existing guard query; no persisted operation; current eligibility versus historical evidence |
| J-Q10 | What the 2 → 0 learning result actually proves | Synthetic repeated owner-question reduction, separate governance cost, no general accuracy/labor-savings claim |

**Exclude by default:** Base ABI/ERC-3009 details, operator nonce serialization, payment-worker cancellation/scheduling, Lucas's camera/motion algorithms, and Rehan's sealed labels. Ask byte-verifier internals only in a shared round; Jeff owns their semantic requirements but did not author the current deterministic engine.

## 2. Nikita owned

**Study focus:** durable execution, acceptance/consent/payment authority, the aggregate migration and deterministic verifier, live checkout/bridge integration, evaluation infrastructure and operational safeguards.

**Ownership versus authorship:** Nikita owns the shared runtime/payment plane. He also implemented significant compiler/verifier foundations and primary frontend behavior. Do not erase those contributions by assigning all intelligence to Jeff and every frontend file to Lucas. Jeff's later semantic/model-budget work remains Jeff's quiz material.

### N1. Foundation, compatibility and aggregate migration

Evidence: `6ac1810`, `06112e2`, `0326ae6`, integration `53accd2` / `ac385a1`, aggregate migration `1956f18`.

Read [orders/service.py](../backend/app/orders/service.py), [orders/catalog.py](../backend/app/orders/catalog.py), [contracts/catalog.py](../backend/app/contracts/catalog.py), [contracts/dataset.py](../backend/app/contracts/dataset.py), [main.py](../backend/app/main.py), and [workstream 06](workstreams/06-data-broker.md).

The product evolved from invoice review to catalog contracts/Base payment terms and then aggregate brokerage. New aggregate behavior extends existing CatalogService, persistence, jobs and financial execution. It does not create a second payment ledger or reinterpret saved v0.2/v0.3 records as live obligations. Accepted snapshots retain their original pricing, source pins, policy and authority. Existing invoice/broker routes stay isolated.

Tests: [merged profiles](../backend/tests/broker/test_merged_profiles.py), [merged runtime](../backend/tests/api/test_merged_runtime.py), [catalog contracts](../backend/tests/catalog/test_contracts.py), [dataset lifecycle](../backend/tests/dataset/test_lifecycle.py).

### N2. Durable commands, idempotency and version fencing

Evidence: `0326ae6`, `3a7b754`, `39dd586`, `692f500`.

Read [storage/catalog.py](../backend/app/storage/catalog.py): `replay`, `remember`, `fingerprint`; [orders/catalog.py](../backend/app/orders/catalog.py): `compile_request`, `accept_quote`, `mutate`, `_check`, `_invalidate`, `claim_job`, `_check_job`; [storage/catalog_dispatch.py](../backend/app/storage/catalog_dispatch.py); [runtime/catalog_worker.py](../backend/app/runtime/catalog_worker.py).

A command's durable effects and exact saved response commit together. Same key/same request replays; changed payload or stale expected revision/binding returns 409. The binding tracks snapshot, delivery version and evidence revision. Evidence changes invalidate dependent findings/approvals/jobs rather than reusing stale authority. Lease ownership and job checks stop superseded workers from committing effects. Compiler dispatch is reserved durably and bounded; it is not a side effect of browser polling.

Tests: [catalog lifecycle](../backend/tests/catalog/test_lifecycle.py), [approvals](../backend/tests/catalog/test_approvals.py), [catalog worker](../backend/tests/runtime/test_catalog_worker.py), [lifespan](../backend/tests/runtime/test_catalog_lifespan.py). Jeff owns the special completed-semantic-assessment recovery exception described in J5.

### N3. Actual source/delivery verification and artifact publication

Evidence: catalog foundation `0326ae6`, aggregate implementation `1956f18`, hardening `692f500`, preview-failure recovery `845b7c5`. At the audited HEAD, [datasets.py](../backend/app/datasets.py) is Nikita's implementation; the assigned semantic owner is Jeff.

Read `seed_registry`, `produce_dataset`, `verify_dataset`, `resolve_reference`, `public_bytes` in [datasets.py](../backend/app/datasets.py); [catalog/artifacts.py](../backend/app/catalog/artifacts.py); `current_dataset_checks`, `run_dataset`, `complaint_targets` in [orders/dataset.py](../backend/app/orders/dataset.py).

The producer's output is not proof of correctness. Verification reopens accepted source, coverage, authority and delivered CSV/JSON bytes. It checks exact schema, source metadata, every expected key once, missing/duplicate/unknown rows, suppression, provenance and agreement between artifacts. Absence evidence includes the checked artifact and frozen coverage denominator. Citation identity includes hash, source/version and row/column, not merely a plausible quoted value.

Public output must not disclose exact suppressed counts or accept arbitrary raw JSON through a missing discriminator. Missing preview bytes must not prevent order polling or the customer's ability to complain. Before capture, current byte revalidation can block settlement even when a saved report once said PASS.

Historical catalog code in [catalog/verification.py](../backend/app/catalog/verification.py), [catalog/documents.py](../backend/app/catalog/documents.py), [catalog/requirements.py](../backend/app/catalog/requirements.py) and [agents/compiler.py](../backend/app/agents/compiler.py) also originated in Nikita's baseline. PDF content/interpretation remains Jeff's assigned domain; no PDF belongs in the new aggregate happy path.

Tests: [delivery](../backend/tests/dataset/test_delivery.py), [faults](../backend/tests/dataset/test_faults.py), [artifact availability](../backend/tests/dataset/test_review_artifact_availability.py), [review targets](../backend/tests/dataset/test_review_targets.py), [artifact publication](../backend/tests/catalog/test_artifact_publication.py).

### N4. Settlement gates, correction and time budgets

Evidence: `1483046`, `1956f18`, `692f500`, `99a5bfe`.

Read [runtime/catalog_policy.py](../backend/app/runtime/catalog_policy.py), [runtime/dataset_policy.py](../backend/app/runtime/dataset_policy.py): `fits`, `cutoff`; [payments/catalog.py](../backend/app/payments/catalog.py): `_eligible`, `work_allowed`, `reserve_terminal`; [orders/catalog.py](../backend/app/orders/catalog.py): `_capture`, `_reserve_correction`, `complete_verification`; [orders/runs.py](../backend/app/orders/runs.py): `offer`, `decide`, `answer`.

Acceptance freezes terms but does not fund the order. Confirmed exact funding or explicit mock simulation enables work. Capture also requires current mandatory checks, no material blocker/unresolved dispute/pending consent, current customer acceptance or undisputed review expiry, unexpired authority and no competing terminal operation. A model verdict cannot satisfy those conditions on its own.

One established provider-output defect can consume the durable free-correction allowance; a source problem alone or an operational retry must not. A substantive replacement waits for confirmed parent void before child funding/work. Ordinary additional work has a separate accepted quote/authorization. Failed or uncertain void is not successful return; post-capture refunds are unimplemented.

Scheduling reserves fulfillment, a full review plus last-instant dispute, an unused correction and another review/dispute cycle, then a transaction margin before signed expiry. `fits` uses strict remaining-time comparisons. Insufficient time persists human review; it does not extend the signed deadline or shorten promised review. Already-submitted operations still reconcile after cutoff.

Tests: [catalog settlement](../backend/tests/payments/test_catalog_settlement.py), [review boundary](../backend/tests/dataset/test_review_boundary.py), [payment lease](../backend/tests/dataset/test_payment_lease.py), [failed return](../backend/tests/dataset/test_failed_return.py), [review payments](../backend/tests/dataset/test_review_payments.py).

### N5. Base Commerce Payments transport and buyer authorization

Evidence: `0326ae6`, `a23f999`, `39dd586`, `f8a929a`.

Read [payments/base.py](../backend/app/payments/base.py): `BasePaymentTransport`, `preflight`, `calldata`, `prepare_transaction`, `reconcile`; [payments/base_rpc.py](../backend/app/payments/base_rpc.py): `PinnedAbi`, `HttpRpc`; [payments/base_config.py](../backend/app/payments/base_config.py); [ABI provenance](../backend/app/payments/abi/README.md); [payment runbook](PAYMENT_RUNBOOK.md); [laboratory](../spikes/payments/README.md).

The implemented rail is direct Base Commerce Payments on Base Sepolia, with a dedicated operator and exact frozen PaymentInfo, chain, token, parties, amount and deadlines. ERC-3009 ReceiveWithAuthorization authorizes the collector, exact amount and expiry; the authorization nonce uses the escrow hash with payer zeroed, while the actual payment hash uses the real payer. Domain verification is against USDC's domain separator, not a guessed token label. A transfer to an address is not equivalent to the collector authorization flow.

The buyer signs exact prepared typed data; the operator signs the chain transaction. Full capture uses zero fee and the pinned v1.1 ABI; void releases uncaptured funds. Expiry only enables the relevant recovery path, not proof that cash returned. Two canonical confirmations are the configured demo threshold, not L1 finality. Private keys, raw signed transactions and authorizations do not belong in public artifacts or model input.

Tests: [protocol](../backend/tests/payments/test_base_protocol.py), [transport](../backend/tests/payments/test_base_transport.py), [laboratory](../backend/tests/payments/test_payment_lab.py), [readiness](../backend/tests/payments/test_payment_readiness.py). The isolated 0.10 test-USDC fixture is not payment for an unrelated accepted order.

### N6. Outbox, nonce serialization, reconciliation and atomic booking

Evidence: `0326ae6`, `1483046`, `a23f999`, `39dd586`, later `99a5bfe`.

Read [payments/journal.py](../backend/app/payments/journal.py): `reserve`, `reserve_nonce`, `save_signed`, `confirm`, `invalidate`; [payments/executor.py](../backend/app/payments/executor.py): `_process`, `_reconcile`; [payments/catalog.py](../backend/app/payments/catalog.py): `complete`, `changed`.

Reserve one terminal capture/void operation. Persist signed bytes/hash before broadcast and serialize operator nonce reservation. The durable `submitted` transition precedes the network send; an ambiguous outcome retains that identity for reconciliation. It is not safe to invent a new salt/nonce or claim a sent transaction was cancelled after a complaint. Receipt, matching payment events/state and canonical-block checks establish confirmation; balances corroborate rather than substitute for payment-specific evidence.

Submission does not book funds. Confirmed observation, payment state and ledger effect commit together, idempotently. Reorg/uncertainty must become a hold, not automatic duplicate fulfillment or transfer. Do not claim unrestricted exact-byte rebroadcast recovery: inspect the executor's current supported transitions and the runbook before describing a retry path.

Tests: [journal](../backend/tests/payments/test_journal.py), [journal/catalog](../backend/tests/payments/test_journal_catalog.py), [transport](../backend/tests/payments/test_base_transport.py).

### N7. Payment attempt bounds, worker fairness and latency diagnosis

Evidence: `9622fe0`, `593e02f`, `99a5bfe`; see [lease workstream](workstreams/09-payment-lease-renewal.md), [payment scheduling review](reviews/payment-scheduling-20261024.md).

Read [payments/attempt.py](../backend/app/payments/attempt.py): `PaymentAttempt`, `checkpoint`; [payments/base_rpc.py](../backend/app/payments/base_rpc.py): `HttpRpc.request`; [payments/_http_request.py](../backend/app/payments/_http_request.py); `pending`, `renew_claim`, `owns` in [payments/journal.py](../backend/app/payments/journal.py); [runtime/background.py](../backend/app/runtime/background.py).

Renewing a worker lease does not extend payment authority. A monotonic elapsed attempt budget, current lease/ownership and original action deadline all constrain execution. Slow streaming must be cancellable across the entire HTTP operation, not merely socket inactivity. The disposable HTTP process provides a hard bound; late buyer authorization is rejected before reservation.

Historical receipt audits once competed equally with active funding/capture. The current journal selects unfinished work preferentially and periodically gives due confirmed-receipt audits a fair turn; only the latest relevant receipt is audited, with a cadence. Preserve uncertain-operation fairness and reorg detection. Application observation delay is different from chain inclusion latency, and the 0.25-second worker interval is not a bound on a full work call.

Tests: [lease renewal](../backend/tests/payments/test_lease_renewal.py), [HTTP boundary](../backend/tests/payments/test_http_boundary.py), [scheduling](../backend/tests/payments/test_scheduling.py). Already-present uncommitted mock-pacing work is not part of this committed attribution.

### N8. Persisted run API, primary live checkout and wallet integration

Evidence: `1956f18`, `692f500`, `a66c3cf`, `99a5bfe`, `c0a1147`. These are substantive Nikita frontend contributions, while Lucas owns ongoing frontend design.

Read [orders/runs.py](../backend/app/orders/runs.py), [orders/run_events.py](../backend/app/orders/run_events.py), [storage/runs.py](../backend/app/storage/runs.py), [run/live.ts](../frontend/lib/run/live.ts), [run/checkout.ts](../frontend/lib/run/checkout.ts), [run/wallet.ts](../frontend/lib/run/wallet.ts), [run/use-live-order.ts](../frontend/lib/run/use-live-order.ts), [live-customer.tsx](../frontend/components/run/live-customer.tsx), [live-order.tsx](../frontend/components/run/live-order.tsx).

Events are persisted with monotonic sequence/cursor semantics. The primary browser merges by sequence and guards old responses after switching runs; it waits until caught up before enabling mutations. Errors preserve last confirmed state while withholding stale permissions. A 409 refetches and asks the customer to review/click again; it does not silently replay approval against a new revision. Run creation and checkout use stable identities to recover lost responses.

Checkout separates agreement acceptance, current-state inspection, funding preparation, exact wallet signing and authorization submission. It validates quote/order/payment hash/mode/amount, rechecks wallet account/network around signing, and checks cancellation after the wallet popup. Existing pending funding must not ask for another signature blindly. Explicit mock funding is a separate, disclosed path. Customer view, Run and human review refer to the same backend order.

Tests: [run polling](../frontend/tests/run-live.test.ts), [checkout](../frontend/tests/checkout.test.tsx), [wallet settings](../frontend/tests/wallet-settings.test.tsx), [human review](../frontend/tests/human-review-progress.test.tsx), [payment progress](../frontend/tests/payment-progress.test.tsx).

### N9. Trusted bridge, hosted demo and deployment configuration

Evidence: `1956f18`, `a66c3cf`, `99a5bfe`, `95d3281`.

Read [live-bridge.ts](../frontend/lib/live-bridge.ts), [hosted-demo.ts](../frontend/lib/hosted-demo.ts), [proxy.ts](../frontend/proxy.ts), [Railway runbook](RAILWAY.md), and [main.py](../backend/app/main.py).

The browser does not receive worker/reviewer tokens. The server bridge allowlists paths, routes distinct privileged credentials, validates origin/mode and refuses unsupported operations. Local mode is trusted loopback. Hosted shared-password mode is operator demo access, not customer/tenant authentication. Explicit public mode permits the aggregate bridge only after backend capabilities confirm mock payments and disabled live settlement; it does not publish arbitrary privileged APIs. Source learning remains local-only. A failed live backend is an error, not grounds to substitute recorded success.

Tests: [hosted demo](../frontend/tests/hosted-demo.test.ts), plus bridge assertions in the frontend tests. Configuration and historical deployment evidence do not authorize any new deployment during a quiz.

### N10. Aggregate evaluator and integration evidence

Evidence: `ade5d8e`, `ee8fd85`, `fd3e337`; explicit ownership exception in [responsibilities](responsibilities.md) and [eval instructions](../evals/AGENTS.md).

Read [tools/aggregate_eval.py](../tools/aggregate_eval.py), [evals/aggregate/runner.py](../evals/aggregate/runner.py), [evals/aggregate/audit.py](../evals/aggregate/audit.py), [workstream 10](workstreams/10-aggregate-evaluation.md).

Nikita implemented isolated execution, requirement-level scoring, independent byte/citation audit integration and readable reports. Startup failures are classified without leaking raw exception text; completed checkpoints survive later audit failure. Rehan owns independent expectations, rationales and held-out classification. Bundled engineering labels are not independent gold, and expected answers/mutation recipes cannot enter runtime DTOs or model context. Jeff's later real-model qualification and source-learning audits are separate tooling contributions.

Tests: [evaluator runner](../backend/tests/evals/test_runner.py), [evidence audit](../backend/tests/evals/test_audit.py). Nikita also integrated multiple owner branches; merge authorship does not mean he authored the imported subsystem.

### Nikita question pool and grading anchors

| ID | Ask one question about | A sufficient answer must explain |
| --- | --- | --- |
| N-Q1 | Lost acceptance response followed by a retry | Atomic stored response/effects; same fingerprint replay; changed request 409; no duplicate job |
| N-Q2 | Why a PASS report alone cannot trigger capture | Current binding/bytes, funding, review/acceptance, blockers, consent, deadlines and terminal exclusivity |
| N-Q3 | Detecting an omitted ZIP rather than trusting row count | Independent frozen coverage denominator, exact key uniqueness, actual bytes and resolvable absence evidence |
| N-Q4 | Why an evidence answer invalidates stale approvals | Evidence revision/binding changes and dependent findings/jobs/approvals cannot carry old authority |
| N-Q5 | Why a correction cannot begin near authorization expiry | Strict reserved lifecycle budget plus margin; immutable cutoff; hold rather than shortened review |
| N-Q6 | Crash after submitted state but before known broadcast outcome | Saved signed hash/nonce, ambiguous reconciliation, no fresh payment identity or premature booking |
| N-Q7 | Why lease renewal does not allow unbounded payment work | Monotonic attempt bound, current owner fencing, original authority cutoff and cancellable HTTP |
| N-Q8 | Why old confirmed payments delayed a new capture | Shared worker selection/expensive audit contention, active priority with bounded audit fairness |
| N-Q9 | Reload while funding status is uncertain | Stable checkout identities, current state inspection, no blind repeat signature, pending versus confirmed |
| N-Q10 | Why public demo mode cannot use the live payment backend | Explicit mode, capability check, route allowlist and server-only credentials; not production auth |
| N-Q11 | Who owns aggregate evaluator expectations | Runner/audit infrastructure is Nikita; independent labels and held-out rationale are Rehan |

**Exclude by default:** Jeff's novel-language review algorithm, learning induction/qualification internals, model-budget ledger internals, Lucas's detailed camera/motion behavior and Rehan's evaluation labels. Nikita should know these interfaces, not be graded as their implementer.

## 3. Lucas owned

**Study focus:** the run canvas and visual system, event-to-presentation projection, retained broker adapter, customer/reviewer interaction, evidence display and motion/navigation.

**Ownership versus authorship:** Lucas is the complete frontend/design owner, but the original invoice workbench was Jeff's, primary checkout/wallet/bridge was Nikita's, and learning/financial-explanation panels were Jeff's. Those implementations are excluded from Lucas's default internals quiz. His duty to integrate their display does not mean he wrote their mechanics.

### L1. Run canvas, event contract and state projection

Evidence: `90d14ef`, `391ed11`, `b4dc717`; later `05a32cd`, `c63c775`.

Read [run/canvas.tsx](../frontend/components/run/canvas.tsx), [run/panel.tsx](../frontend/components/run/panel.tsx), [run/checklist.tsx](../frontend/components/run/checklist.tsx), [run/run-app.tsx](../frontend/components/run/run-app.tsx), [run/contract.ts](../frontend/lib/run/contract.ts), [run/fold.ts](../frontend/lib/run/fold.ts), and [run.css](../frontend/app/run.css).

Lucas built the canvas presentation and initial event vocabulary/projection. Rendering derives nodes, messages, evidence, delivery and financial presentation from events rather than executing business policy. The fold is now shared: Lucas owns the original canvas projection; Nikita added primary lifecycle/payment transitions; Jeff added fractional display and scope-answer projection fixes. Inspect the specific event case before choosing its quiz owner.

Know how the contract, view model and node statuses compose; how the path progressively reveals work; and why an evidence gap or human review is visually different from an operational failure. An animation completing cannot authorize payment or resolve a dispute.

Tests: [run app](../frontend/tests/run-app.test.tsx), [scenario](../frontend/tests/run-scenario.test.ts), [canvas connectors](../frontend/tests/canvas-connectors.test.tsx). Primary settlement-progress cases in the fold belong to Nikita unless Lucas opts into the shared topic.

### L2. Backend broker adapter and recorded/live feed separation — retained demo

Evidence: `bd7e8d1`, `7c5ccbc`, `0189de6`, `339c602`, `c06fa5d`, `4aaf720`, `4f3d08f`.

Read [broker/client.ts](../frontend/lib/run/broker/client.ts), [broker/driver.ts](../frontend/lib/run/broker/driver.ts), [broker/store.ts](../frontend/lib/run/broker/store.ts), [broker/translate.ts](../frontend/lib/run/broker/translate.ts), [run/source.ts](../frontend/lib/run/source.ts), [run/scenario.ts](../frontend/lib/run/scenario.ts), and [demo page](../frontend/app/demo/page.tsx).

The adapter invokes the retained broker and translates persisted backend state/events into the canvas contract. It includes demo orchestration/scripted customer actions; “live broker” does not mean every intake action is spontaneous model reasoning. Recorded scenarios are an explicit rehearsal feed, not authoritative financial history. A poll's event burst can be presented one event at a time without changing backend authority. Live narration comes from the live feed, not recorded captions. `dispute.assessed` must preserve who assessed the case and its quoted evidence.

Tests: [driver](../frontend/tests/broker-driver.test.ts), [translation](../frontend/tests/run-translate.test.ts), [broker live](../frontend/tests/broker-live.test.tsx), [buyer actions](../frontend/tests/run-buyer.test.ts). Primary `/api/live` cursor/idempotency mechanics are Nikita's separate adapter.

### L3. Customer view, decision focus and coherent objections

Evidence: `0189de6`, `ebf9086`, `0080aa8`, `6c3a397`, `67c7d58`, `9668324`, `d0417a4`, `f52535f`, `c916989`, `53b5086`, `be76347`.

Read [run/customer.tsx](../frontend/components/run/customer.tsx), [run/guide.tsx](../frontend/components/run/guide.tsx), [run/inspector.tsx](../frontend/components/run/inspector.tsx), [run/panel.tsx](../frontend/components/run/panel.tsx), and [run/run-app.tsx](../frontend/components/run/run-app.tsx).

Customer view focuses on the buyer's next meaningful decision and follows conversation/delivery as the run evolves. Returning to Run should show the agent's current work rather than leaving focus on a completed buyer action. Objection text, investigation, finding and human decision form one comprehensible flow. A reopened review must preserve state; closing a view is not resolving a case. Background page scroll should not fight the customer overlay. Modern primary screens reuse the visual language but their live-order commands were implemented by Nikita.

Tests: [customer review](../frontend/tests/customer-review.test.tsx), [run app](../frontend/tests/run-app.test.tsx), [broker live](../frontend/tests/broker-live.test.tsx). Avoid testing Lucas on backend dispute deadlines merely because the interface displays them.

### L4. Evidence, source visualization and understandable review states

Evidence: `3e6d865`, `2463d24`, `c06fa5d`, `49fb413`, `ae527e6`, `18763ae`, `6c3a57c`.

Read [inspector.tsx](../frontend/components/run/inspector.tsx), [warehouse.tsx](../frontend/components/run/warehouse.tsx), [checklist.tsx](../frontend/components/run/checklist.tsx), [panel.tsx](../frontend/components/run/panel.tsx), and [broker/translate.ts](../frontend/lib/run/broker/translate.ts).

Contract line ordering should follow the clarified conversation; formatting age ranges should not change their meaning. Large delivery tables scroll within their surface. Evidence inspection connects a finding to the actual provided references, rather than treating decorative source graphics as proof. Human review should say what is unresolved and make the recorded decision understandable. A live step's own flags take precedence over assumptions inherited from a recorded scenario.

The 27-ZIP recorded display was a demo fixture improvement, not an independent assertion about real San Francisco boundaries. The backend's frozen coverage registry remains authoritative. Evidence color/label bugs must be graded against current code: do not repeat an old handoff's UNKNOWN-color finding as if it necessarily remains unfixed.

Tests: [evidence targets](../frontend/tests/broker-evidence-targets.test.tsx), [translation](../frontend/tests/run-translate.test.ts), [scenario](../frontend/tests/run-scenario.test.ts).

### L5. Camera, mascot and motion sequencing

Evidence: `05a32cd`, `55d62bc`, `c63c775`, `37d66e1`, `8d180af`, `c697d09`, `69d3360`, `f12ad6a`, `c991fd6`, `1f31360`.

Read [canvas.tsx](../frontend/components/run/canvas.tsx), [orb.tsx](../frontend/components/run/orb.tsx), [guide.tsx](../frontend/components/run/guide.tsx), [icons.tsx](../frontend/components/run/icons.tsx), and [run.css](../frontend/app/run.css).

Know how the camera frames the current step, how rapid step changes avoid a distracting sequence of separate trips, and how scroll/view transitions coordinate with mascot arrival. The later burrow design ducks the character completely, waits, then emerges at a new hole; the hole itself should not slide across the canvas. Returning mid-run should align the character with the current step. Reduced motion and cleanup behavior should be checked in the current implementation, not assumed from an animation description.

Attribution caveat: Rehan supplied the detective groundhog artwork/code in `c08b663` and its color change `a945262`. Lucas integrated it through `5f8a96c` and subsequent motion/design work. Do not credit Lucas with sole creation of Rehan's mascot, or ask him to explain Rehan's branch-only trail experiments.

Tests: [canvas connectors](../frontend/tests/canvas-connectors.test.tsx) and current component tests; for visual claims use the code and recorded visual evidence rather than claiming unit tests establish every animation detail.

### L6. Product language, route integration and frontend contracts

Evidence: `e408c0c`, `7c906d2`, `580fc33`, `3fb6a4b`, `8b7d914`, `ef40191`, `24ed18c`, `d03918f`, `ed6390b`.

Lucas revised the human-review persona, customer/provider/agent naming and demo narration, and made narrow backend copy edits where those labels were emitted. Groundhog is the agent; the displayed provider and customer are separate parties. Friendly names do not change accepted stored parties. The historical route note placing the canvas at `/` was superseded: primary intake is now `/` and `/live`; retained demo is `/demo`.

Read [frontend instructions](../frontend/AGENTS.md), [contract generator](../frontend/scripts/generate-contracts.mjs), [run-app.tsx](../frontend/components/run/run-app.tsx), [scenario.ts](../frontend/lib/run/scenario.ts), and [frontend package commands](../frontend/package.json). Backend DTOs generate clients together; canvas-only narration extends the generated contract rather than hand-editing it. The generator originated with Jeff and was extended by several contributors; regeneration commits alone do not establish schema authorship.

Simplifying payment copy never turns simulated receipts into real settlement. Be able to identify the actual disclosure and the difference between pending, held, captured, returned, uncertain and expired-not-returned displays. Underlying funding signature and operator execution details are Nikita's domain.

### Lucas question pool and grading anchors

| ID | Ask one question about | A sufficient answer must explain |
| --- | --- | --- |
| L-Q1 | How an event becomes visible run state | Event contract → fold/view model → node/panel rendering; no authority granted by animation |
| L-Q2 | Difference between retained live broker and recorded rehearsal | Backend adapter versus explicit scenario feed; scripted demo actions disclosed; no invented live outcomes |
| L-Q3 | Why a poll burst is presented incrementally | Ordered event presentation/pacing without replacing backend results or treating pacing as a policy clock |
| L-Q4 | How a buyer objection stays understandable across views | Buyer action, focus/scroll transition, investigation/finding and retained review state |
| L-Q5 | How `dispute.assessed` appears in the canvas | Assessor/provenance and resolving references translated into evidence and finding presentation |
| L-Q6 | Why a live step's flags override recorded defaults | The current event specifies behavior; prerecorded case assumptions cannot hide a live panel/action |
| L-Q7 | How camera/mascot transitions handle rapid updates | Current-step framing, coalesced travel, coordinated scroll/arrival and current view restoration |
| L-Q8 | Which UI state is authoritative for money | Backend payment state, not coin/orb position; distinguish pending/uncertain from confirmed |
| L-Q9 | Why changing displayed party names must not alter financial parties | Product copy is presentation; frozen accepted payer/receiver/operator and order identity remain backend data |

**Exclude by default:** original workbench internals, live checkout/wallet/bridge internals, source-learning induction/activation, payment-justification guard implementation, deterministic CSV verification, payment cryptography and Rehan's gold-label methodology. Route those to Jeff or Nikita as identified above.

## Shared-file routing: exceptions take precedence over directories

“Primary quiz owner” below means implementation-depth questions, not a reassignment of engineering ownership.

| File or area | Primary quiz owner | Boundary / exception |
| --- | --- | --- |
| `backend/app/agents/dataset.py` | Jeff | Nikita supplied initial migration; later consent/interpretation internals are Jeff |
| `backend/app/agents/compiler.py`, `backend/app/catalog/verification.py`, `backend/app/datasets.py` | Nikita | Jeff owns semantic policy and can take a shared semantic-contract question |
| `backend/app/agents/gateway.py` | Split | Nikita: base gateway/harness; Jeff: dataset interpretation, semantic/model integration; inspect symbol history |
| `backend/app/agents/budget.py`, `bounded_client.py` | Jeff | Operational model infrastructure is generally Nikita-owned, but these implementations are Jeff's |
| `backend/app/orders/catalog.py` | Nikita | Jeff: prepared-source integration and completed-semantic-attempt recovery hooks |
| `backend/app/orders/dataset.py` | Split | Nikita: production, verification/lifecycle/remedy plumbing; Jeff: semantic recovery/provenance/effective assessment; Lucas: narrow Human copy |
| `backend/app/investigation/dataset.py` | Jeff | Nikita: initial deterministic boundaries and later specific geography fixes; inspect targeted function |
| `backend/app/orders/dataset_evidence.py`, `orders/runs.py`, `storage/runs.py` | Nikita | Jeff's semantics feed these interfaces; Lucas's copy edits do not confer runtime authorship |
| `backend/app/runtime/broker.py`, `runtime/dispute_assessment.py`, `runtime/jobflow*` | Jeff | Retained runtime, not Nikita's new aggregate/payment worker |
| `backend/app/payments/jobflow.py` | Jeff | Simulated compatibility implementation; most other payment internals are Nikita |
| `backend/app/payments/base*`, `journal.py`, `executor.py`, `attempt.py`, `catalog.py`; `spikes/payments/` | Nikita | Learning/model-usage accounting is a separate Jeff component |
| `backend/app/learning/`, source preparation/knowledge, `api/source_learning.py` | Jeff | Nikita owns the surrounding commercial acceptance/payment gates |
| `backend/app/orders/payment_justification.py`, `contracts/payment_justification.py`, money formatting | Jeff | Existing financial execution/gates being inspected are Nikita's |
| `frontend/components/workbench.tsx`, invoice components, `lib/use-workbench.ts` | Jeff | Historical authored work; Lucas is ongoing frontend owner |
| `frontend/components/run/canvas.tsx`, `customer.tsx`, `guide.tsx`, `inspector.tsx`, `warehouse.tsx`, `run-app.tsx` | Lucas | Nikita contributed primary integration/layout fixes; Rehan contributed mascot; inspect the mechanism |
| `frontend/lib/run/broker/`, `source.ts`, recorded `scenario.ts` | Lucas | Backend broker semantics are Jeff; primary live transport is Nikita |
| `frontend/lib/run/fold.ts`, `contract.ts` | Split | Lucas: canvas model; Nikita: live/payment projection; Jeff: answered-scope/financial display fixes |
| `frontend/lib/run/live.ts`, `checkout.ts`, `wallet.ts`, buyer settings, live-order hooks | Nikita | Lucas owns display/design integration, not original checkout mechanics |
| `frontend/components/run/live-run.tsx`, `live-customer.tsx`, `live-order.tsx`, `conversation.tsx` | Mostly Nikita | Shared visual language is Lucas; embedded learning/financial panels are Jeff |
| `frontend/lib/live-bridge.ts`, `hosted-demo.ts` | Nikita | Jeff added narrowly scoped source-learning/payment-justification routes |
| `frontend/components/run/source-learning.tsx`, `payment-justification.tsx`, `frontend/lib/money.ts` | Jeff | Lucas retains design responsibility; Nikita made layout/integration changes |
| `frontend/app/run.css`, `icons.tsx`, `orb.tsx` | Split | Lucas main visual system; Nikita live/layout work; Rehan groundhog contribution |
| Generated DTOs, `docs/openapi.json`, shared contracts, `main.py` | No whole-file owner for quizzes | Trace the specific semantic contract or integration change; do not quiz on generated trivia |
| `evals/aggregate/`, `tools/aggregate_eval.py` | Nikita | Explicit delegated evaluator infrastructure; not ownership of independent gold |
| Source-learning/model qualification and `tools/audit_*journey.py` | Jeff | Preserve developer-regression versus independent-evaluation distinction |
| Rehan's dispute eval/holdout and independent expectations | Excluded | Do not redistribute his contribution among the three names |

## Judge claims: evidence level and known limitations

- **Implemented:** inspectable state machine, immutable contracts, byte verifier, grounded investigation, controlled source knowledge, Base transport and durable payment execution. Code capability does not establish that a specific deployment exercised it.
- **Reported real-model evidence:** [final qualification](HYPHENATE_FINAL_QUALIFICATION.md) and its [sanitized evidence index](evidence/hyphenate-final-20261024.json) preserve small real-Claude cohorts and learning/mock-settlement journeys. These are historical, revision-bound reports; no new paid calls or full test suite were run for this ownership document.
- **Testnet nuance:** the early [payment spike](PAYMENT_SPIKE.md) says no transactions had been observed at that checkpoint. Later [funding-delay](reviews/funding-delay-20261024.md) and [capture-delay](reviews/capture-delay-20261024.md) reports describe persisted application observations of Base Sepolia funding/capture. Say “reported application-observed testnet activity,” not “never ran on-chain,” and not “this combined learning/model workflow was independently verified on-chain.” This audit did not reverify private receipts or query RPC.
- **Latency nuance:** those reports observed delayed application confirmation despite ample chain confirmations. Later scheduling code is implemented; do not promise a measured post-fix latency without a corresponding run.
- **Quality nuance:** mandatory byte checks do not prove every natural-language interpretation correct. Blind model review is not independent human evaluation. Retain the disclosed compound-claim over-escalation and prior failed cohorts; do not advertise universal dispute accuracy.
- **Learning nuance:** source conventions are explicitly governed, simulated-owner knowledge. Production identity, tenant isolation, broad source authority, measured labor savings and independent human holdout accuracy remain outside the demonstrated claim.
- **Finance nuance:** direct Base Commerce Payments is not full x402 compliance. No extra verification fee, partial capture, production accounting integration or post-capture refund implementation is established. The app's operator remains trusted to apply accepted policy.
- **UI nuance:** scripted/recorded rehearsal and real persisted executions are distinct. Saved real executions are useful evidence but are not fresh onstage inference. Mock payment history stays mock even when actual models ran.

For rehearsal phrasing and the shared demo sequence, see [judge defense](HYPHENATE_JUDGE_DEFENSE.md). Its whole-product questions can be split across these owners rather than grading each person on all subsystems.

## Updating this reference

After new commits, refresh refs and inspect changes since the baseline, including all relevant branches. Recheck current policy and route wiring. Update owner topics only where implementation evidence supports it; an integration merge or generated-client update is insufficient by itself. Keep the old evidence revision alongside later proof. Do not inspect secrets, mutate live state, run paid qualification or send transactions to prepare quiz questions.

Useful read-only checks:

```sh
git status --short
git log --all --reverse --format='%h | %aN | %s'
git log --follow -- path/to/file
git show COMMIT -- path/to/file
git blame HEAD -- path/to/file
git merge-base --is-ancestor COMMIT HEAD
```

## Complete reachable commit index

This appendix is provenance, not a question bank. `HEAD` means the commit is an ancestor of the audited checkout; it does not mean every old behavior survives. `branch` means reachable elsewhere but not by that exact hash from HEAD; imported/squashed equivalents are explained above. `stash` means local checkpoint metadata, not shipped work. `merge` credits integration only unless an inspected resolution establishes an additional contribution. Entries are grouped by author identity for completeness; the substantive ownership split is in sections 1–3 and the shared-file table.


### Jeff: 113 reachable commits

| Commit | Reachability | Kind | Recorded subject |
| --- | --- | --- | --- |
| `b92b628` | branch | commit | Define additive jobflow contracts and integration boundary |
| `d3f85f4` | branch | commit | Add bounded PDF extraction and synthetic artifact dependencies |
| `cc34286` | branch | commit | Implement scoped evidence investigation with exact citations and authority guards |
| `c4359c2` | branch | commit | Validate actual PDF evidence and record implementation boundaries |
| `fd71b59` | branch | commit | Preserve precise JSON-pointer and CSV-cell evidence locators |
| `fd89f8c` | branch | commit | Bound unresolved follow-ups and preserve question identity on resume |
| `1d77ae4` | branch | commit | Preserve no-remedy outcome for already correct disputed delivery |
| `dfcc346` | branch | commit | Implement V4 jobflow workbench frontend |
| `a83fd64` | branch | commit | Align workbench types with current investigator and add browser acceptance tooling |
| `fc9fb63` | branch | commit | Implement durable simulated jobflow runtime and guarded API |
| `0b67aa2` | branch | commit | Connect investigator and jobflow with independent scope actions and exact evidence guards |
| `178becd` | branch | commit | Integrate jobflow with v0.2 base authority and separately authorized change orders |
| `39538c0` | HEAD + main | commit | Add integrated jobflow MVP |
| `4df1dab` | branch | commit | Start broker workflow extension |
| `efdb161` | branch | commit | Fix bound question delivery and exact answer resume |
| `8bcdc35` | branch | commit | Add broker review workflow |
| `65cf3e8` | branch | commit | Add V5 broker acceptance regressions (known red) |
| `88459e8` | branch | commit | Add bounded improvement loop |
| `fd160ea` | branch | commit | Record results handoff |
| `835d7f1` | branch | commit | Preserve merged profiles |
| `49a4e82` | branch | commit | Add broker review and improvement workflow |
| `5c8dc72` | HEAD + main | commit | Add broker review and improvement workflow |
| `f388fe3` | branch | commit | Integrate catalog adaptation with dollar-bounded Claude calls and live canvas |
| `0b1127f` | branch | commit | Complete V6 browser controls, independent results and reproducible handoff |
| `db7aab8` | HEAD + main | commit | Add guarded source-bound broker dispute assessment behind default-off flag |
| `4b12988` | HEAD + main | merge | Integrate primary aggregate brokerage main into preserved dispute feature |
| `de53450` | HEAD + main | commit | Fix R3 category polarity and R4 question-bound cohort corrections |
| `d2b6ba1` | HEAD + main | commit | Add guarded primary dataset semantic assessment with durable provenance |
| `5946378` | HEAD + main | commit | Validate equivalent frozen authority proof without regrading prior cohort |
| `ef8c99a` | HEAD + main | commit | Finish bound compiler recovery and preserve primary qualification evidence |
| `db3bafd` | HEAD + main | commit | Record final primary verification, costs and owner handoff |
| `f471718` | HEAD + main | commit | Note Lucas upstream UI merge without changing tested delivery |
| `e774495` | HEAD + main | merge | Integrate completed semantic and dispute backend onto current main |
| `706f41e` | HEAD + main | commit | Fix aggregate intake consent loops and wire bounded Claude interpretation |
| `37a8bf1` | HEAD + main | merge | Preserve latest frontend integration and demo-route ownership guidance |
| `849e98a` | HEAD + main | commit | Record final integration evidence and frontend handoff |
| `82bc5ba` | HEAD + main | commit | Add bounded real intake and dispute qualification cohort |
| `1b7ed75` | HEAD + main | commit | Separate taxonomy authority from scope and validate scope-first claims |
| `b9476d9` | HEAD + main | commit | Bind cohort confirmations to explicit supported offers |
| `e822bde` | HEAD + main | commit | Publish real Claude qualification evidence and preserved negative results |
| `add00af` | HEAD + main | commit | Make published evidence hashes portable across Windows and Git |
| `3a15bd8` | HEAD + main | merge | Integrate current main while preserving qualified backend and teammate changes |
| `e5ab269` | HEAD + main | commit | Document integrated qualification and inherited Windows payment failures |
| `19bcf8e` | HEAD + main | merge | Integrate current main evaluator without changing runtime semantics |
| `44de0fe` | HEAD + main | commit | Reproduce Greptile cohort consent, proposal identity, and cutoff findings |
| `43cb18c` | HEAD + main | commit | Fix cohort consent, proposal model identity, and guarded dispatch cutoff races |
| `e60aa6f` | HEAD + main | commit | Record P1 reproductions, fixes, and integrated verification evidence |
| `30ddd34` | HEAD + main | commit | Reproduce amendment fulfillment and lost acknowledged assessment work |
| `01429b7` | HEAD + main | merge | Integrate Lucas customer guide and dispute-assessed canvas mapping |
| `36e9eb8` | HEAD + main | commit | Persist acknowledged dispute work and fulfill verified accepted amendments |
| `ba79817` | HEAD + main | commit | Preserve completed deterministic effects during legacy receipt recovery |
| `e45ddde` | HEAD + main | merge | Merge remote-tracking branch 'origin/main' into feature/aggregate-intake-integration-20261024 |
| `9bff90c` | HEAD + main | commit | Document scope fulfillment and durable assessment recovery evidence |
| `2146cde` | HEAD + main | commit | Reproduce numeric qualifiers being erased from dataset consent |
| `3f90ad5` | HEAD + main | commit | Retain numeric and symbolic qualifiers when checking dataset consent |
| `5fc7b4d` | HEAD + main | commit | Record fresh-review numeric consent fix and regression evidence |
| `e41dd03` | HEAD + main | merge | Merge remote-tracking branch 'origin/main' into feature/aggregate-intake-integration-20261024 |
| `d007157` | HEAD + main | commit | Record intact Lucas PR21 integration and frontend checks |
| `c7f82dd` | HEAD + main | commit | Reproduce completed dataset assessment loss after lease reclaim |
| `7b97c2b` | HEAD + main | commit | Recover completed dataset assessments across pure job lease reclaims |
| `a755c9f` | HEAD + main | commit | Document completed semantic recovery, stale guards and final regression results |
| `7de44d7` | HEAD + main | merge | Merge pull request #12 from redrum2k/feature/aggregate-intake-integration-20261024 |
| `bb7edc1` | HEAD + main | commit | Add source-scoped institutional procedures from resolved operational exceptions |
| `c1de7f3` | HEAD + main | commit | Fix source preparation replay and isolate per-request evidence |
| `6defeb7` | HEAD + main | commit | Preserve prepared source selection through clarification |
| `af1a0e8` | HEAD + main | merge | Merge pull request #24 from redrum2k/feature/source-procedures-20261024 |
| `75eb252` | HEAD + main | commit | Enable approved persistent source learning in the controlled local app |
| `35679a9` | HEAD + main | merge | Merge remote-tracking branch 'origin/main' into feature/live-source-learning-review-20261024 |
| `072a58b` | HEAD + main | commit | Guard stale prepared learning and commit owner corrections atomically |
| `447a8f1` | HEAD + main | commit | Address Greptile learning dependencies, qualification and review controls |
| `3da56a1` | HEAD + main | merge | Merge pull request #29 from redrum2k/feature/live-source-learning-review-20261024 |
| `c0aa7df` | HEAD + main | commit | Connect mock learning, grounded disputes and audited settlement end to end |
| `d7d776b` | HEAD + main | merge | Merge remote-tracking branch 'origin/main' into feature/llm-learning-qualified-20261024 |
| `1c50134` | HEAD + main | commit | Permit explicitly budgeted local learning and real-model qualification |
| `5614708` | HEAD + main | commit | Recover qualification from persisted assessment without repeated model calls |
| `e09a240` | HEAD + main | commit | Preserve real-model evidence and expose semantic integration failure |
| `cbcef40` | HEAD + main | merge | Merge remote-tracking branch 'origin/main' into feature/llm-learning-qualified-20261024 |
| `cd97bbf` | HEAD + main | commit | Reconcile raw Claude findings and record integrated verification results |
| `a08f1df` | HEAD + main | merge | Merge remote-tracking branch 'origin/main' into feature/llm-learning-qualified-20261024 |
| `60023de` | HEAD + main | commit | Ground novel semantic dispositions with a blind model evidence review |
| `2faf554` | HEAD + main | commit | Audit semantic review calls and recover replaced-finding observation |
| `ec959dc` | HEAD + main | commit | Retain repeated recovery evidence and reuse initial assessment after answers |
| `8ff5a30` | HEAD + main | commit | Freeze fresh uninterrupted end-to-end model qualification cases |
| `3322c82` | HEAD + main | commit | Preserve contractual meaning when reviewing multi-clause objections |
| `1245d58` | HEAD + main | commit | Repair incomplete semantic review once without retrying disagreements |
| `5263835` | HEAD + main | commit | Preserve full qualification history and audit final model settlement workflow |
| `01add58` | HEAD + main | merge | Merge remote-tracking branch 'origin/main' into feature/llm-learning-qualified-20261024 |
| `d8df050` | HEAD + main | commit | Finalize verified end-to-end Claude learning and settlement evidence |
| `a52c642` | HEAD + main | commit | Close accepted-source and downloaded-preview audit gaps |
| `368cb96` | HEAD + main | commit | Verify raw review judgments and reject repeated audit rows |
| `6ada9d5` | HEAD + main | commit | Preserve offline evaluator mismatch and record full-suite findings |
| `d59853f` | HEAD + main | merge | Merge pull request #37 from redrum2k/feature/judge-proof-order-to-cash-20261024 |
| `17d8e98` | HEAD + main | commit | Reject historical source and authority publication before installing stale bundles |
| `6a6fe2a` | HEAD + main | commit | Include named ZIP source and delivery cells in model investigation evidence |
| `6ceab8b` | HEAD + main | merge | Merge remote-tracking branch 'origin/main' into fix/hyphenate-historical-authority-20261024 |
| `1a26108` | HEAD + main | commit | Record Hyphenate release qualification and preserved no-go evidence |
| `76b1da5` | HEAD + main | commit | Honor explicit budget-only live-model authorization without resetting spend |
| `3da9be2` | HEAD + main | merge | Merge remote-tracking branch 'origin/main' into fix/hyphenate-historical-authority-20261024 |
| `71a1ead` | HEAD + main | commit | Preserve successful budget-only real-Claude integrated qualification |
| `c3422f7` | HEAD + main | commit | Expose recorded buyer complaints and effective investigation provenance in existing transcript |
| `97ed030` | HEAD + main | merge | Merge remote-tracking branch 'origin/main' into fix/hyphenate-historical-authority-20261024 |
| `81c7ee1` | HEAD + main | commit | Fix Greptile launcher portability finding with explicit private credential routing |
| `be8fd48` | HEAD + main | commit | Document visible live findings and preserve fresh reviewer disagreement |
| `49ec1ee` | HEAD + main | merge | Merge remote-tracking branch 'origin/main' into fix/hyphenate-historical-authority-20261024 |
| `a44b411` | HEAD + main | commit | Complete bounded release qualification with full-suite baseline comparison |
| `a57e23e` | HEAD + main | merge | Merge pull request #46 from redrum2k/fix/hyphenate-historical-authority-20261024 |
| `0bb253a` | HEAD + main | commit | Fix scope inquiries and fractional prices; expose persisted financial evidence |
| `f80bc3a` | HEAD + main | commit | Support budget-bound live qualification and post-restart objections |
| `b031cc1` | HEAD + main | commit | Audit real model evidence and clarify terminal financial presentation |
| `d754c25` | HEAD + main | merge | Integrate latest main payment scheduling and hosted-demo safeguards |
| `c2ce32b` | HEAD + main | commit | Finalize live-AI learning qualification and exact fractional canvas display |
| `82dd93a` | HEAD + main | commit | Bind audit responses to dispatched requests and retain unresolved findings |
| `301ffe5` | HEAD + main | merge | Merge pull request #53 from redrum2k/feature/hyphenate-final-20261024 |

### Nikita: 56 reachable commits

| Commit | Reachability | Kind | Recorded subject |
| --- | --- | --- | --- |
| `6ac1810` | HEAD + main | commit | Initialize backend scaffold and team contracts |
| `06112e2` | HEAD + main | commit | Add invoice review workflow and versioned polling API |
| `0326ae6` | HEAD + main | commit | Freeze catalog API and mock payment frontend handoff |
| `53accd2` | HEAD + main | merge | Integrate catalog handoff with preserved invoice jobflow |
| `ac385a1` | HEAD + main | merge | Merge catalog payment handoff and preserve invoice jobflow (#2) |
| `1483046` | HEAD + main | commit | Connect catalog settlement to durable payment execution |
| `3a7b754` | HEAD + main | commit | Add durable automatic catalog dispatch and isolated runtime lanes |
| `a23f999` | HEAD + main | commit | Implement offline-validated Base transport and payment laboratory |
| `3693efa` | HEAD + main | merge | Merge completed catalog runtime into backend integration |
| `f72944a` | HEAD + main | merge | Merge completed Base transport into backend integration |
| `22f52db` | HEAD + main | merge | Merge completed catalog settlement into backend integration |
| `39dd586` | HEAD + main | commit | Integrate and validate automatic catalog runtime and Base settlement |
| `41ecf61` | HEAD + main | merge | Merge current main broker workflow and canvas with integrated backend |
| `f8a929a` | HEAD + main | commit | Prepare isolated Base payment readiness and recovery evidence |
| `1956f18` | HEAD + main | commit | Migrate primary brokerage domain and connect durable live canvas |
| `6a714cf` | HEAD + main | merge | Integrate completed payment readiness workstream |
| `3519453` | HEAD + main | commit | Validate combined brokerage workflow and document production browser evidence |
| `692f500` | HEAD + main | commit | Close runtime review gaps and document remaining compiler blockers |
| `086b5ba` | HEAD + main | commit | Publish compiler handoff and polling recovery follow-up |
| `845b7c5` | HEAD + main | commit | Keep run polling and complaints available when preview artifacts fail |
| `799a6d9` | HEAD + main | merge | Merge review remediation and preserve the legacy broker demo |
| `62fe035` | HEAD + main | merge | Merge completed 08b polling and complaint recovery |
| `9622fe0` | HEAD + main | commit | Renew payment-worker leases within bounded attempts |
| `593e02f` | HEAD + main | commit | Bound payment HTTP calls and discard late buyer authorizations |
| `384c21e` | HEAD + main | commit | Checkpoint local route schema and review handoff fixes |
| `e2307e4` | HEAD + main | merge | Merge latest main route guidance with local frontend fixes |
| `4a24c9f` | HEAD + main | merge | Merge reviewed payment lease renewal and bounded attempts |
| `676b4e2` | HEAD + main | commit | Record reviewed frontend payment integration and current demo routes |
| `331a614` | HEAD + main | commit | Record newly published unreviewed intake branch at final fetch |
| `ade5d8e` | HEAD + main | commit | Add isolated aggregate evaluation and independent evidence reports |
| `ee8fd85` | HEAD + main | commit | Classify evaluator startup failures without exposing exception text |
| `991b5b9` | HEAD + main | commit | Record aggregate evaluator validation and remaining review dependencies |
| `fd3e337` | HEAD + main | commit | Preserve evaluation checkpoints when later audits fail |
| `947140e` | HEAD + main | merge | Merge pull request #18 from redrum2k/codex/aggregate-evaluation |
| `c57b04c` | branch | merge | Merge remote-tracking branch 'origin/lucas/customer-guide' into codex/pr-review-integration |
| `6796373` | HEAD + main | merge | Merge pull request #9 from redrum2k/lucas/orb-detective |
| `31f6da6` | branch | commit | Fix customer review layout, orb flight, and recorded coverage cues |
| `f1a9011` | HEAD + main | commit | Fix customer review layout, orb flight, and recorded coverage cues |
| `11d4a32` | branch | merge | Merge remote-tracking branch 'origin/feature/aggregate-intake-integration-20261024' into codex/pr-review-integration |
| `7c4dde1` | HEAD + main | merge | Merge pull request #14 from redrum2k/lucas/customer-guide |
| `7532106` | HEAD + main | merge | Merge remote-tracking branch 'origin/feature/aggregate-intake-integration-20261024' into codex/local-claude-live |
| `800c985` | HEAD + main | merge | Merge remote-tracking branch 'origin/main' into codex/local-claude-live |
| `1c736f8` | HEAD + main | merge | Merge remote-tracking branch 'origin/main' into codex/local-claude-live |
| `ccedace` | HEAD + main | merge | Merge remote-tracking branch 'origin/main' into codex/local-claude-live |
| `a66c3cf` | HEAD + main | commit | Unify live checkout and complaint review |
| `e2b6483` | HEAD + main | merge | Merge branch 'codex/local-claude-live' into main |
| `4564064` | HEAD + main | merge | Merge origin/main into live demo branch |
| `8d47015` | HEAD + main | merge | Merge remote-tracking branch 'origin/main' |
| `6303841` | HEAD + main | commit | Preserve implementation prompts and integration runbooks |
| `de17250` | HEAD + main | merge | Merge branch 'codex/local-claude-live' |
| `99a5bfe` | HEAD + main | commit | Prepare password-protected Railway demo and integrate workflow fixes |
| `95d3281` | HEAD + main | commit | Allow public hosted demos with verified mock payments |
| `0894be8` | stash | checkpoint | untracked files on codex/ui-integration-20261024: 99a5bfe Prepare password-protected Railway demo and integrate workflow fixes |
| `19522ae` | stash | checkpoint | index on codex/ui-integration-20261024: 99a5bfe Prepare password-protected Railway demo and integrate workflow fixes |
| `bf11cbc` | stash | checkpoint | On codex/ui-integration-20261024: pre-push-ui-integration-20261024 |
| `c0a1147` | HEAD only; not origin/main | commit | Polish customer UI and human-review handoff |

### Lucas: 99 reachable commits

| Commit | Reachability | Kind | Recorded subject |
| --- | --- | --- | --- |
| `90d14ef` | HEAD + main | commit | Add the Datum run canvas to the frontend |
| `391ed11` | HEAD + main | commit | Rebuild the run canvas to match preview-v2 |
| `b4dc717` | HEAD + main | commit | Pressure-test the run canvas and fix what it found |
| `46f6c07` | HEAD + main | merge | Merge pull request #3 from redrum2k/lucas/run-canvas |
| `bd7e8d1` | HEAD + main | commit | Wire the run canvas to the broker backend |
| `c2f5619` | HEAD + main | merge | Merge pull request #5 from redrum2k/lucas/broker-live |
| `7c5ccbc` | HEAD + main | commit | Finish the grey and red cases live through a clarification |
| `05a32cd` | HEAD + main | commit | Polish the run screen: pan, investigate and capture beats, quieter chrome |
| `0189de6` | HEAD + main | commit | Customer view with Acme's decisions; the demo is one order plus act two |
| `af35856` | HEAD + main | merge | Merge main: keep the canvas at /, mount the aggregate intake at /live |
| `5a68ea1` | HEAD + main | merge | Merge pull request #6 from redrum2k/lucas/broker-live |
| `339c602` | HEAD + main | commit | Live interview reads as a conversation; Replay reopens the first step |
| `8ab1e7f` | HEAD + main | merge | Merge pull request #7 from redrum2k/lucas/live-polish |
| `ebf9086` | HEAD + main | commit | Customer view opens on Acme's decision |
| `63ac21f` | HEAD + main | merge | Merge pull request #8 from redrum2k/lucas/customer-scroll |
| `c9d662c` | HEAD + main | commit | Dress the orb as a detective: deerstalker and round glasses |
| `e408c0c` | HEAD + main | commit | Rename the controller persona Maya to Human across the frontend |
| `0080aa8` | HEAD + main | commit | Customer view keeps the decision in view; the chat follows itself |
| `7c906d2` | HEAD + main | commit | Rename Maya to Human in backend run text and policy docs |
| `580fc33` | HEAD + main | commit | Regenerate API contracts for Starlette's 422 wording |
| `31ad60b` | HEAD + main | merge | Merge pull request #11 from redrum2k/lucas/maya-to-human |
| `c7b9ddf` | HEAD + main | merge | Merge remote-tracking branch 'origin/main' into lucas/customer-focus |
| `6c3a397` | HEAD + main | commit | After Acme's move, the view returns to the agent at work |
| `dbf9006` | HEAD + main | merge | Merge pull request #10 from redrum2k/lucas/customer-focus |
| `aa1bc80` | HEAD + main | merge | Merge remote-tracking branch 'origin/main' into lucas/orb-detective |
| `3fb6a4b` | HEAD + main | commit | AGENTS.md: the demo route is the canvas at /, Nikita's intake is at /live |
| `04756e1` | HEAD + main | merge | Merge pull request #13 from redrum2k/lucas/agents-note |
| `67c7d58` | HEAD + main | commit | Customer view: the orb guides the buyer, checks sit beside the data, the window counts down |
| `3e6d865` | HEAD + main | commit | Live contract keeps the interview's line order; age ranges read with a dash |
| `16d33c1` | HEAD + main | merge | Merge pull request #15 from redrum2k/lucas/contract-order |
| `a150b14` | HEAD + main | commit | Test: look the geography line up by id, not by its old position |
| `4aac0db` | HEAD + main | merge | Merge pull request #16 from redrum2k/lucas/contract-order-test |
| `a654dbd` | HEAD + main | commit | Acme answers the intake every 0.5s instead of 0.84s |
| `b177d53` | HEAD + main | merge | Merge pull request #17 from redrum2k/lucas/interview-pace |
| `3802d49` | HEAD + main | commit | Drop the review countdown from the delivery card |
| `9668324` | HEAD + main | commit | Smooth the hand-off between Customer view and Run |
| `2463d24` | HEAD + main | commit | Deliver all 27 San Francisco ZIPs, scrolling in place |
| `c06fa5d` | HEAD + main | commit | Map Jeff's dispute.assessed: who decided, with quoted references as evidence |
| `f5cc8ed` | HEAD + main | merge | Merge pull request #19 from redrum2k/lucas/dispute-assessed |
| `49fb413` | HEAD + main | commit | The detective inspects an objection with a magnifier in hand |
| `d0417a4` | HEAD + main | commit | Customer view: our agent talks from the left, the orb beside it, and the interview stays open |
| `3d69b92` | HEAD + main | merge | Merge pull request #20 from redrum2k/lucas/customer-guide |
| `f52535f` | HEAD + main | commit | Fix the objection flow from Lucas's recording |
| `c916989` | HEAD + main | commit | Keep the page from scrolling under the customer view |
| `34aa770` | HEAD + main | merge | Merge pull request #21 from redrum2k/lucas/objection-fixes |
| `ae527e6` | HEAD + main | commit | Say plainly what the grey area is, and that the human's call is on record |
| `55d62bc` | HEAD + main | commit | Canvas follows at 1.15x minimum |
| `3445e19` | HEAD + main | merge | Merge pull request #23 from redrum2k/lucas/canvas-zoom |
| `c63c775` | HEAD + main | commit | The dispute beat on the canvas, and the path reveals itself step by step |
| `89d8f4b` | HEAD + main | merge | Merge pull request #25 from redrum2k/lucas/dispute-beat |
| `6a60dfb` | HEAD + main | commit | The thought stays with the step it was had at |
| `c7e2c70` | HEAD + main | merge | Merge pull request #26 from redrum2k/lucas/thought-at-node |
| `baeedb3` | HEAD + main | merge | Merge pull request #22 from redrum2k/lucas/grey-area-copy |
| `130d9f3` | HEAD + main | commit | A remembering thought on the learned replay; a longer beat for the walk to the source |
| `557bfba` | HEAD + main | merge | Merge pull request #27 from redrum2k/lucas/walk-beat |
| `18763ae` | HEAD + main | commit | The source is a small database with the orb's eyes; its checks read as queries |
| `3ddf895` | HEAD + main | merge | Merge pull request #28 from redrum2k/lucas/warehouse |
| `4aaf720` | HEAD + main | commit | The live feed takes a poll's burst one event at a time |
| `066d2f2` | HEAD + main | merge | Merge pull request #30 from redrum2k/lucas/live-drip |
| `8b7d914` | HEAD + main | commit | The customer is Summit Fitness, with a summit mark instead of initials |
| `100a0e1` | HEAD + main | merge | Merge pull request #31 from redrum2k/lucas/summit |
| `ef40191` | HEAD + main | commit | The second case is called Escalation |
| `275c127` | HEAD + main | merge | Merge pull request #32 from redrum2k/lucas/escalation-label |
| `b18e835` | HEAD + main | commit | The thought is smaller and leads with the point |
| `8b3b216` | HEAD + main | merge | Merge pull request #33 from redrum2k/lucas/quiet-thought |
| `37d66e1` | HEAD + main | commit | One visual thing at a time after an objection |
| `7ab7002` | HEAD + main | merge | Merge pull request #34 from redrum2k/lucas/one-thing-at-a-time |
| `6c3a57c` | HEAD + main | commit | A live step's own flags win; the recorded investigations keep their panel closed |
| `d0a49e4` | HEAD + main | merge | Merge pull request #35 from redrum2k/lucas/live-step-flags |
| `24ed18c` | HEAD + main | commit | The word mock leaves the screen; one plain disclosure where the money lands |
| `7a3aa75` | HEAD + main | merge | Merge pull request #36 from redrum2k/lucas/no-mock-word |
| `be76347` | HEAD + main | commit | No thought bubble; a reopened review keeps its state |
| `0722104` | HEAD + main | merge | Merge pull request #39 from redrum2k/lucas/no-thought |
| `a211741` | HEAD + main | commit | Call the broker Groundhog, and make the orb a little groundhog |
| `53b5086` | HEAD + main | commit | One clean objection flow in the customer view, and a quieter source check |
| `ab8545c` | HEAD + main | merge | Merge pull request #40 from redrum2k/lucas/groundhog-objection |
| `ed6390b` | HEAD + main | commit | HANDOFF: the canvas demo is at /demo |
| `30c6abc` | HEAD + main | merge | Merge pull request #41 from redrum2k/lucas/demo-route-note |
| `4f3d08f` | HEAD + main | commit | The live feed narrates itself; no recorded captions on a live run |
| `96be3fc` | HEAD + main | merge | Merge pull request #42 from redrum2k/lucas/live-narration |
| `5f8a96c` | HEAD + main | merge | Rehan's groundhog is the mascot, in brown; the header mark wears the same brown |
| `d03918f` | HEAD + main | commit | Name the data broker: Groundhog is Bayline Data's agent, not the seller |
| `5a8e6e8` | HEAD + main | merge | Merge pull request #43 from redrum2k/lucas/broker-name |
| `4bc8780` | HEAD + main | merge | Merge pull request #44 from redrum2k/lucas/rehan-groundhog |
| `0494da8` | HEAD + main | commit | Back to the blue groundhog |
| `1408b56` | HEAD + main | merge | Merge pull request #45 from redrum2k/lucas/blue-groundhog |
| `a491243` | HEAD + main | commit | Revert "Merge pull request #45 from redrum2k/lucas/blue-groundhog" |
| `8d180af` | HEAD + main | commit | The groundhog tunnels between steps: sink, slide under the cards, climb out |
| `e2f5000` | HEAD + main | merge | Merge pull request #47 from redrum2k/lucas/groundhog-tunnel |
| `c697d09` | HEAD + main | commit | The burrow slides across with the groundhog down in it; a row change goes down first, never diagonal |
| `672e10d` | HEAD + main | merge | Merge pull request #48 from redrum2k/lucas/tunnel-hat |
| `69d3360` | HEAD + main | commit | The burrow never moves: it ducks all the way in, a beat under, then climbs out of a new hole |
| `c75e875` | HEAD + main | merge | Merge pull request #49 from redrum2k/lucas/tunnel-no-slide |
| `f12ad6a` | HEAD + main | commit | Customer view: the groundhog climbs out only after the view has stopped scrolling |
| `5782f69` | HEAD + main | merge | Merge pull request #50 from redrum2k/lucas/tunnel-after-scroll |
| `c991fd6` | HEAD + main | commit | The camera closes in on the current step; a burst of steps is one trip for the groundhog |
| `b490402` | HEAD + main | merge | Merge pull request #51 from redrum2k/lucas/camera-window |
| `1f31360` | HEAD + main | commit | No caption line under the canvas; the groundhog arrives under when the view comes back mid-run |
| `0c280db` | HEAD + main | merge | Merge pull request #52 from redrum2k/lucas/no-caption |

### Rehan — preserved credit, excluded from the three quiz pools: 7 reachable commits

| Commit | Reachability | Kind | Recorded subject |
| --- | --- | --- | --- |
| `737cd5c` | branch | commit | Add leakage-safe dispute dataset evaluation and sealed aggregate holdout |
| `c08b663` | HEAD + main | commit | Replace the blue orb mascot with a detective groundhog |
| `a945262` | HEAD + main | commit | Make the groundhog blue |
| `1438e38` | branch | commit | Revert "Make the groundhog blue" |
| `36d1aa3` | branch | commit | Dig a pebble trail between steps |
| `4020406` | branch | commit | Bury the whole groundhog, and undig the trail pebble by pebble |
| `d90dcb1` | branch | commit | Drop the dig trail, keep the tunnel |
