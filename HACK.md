# CalHacks: aggregate data brokerage, from request to cash

Primary product policy: **aggregate-brokerage-v1**, October 24, 2026.
Deadline: October 25, 2026, 9 a.m. America/Los_Angeles. Tracks: Hyphenate,
Coinbase, Microsoft. Sponsor eligibility remains unverified.

## Product

Bayline Data delivers a contract-checked synthetic aggregate dataset to Summit Fitness:
San Francisco adults aged 25–34 interested in fitness, grouped by ZIP. Intake,
clarification, provider quote, explicit acceptance, confirmed funding, production,
independent verification, customer review and settlement are separate transitions.
No personal records, live acquisition or marketplace is implemented.

Fitness is clarified as gym membership or fitness-app use, with standalone yoga
available only under explicitly agreed expanded scope. A cited category dispute
can be resolved, questioned or escalated; the UI does not pick its verdict.

The accepted dataset specification freezes geography, cohort age, category meaning,
population, unique-adult integer count unit, disjoint ZIP assumptions, exact sources,
authority records, coverage registry, schema and suppression. The independent
synthetic city registry specifies ZIP inclusion; postal ZIPs are not asserted to
match real city boundaries. Every expected key must occur once. Missing/unknown
counts block; suppressed counts are null with a distinct status. Released counts
must be at least 50. No exact suppressed counts are exposed. This is a demo contract
rule, not a general privacy guarantee.

The delivery is immutable CSV plus JSON preview/manifest. Independent checks reopen
actual source and delivered bytes. The eight mandatory requirements cover cohort,
category, geography, schema, coverage, suppression, provenance and artifact agreement.
PASS/FAIL/UNKNOWN/CONFLICT describe evidence; deterministic lifecycle gates control money.
No PDF generation or parsing belongs to the new happy path.

## Agreement and remedies

New quotes use server pricing `datumco-demo-pricing-v2`: base $1, separate Oakland
extension $0.50, separately offered yoga expansion $0.25, whole-specification
replacement $1. These are synthetic demo assumptions, not market prices. Previously
issued v1 quotes and accepted prices ($120/$60/$30/$120) stay unchanged. Yoga already
owed under the accepted definition cannot be billed again. Exact USD minor units
convert at the retained accepted 1 USD:1 USDC rule; $1 is 1000000 atomic USDC.
On-chain integers serialize as decimal strings.

Creation is not consent. Acceptance freezes parties, price, source hashes, policy,
payment terms and deadlines. Work starts only after confirmed funding or explicit
mock funding simulation. An operational retry is not the one free correction.

An established provider-output defect permits one durable free correction. A bad
source alone does not establish that fault. Another failed correction escalates.
Evidence answers increment evidence revision without inventing a delivery or
changing source editions. Substantive changes require a separate accepted child
agreement and confirmed parent void before child funding/work. Additional work
has a separate accepted price and authorization. Unsupported complaints incur no fee.

Human can approve an eligible proposed return of uncaptured funds, reject with a
reason, ask one bounded question or retain human review. Decisions cite evidence,
carry the exact observed binding and use trusted server credentials. They cannot
change accepted scope, activate a global rule or grant unconditional capture.
Jeff's improvement workflow remains scoped to its compatibility profile.

## Time and settlement

Review and dispute windows are 60 seconds each; answers never extend either.
For aggregate orders, a resolved unsupported complaint or answered scope question
permits another objection to the same delivery. Only one case may be unresolved
at a time. Each new case has its own 60-second dispute window; the delivery review
deadline stays fixed. Objections after review expiry or submitted settlement go
to human review and cannot cancel submitted payment. Catalog compatibility retains
its one-case-per-delivery rule.
Intake has two questions within 300 seconds. Investigation has at most two questions.
Source repair has two attempts and a 120-second episode bounded by existing clocks.
Capture authority expires one hour after quote preparation, not after delivery.

Scheduling policy `broker-budget-v1` reserves 135 seconds for fulfillment, a full
60-second review plus a dispute opened at its end, 135 seconds for an unused free
correction and another full review/dispute cycle. A positive 120-second transaction
margin covers latency, inclusion and skew conservatively; it is not a finality promise.
Dispatch, publication and correction require strictly sufficient remaining budget.
At the latest-safe-submission cutoff, new capture is forbidden. Insufficient budget
persists human review; it never shortens promised windows, extends signed terms or
invents returned funds. Late complaints remain recordable. Already submitted
operations reconcile after cutoff.

