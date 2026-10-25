# CalHacks: aggregate data brokerage, from request to cash

Primary product policy: **aggregate-brokerage-v1**, October 24, 2026.
Deadline: October 25, 2026, 9 a.m. America/Los_Angeles. Tracks: Hyphenate,
Coinbase, Microsoft. Sponsor eligibility remains unverified.

## Product

DatumCo delivers a contract-checked synthetic aggregate dataset to AcmeFitness:
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
The Next bridge requires trusted loopback demo
mode and distinct server-only worker/reviewer tokens. Hosted access requires a
separate authentication/deployment design; no tenant isolation is claimed.
See [workstream 06](docs/workstreams/06-data-broker.md) for implementation and evidence.
