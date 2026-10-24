# Shared integration checkpoint — catalog v0.3 / payments v1

> Aggregate brokerage update (October 24): new default intake uses
> `aggregate-brokerage-v1`, funded CSV/JSON deliveries and the persisted `/runs` API.
> See [workstream 06](workstreams/06-data-broker.md) for current contracts, commands,
> compatibility boundaries and validation limitations. The catalog-specific details
> below remain historical compatibility guidance and do not set new dataset policy.


Deadline: Sunday, October 25, 2026, 9 a.m. America/Los_Angeles. Hold the first integration
checkpoint 90 minutes after the team starts its split; check the shared fixture at 30 minutes.
If necessary, reduce to one supplier PDF while preserving the end-to-end evidence repair path.

## Shared foundation

Run the repaired and unresolved commands in README.md. The fixture contains four synthetic
supplier PDFs, 12 products each. Supplier B has unreadable prices; a registered same-edition
copy can restore them. An unregistered readable copy cannot establish authority. Source and
actual delivery PDFs, JSON sidecar and exact citations are retained. Generator labels/expected
answers never enter runtime. Rehan reviews outcomes independently.

## First handoff

- Nikita: show persisted draft, clarification, server quote/acceptance, pending funding, explicit mock authorization, a leased durable job, pre-delivery evidence request and versioned repair.
  Restart the backend and demonstrate identical retries and stale-action 409 behavior.
- Jeff: inspect typed requirements/limitations, source parsing and product exclusions. Show
  actual-PDF verification and a cited amendment classification. Exercise the semantic
  interface offline; improve it autonomously within runtime/authority contracts.
- Lucas: start from [handoff](handoffs/lucas.md), generated API types and all-state mock API.
  Implement buyer typed-data signing/rejection, exact token/amount/receiver/operator/deadline
  display and pending/held/paid/returned/uncertain/expired states; then prompt and quote approval screens, progress/evidence request/upload flow,
  output/source PDF view and one clickable citation. Confirm page coordinate mapping and
  use server-driven 60-second timers. Add frontend setup/test commands when implemented.
- Rehan: independently label clean, defective, repaired, substantively amended and unresolved
  cases from the source/output PDFs. Record disagreements offline; verify actual sponsor rules.

Success: one complete request-to-repair-to-delivery journey produces a verified PDF and one
mock capture only after acceptance/review cutoff; the unresolved journey produces a useful
human-review table without capture. The frontend must show mock money and synthetic fixtures.

## Next checks

Demonstrate one free correction and repeated failure escalation; unsupported complaint with
zero fee; explicit additional-work acceptance creating one child job/authorization; two question
rounds; approval rejection; authorization expiry; reviewer release versus unimplemented refund.
Tests use an injected clock. Customer authentication, production isolation, live payments,
deployment and arbitrary PDF/OCR support are not part of the completed foundation.

No paid calls, broadcasts or deployment are authorized. Never route evaluator labels or
privileged worker/reviewer tokens through the browser or model context.


## Integrated payment handoff

The contract handoff retains API version 0.4.0 (`catalog-api-v1`, `catalog-payments-v1`), adds schema-4
accepted terms while preserving historical mock records, and supplies executable mock/fake
responses for all payment states. Base RPC/operator execution and automatic catalog dispatch are now integrated and validated
with synthetic RPC, clocks and PDFs; no observed testnet outcome is claimed. Mock terminal
actions complete atomically; Base bookings wait for confirmation. See workstreams/04-integration.md
and handoffs/lucas.md for the exact evidence and server bridge recipe.

The executable payment laboratory uses synthetic accepted terms and a fixture settlement
decision independent of Jeff's prompts or Lucas's UI. The later separately authorized
live proof is two 0.10 test-USDC payments: fund/restart/capture and fund/void. Main catalog
USD 15 pricing remains 15000000 atomic USDC under an explicit 1:1 demo conversion.

Jeff's version-bound findings/questions/recommendations never become wallet operations. Rehan
independently checks held provider balance, capture once, void return, provider non-authority
and uncertain-state disclosure, and verifies actual sponsor rules. Use Base Commerce Payments,
not x402. All four scoped handoffs are in docs/handoffs/.