Capture requires current complete mandatory checks (revalidated against bytes),
no material blocker, unresolved dispute or pending consent, current acceptance or
undisputed review expiry, exact confirmed funding and terminal exclusivity.
Pending/submitted/uncertain payment is not completed settlement. Books reflect
existing idempotent payment bookings; data/compute cost and margin are unavailable.
No external accounting integration or invented balanced entries are shown live.

## Payment choice and compatibility

Payment rail: direct **Base Commerce Payments on Base Sepolia**, mock by default.
The user relayed judges' lightweight option-2 guidance. This is neither an award
promise nor full x402 compliance. No x402 facilitator or CDP server-wallet operator
was added. The x402 auth-capture EVM binding uses the same escrow stack; see the
[reference binding](https://github.com/x402-foundation/x402/blob/main/specs/schemes/auth-capture/scheme_auth_capture_evm.md).
The platform operator is trusted to apply the accepted rules. Void returns uncaptured
funds; post-capture refunds are not implemented. No live broadcast or paid model call
is authorized by this migration.

Historical catalog-v0.3 PDFs ($15/$5), invoice/jobflow, schema-3 snapshots and saved
responses remain under their accepted policies. `/api/broker` retains
broker-review-v0.3 with its 600-second review, 1,800-second case bound and USDSIM
mock authority; `/api/improvements` retains Jeff's scoped proposal/probe/approval/
activation/revoke loop. None is reinterpreted as a newly funded aggregate order.

The primary app at `/` and `/live` consumes persisted aggregate backend events from
intake onward. Customer view and Run share one order, with real funding consent and
server-gated admin controls. The retained broker demo/recorded rehearsal is at `/demo`.
The Next bridge requires trusted loopback demo mode or explicitly enabled,
password-protected hosted demo mode, with distinct server-only worker/reviewer
tokens. Hosted setup keeps the backend private; access is shared operator access,
not customer authentication or tenant isolation. See [Railway setup](docs/RAILWAY.md).
An explicitly enabled public demo can use real model calls with mock payments and
no browser password. The bridge checks the backend's mock-payment capabilities
before forwarding requests; legacy API proxies and controlled learning stay closed.
All visitors share demo access and its configured model budget.
See [workstream 06](docs/workstreams/06-data-broker.md) for implementation and evidence.

## Devpost video pitch — October 25

Groundhog connects a data broker's customer request, delivered data and evidence
behind permitted collection. The selected video follows one correct delivery:
SF request → fitness clarification → accepted agreement → simulated funding →
verified CSV/JSON → “Oakland should be in there” → cited defense of the agreed
SF scope → customer acceptance → confirmed mock collection.
The three-minute demo excludes source learning, reviewer-memory teaching and a
second-order improvement comparison. Those implementations remain background
work; reliable self-improvement is not a demonstrated outcome. Human review stays
available for uncertainty and Q&A without entering reusable guidance.
See [PITCH.md](PITCH.md) for narration, recording cues, a short version and Q&A.
Recording driver and narrator are unassigned; the driver plays Summit Fitness.
Technical follow-ups follow existing ownership: Jeff for evidence/interpretation,
Nikita for runtime/payment gates, Lucas for the frontend. This is a recording plan,
not a new execution result or authorization for paid calls or broadcasts.

## Historical competitive demo checkpoint — October 24, 13:22 Pacific

This records the build at that time. The product and route descriptions above
reflect the later integration and take precedence over this checkpoint.

Build phase (approximately 19 hours 38 minutes until submission). Weakest criterion:
visible end-to-end product coherence. The polished `/` canvas still uses retained
broker policy and scripted intake answers; `/live` owns funded aggregate intake.
Prioritize one demonstrated request-to-evidence-to-settlement journey, and qualify
Jeff's unmerged intake/dispute branch before presenting its behavior as integrated.

Honesty: synthetic sources, mock payments and scripted customer actions remain
explicit. Recorded playback is rehearsal, not live inference. Fresh local checks
passed 96 dataset tests with two known expected intake failures, 109 frontend tests,
and four offline acceptance scenarios. The injected missing-ZIP fault is disclosed.
Jeff's published real-Claude qualification is separate branch evidence, not proof
of a combined browser demo or observed on-chain settlement. No new paid model calls,
chain transactions or deployments were performed for this comparison.
