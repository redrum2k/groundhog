> Current route and validation update: see [frontend/payment integration](../reviews/frontend-payment-integration.md).
> `/` and `/live` are the funded aggregate app; `/demo` is the retained broker/rehearsal.
> The checkpoint below retains its historical results and route descriptions.
>
> October 24 live setup update: new quotes use `datumco-demo-pricing-v2` ($1 base,
> $0.50 Oakland, $0.25 yoga, $1 replacement), with exact 1 USD:1 test USDC conversion.
> Prior quotes, accepted snapshots and recorded evidence keep their original prices.
> On `/live`, open **Wallet settings** and connect the Buyer account on Base Sepolia
> once. Only its public address is saved in this browser and supplied to new quotes;
> payment signatures still require the account frozen into the accepted quote.
> Mock runs can still prepare quotes and simulate funding without a browser wallet.
> **Accept & pay $1.00** now accepts the agreement, prepares its exact authorization,
> requests one MetaMask signature and submits funding. Connect/unlock the Buyer in
> settings beforehand. Cancelling the signature leaves an accepted, unpaid order;
> the Funding panel offers a retry. Stable operation keys and a current-state read
> prevent a lost submission response from prompting another payment signature.
> Fulfillment still waits for confirmed funding. Mock checkout explicitly says simulate.
> **Customer view / Run** switch the same order. Customer view reuses the demo's chat,
> decision cards and guide orb; Run shows its canvas, evidence and server-gated admin
> controls. Successful payment submission or delivery acceptance hands off to Run.
> New customer decisions are signaled by a toolbar action. Drafted contract terms are
> separate from independent delivery checks; a completed agreement never fabricates PASS.
> These are trusted local demo views, not a public authentication or deployment change.
> Remote main through `baeedb3` merged at `1c736f8` without conflicts, preserving local
> pricing and wallet work. Validation: full backend suite, 141 frontend tests, Ruff lint/format, generated
> contracts, TypeScript and production build pass. The browser smoke connects a
> synthetic buyer in an isolated context, verifies the 1 USDC quote, completes mock
> checkout/settlement, switches views on the same order and checks saved-wallet recovery
> after reload. Checkout tests cover rejected signatures, stale/changed terms, abandoned
> signing, duplicate clicks and uncertain-response reconciliation. Desktop/mobile settings
> screenshots were inspected. The browser objection path reaches a backend decision,
> with no scripted verdict. React Doctor reports no new diagnostics; retained components
> have existing findings. These regression/browser tests used no paid calls or testnet transfers.
> A separately authorized local check through the primary `/` screen completed one real
> Claude Opus 5.5 intake call (1,596 input / 255 output tokens, $0.011484), reached `ready`,
> and opened the same request in Run without browser errors. The unchanged $10 ledger
> then recorded three completed calls totaling $0.037708. The restarted Base Sepolia
> adapter passed startup preflight. This check did not accept/fund an order or broadcast
> a transaction; it does not establish observed testnet settlement.
>
> October 24 intake recovery: a grounded Claude proposal containing multiple questions
> gets one separately reserved wording-repair call. Both calls count toward the existing
> four-call draft limit and shared paid-model budget; stale revisions and the original
> deadline are rechecked before repair. The repair can change only clarification wording,
> not the proposed scope or evidence quote. Original and repaired proposals are retained;
> invalid repair still stops without terms or consent. Expired/failed historical requests
> are not reset. The live customer heading now shares the Summit identity with the chat.
> A fresh primary-screen Claude check reached a single clarification in one call
> (1,601 input / 404 output tokens, $0.014484); no quote acceptance or payment occurred.
> The same budget ledger then held 14 completed calls totaling $0.211712 of $10.
>
> The live objection UI is one free-text complaint field. POST
> `/orders/{order_id}/complaints` accepts `text` plus the existing revision, binding and
> idempotency key. The server selects an accepted requirement/row as a routing hint;
> unclear or multi-topic text uses the artifact target. It preserves the complete text,
> records the dispute before investigation, and reuses the existing verification,
> review deadlines and settlement gates. Routing never establishes complaint validity
> or changed-scope consent. The explicit-target `/disputes` API remains compatible.
> Browser validation used the production frontend and an isolated mock-payment backend:
> one prompt submitted a missing-ZIP claim, and independent delivery checks rejected it
> because that ZIP was present. No paid call or testnet transaction was used for this check.

# 06 — Aggregate brokerage and live DatumCo canvas

Branch: `codex/data-broker-migration`. Local integration merge: `41ecf61`.
Backend baseline `39dd58602b3f8ac0a7906b4db4ddbbdb57b3d981`, reviewed main
`5c8dc726326bb9e3539cdb51e5aec221868223bc`, and Lucas merge
`46f6c07994bae4f1f0dec7c4c0d3d367b4e8f0d1` are ancestors. Main was verified
through the connected GitHub API after shell fetch failed DNS. No original feature
branch was merged twice. Work is isolated from the original checkout. Implementation
checkpoint: `1956f18`. Completed Prompt 7 commit `f8a929a` is integrated unchanged
by merge `6a714cf`; only its four owned files entered through that merge.

## Migration map

| Existing seam | Treatment |
| --- | --- |
| CatalogService, CatalogWorker, SQLite transactions, gateway | Reused. Dataset hooks select by frozen domain/policy; independent background lanes retained. |
| Base setup/injection, executor, journal, terminal exclusivity | Reused. Only narrow dataset capture revalidation and event hooks added. |
| Jeff's Frozen, SourcePin, TermProvenance, assessor interface | Reused; new dataset adapter accepts bounded cited semantics. |
| Jeff's data_product float rows/methodology PDFs | Compatibility only. New integer/null CSV/JSON models and independent coverage checks replace these for new runs. |
| Jeff's broker/deadlines and improvement recovery | Mounted with the integrated lifecycle; regression suites retained. |
| broker-review-v0.3 and improvement activation | Compatibility only. No new-run rule activation or financial adapter is claimed. |
| Lucas canvas, CSS, checklist, node layout | Reused. Default live intake, generated wire aliases and a data-driven panel added. |
| scenario/source/stub-store | Explicit recorded rehearsal. No prefix or ending selects a live outcome. |
| Catalog/invoice/broker/improvement clients | Retained; shared generation now includes runs and root OpenAPI. |

`contracts/dataset.py` defines domain `aggregate_dataset`, policy
`aggregate-brokerage-v1`, registry `sf-aggregate-v1` and pricing
`datumco-demo-pricing-v1`. Required checks are `dataset:{cohort,category,geography,
schema,coverage,suppression,provenance,artifact}`. Missing registry checks, model
PASS, stale binding or failed byte revalidation cannot authorize capture.

Sources, source authority and coverage are synthetic and registered automatically
by POST /runs. No external data is downloaded. Registry inclusion is explicit,
not a claim that ZIPs follow real city boundaries. The source has no exact value
for suppressed ZIP 94129. All released counts are nonnegative integers >=50;
suppressed/unknown rows have null counts. Unknown is blocking, not suppression.
Actual CSV and JSON preview must agree with the frozen source. Unsafe count-bearing
artifacts are withheld by the download endpoint even when retained internally as evidence.

Source deficiency does not consume correction. The offline harness deliberately
injects one missing-94110 producer output; independent checking rejects it and reserves
one correction. Runtime has no scenario/ending/evaluation labels. Yoga interpretation
uses the frozen definition/taxonomy through an injectable bounded assessor. Offline
excluded-yoga resolves unsupported, supported owed-yoga cannot be charged again,
and unresolved meaning asks at most two questions then escalates.

## API and events

Pydantic is authoritative (`contracts/runs.py`, `catalog.py`, `dataset.py`).
Generated TypeScript: `lib/runs.generated.ts`, `lib/catalog.generated.ts`, retained
jobflow/broker/improvement clients and `api.generated.ts`. No handwritten wire union.

```
POST /runs
Idempotency-Key: create-1
{"prompt":"SF adults 25–34 interested in fitness, counts by ZIP.","corpus_id":"sf-aggregate-v1"}
=> 201 {"id":"request-…","poll_after_ms":1000}

GET /runs/request-…/events?after=0&limit=100
=> {"events":[…],"next_after":3,"high_watermark":3,"caught_up":true,
    "poll_after_ms":1000,"server_time":"…","binding":null,
    "available_actions":[],"request":{…},"quote":null,"payment":null,
    "reviewClosesAt":null,"disputeClosesAt":null,"captureClosesAt":null,
    "latestSafeSubmissionAt":null}

POST /runs/request-…/decisions
Idempotency-Key: decision-1
X-Reviewer-Token: <server only>
{"action":"approve","reason":"Return uncaptured funds under the proposed remedy.",
 "evidence_ids":[],"binding":{"runId":"request-…","orderId":"order-…",
 "snapshotId":"snapshot-…","revision":9,"deliveryVersion":1,"evidenceVersion":2}}
=> {"ok":true,"decision_id":"decision-…"}
```

Events have exclusive strictly increasing per-run sequence numbers. `after=0` is
default; `limit` is 1–100. Empty polling returns the same cursor. Future cursors
return 409. Catch-up pages withhold actions until caught up. Metadata is read in the
same transaction as the high watermark; GET does not sweep deadlines or payments.
Responses use no-store and 1000 ms polling guidance. Browser reload replays from zero,
deduplicates events and resumes its persisted run identity.

SQLite `runs` and append-only `run_events` are additive. Each actual effect has a
unique stable key; order/payment changes and events commit in one transaction.
Writes are serialized by the existing repository. Restart and retries retain
sequences and effects. No snapshot-diff polling or timer script creates events.

Supported union: steps_planned; step_started/completed/waiting; message;
contract_line_drafted/approved; contract_approved; delivery_ready;
check_passed/failed/fixed; evidence_found; dispute_opened; verdict;
amendment_signed; controller_decided; rule_updated; payment_authorized/captured;
books_posted; state_changed. Schema support does not invent effects. Each step event
has attempt >=1. Correction re-enters produce with attempt 2; it may still publish
its first delivery. Evidence revision is independent of visible card count.

Main steps: clarify, paid, produce, review, captured. Dispute steps: investigate,
verdict, decide. “Paid” means held funding. New-run rule_updated is not emitted.
Amendment_signed requires durable acceptance of the identified child quote.
Books reference existing operation IDs; no fabricated expense or double-entry rows.

Additional operations:

- POST `/runs/{id}/offers`: trusted worker; `{binding,scope:"oakland"|"yoga"|"replacement"}`;
  returns frozen Quote. $60/$30/$120 respectively. Replacements renew the whole
  specification and depend on confirmed parent void. Child quotes cannot be repriced
  through the initial quote endpoint. Acceptance and funding remain separate.
- POST `/runs/{id}/answers`: `{binding,text,references:DatasetReference[]}`; bounded
  current request only, no deadline reset. Source repair requires resolving frozen refs.
- GET `/runs/{id}/evidence/{id}`: resolves a persisted message or exact dataset cell.
- Retained `/requests/{id}/answers`, `/requests/{id}/quotes`, `/quote-acceptance`,
  `/orders/{id}/funding-preparation`, `/funding-authorizations`, `/acceptance`,
  `/disputes`, `/artifacts/{artifact_id}` handle compatible commands. Worker compile
  remains `/internal/requests/{id}/compile`; automatic worker compilation also runs.
- Dataset PDF uploads and legacy additional-work DTOs are rejected; use run answers/offers.

Errors: 404 unknown run/reference; 422 invalid input with sanitized issues; 409
stale binding, incompatible state, future cursor or changed payload under a reused
key. Existing credential behavior is retained: 403 missing/wrong token, 503 when
not configured (no new 401 behavior). Exact retries return their saved acknowledgement
before freshness checks. Stale reviewer commands mutate nothing and are not auto-retried.

Reviewer actions are server-owned: approve an eligible proposed release only;
reject records a reason and retains review; ask persists one bounded actual question;
escalate retains review for Human/CFO. Actor/reason/citations/current binding are stored.
Neither an answer nor a reviewer decision can change scope or create money authority.

## Timing and signing

Base $120; review 60 s; dispute 60 s; intake 300 s/two questions; correction one;
repair 120 s/two attempts; accepted capture authority 3600 s from quote preparation.
`broker-budget-v1` reserves 135 s fulfillment + 120 s review/last-moment dispute +
135 s unused correction + 120 s fresh review/dispute, plus 120 s transaction margin.
Dispatch initially needs more than 630 s before expiry. Publication reserves the
remaining review/correction budget; correction reserves 255 s before the cutoff.
Equality fails. No promised window is shortened. Unresolved timing goes to human
review and an authorized return/reclaim path; expiry never proves return. Submitted
operations reconcile after cutoff. Historical policy clocks are unchanged.

Acceptance -> funding preparation -> exact buyer EIP-712 signature -> submission ->
confirmed held funds -> runnable work. Mock mode instead requires explicit simulation.
Wallet account/network changes and rejection stop submission. No private key or
signature is persisted in browser storage/logs. Worker/reviewer tokens are separate,
server-only and never NEXT_PUBLIC. The operator is trusted to apply contract rules.

Rail is direct Base Commerce Payments, not completed x402. The user relayed judges'
option-2 lightweight guidance; no award claim. The referenced x402 auth-capture EVM
binding uses Commerce Payments, but this application adds no facilitator or CDP
server wallet. Post-capture refunds remain unimplemented.

## Clean local acceptance

Use Node 24 (minimum 22.12) and uv. Do not use a private .env or existing DB.
From this worktree/repository root, in terminal A:

```sh
uv sync --locked --project backend
BROKER_DEMO_DIR=$(mktemp -d /private/tmp/datumco-local.XXXXXX)
printf '%s\n' "$BROKER_DEMO_DIR"
ORDER_DB_PATH="$BROKER_DEMO_DIR/orders.sqlite3" ARTIFACT_ROOT="$BROKER_DEMO_DIR/artifacts" \
INTERNAL_API_TOKEN=local-broker-worker REVIEWER_API_TOKEN=local-broker-reviewer \
ENABLE_PAID_MODELS=false PAYMENT_ADAPTER=mock \
uv run --locked --directory backend python -m uvicorn app.main:app --host 127.0.0.1 --port 8016
```

Terminal B, frontend directory (set PATH to your documented Node 24 installation):

```sh
npm ci
npm run generate:check
BACKEND_URL=http://127.0.0.1:8016 BROKER_BUILD_DIR=.next-broker-production npm run build
BROKER_BUILD_DIR=.next-broker-production \
BACKEND_URL=http://127.0.0.1:8016 BROKER_LOCAL_DEMO=1 \
INTERNAL_API_TOKEN=local-broker-worker REVIEWER_API_TOKEN=local-broker-reviewer \
npm run start -- --hostname 127.0.0.1 --port 3017
```

Open `http://127.0.0.1:3017/`. The isolated build directory also permits an
independent `npm run dev -- --port 3016` with the same bridge environment. Set BACKEND_URL at build time as well as startup because
the retained jobflow/broker/improvement rewrites are compiled during the build.
Create request, answer the gym/app clarification,
prepare quote, explicitly accept $120, open Funding, prepare funding, explicitly
simulate mock funding, open Delivery & review, inspect/download, then accept delivery
or record a complaint. Worker/background payments run automatically. Reload resumes.
Oakland/yoga buttons request a provider offer; review the separate offer, accept it,
and fund it separately. Recorded rehearsal has its own explicit button and no live
consent. Hosted/non-loopback bridge access intentionally fails 403, even in production.

Browser smoke, frontend directory, with both production servers already running:

```sh
npx playwright install chromium
BROKER_SMOKE_ORIGIN=http://127.0.0.1:3017 \
BROKER_SMOKE_OUTPUT=/private/tmp/datumco-browser-final \
node scripts/brokerage-smoke.cjs
```

This is separate from the invoice acceptance script. It refuses live payment mode,
uses real commands, verifies reload identity, CSV suppression/coverage and mock
capture, and saves `delivery.png`, `captured.png`, `delivery.csv`, `events-payment.json`
and `trace.zip`. The agent sandbox cannot bind/connect the host's local server ports;
the user started the servers, and the agent validated the real UI in Chrome.
Development run `request-e858effb8cca4241a23537b6d77f23dc` completed acceptance,
explicit mock funding, eight checks, capture and reload; a persisted source citation
resolved to version 1, age_min 25 and the frozen hash. Production run
`request-c2485a1fa6a7459e83ba39274442b81d` repeated the full journey on 3017:
all five canvas steps finished, $120 captured remained labeled mock, and reload
retained identity. Its actual downloaded CSV was independently checked locally:
27 unique ZIPs, 94110 count 170, 94129 suppressed with an empty/null count,
SHA-256 `72af48f698cc4857f784f51a5e75f4c017d88e5232fc3556c008f1007de0037f`.
The browser saved it as `/Users/nikitaafanaskin/Downloads/72af48f698cc4857f784f51a.csv`.
No recorded playback was used as acceptance evidence.

The repeatable Playwright production smoke also passed, executed from the user's
terminal against the same servers (Chromium 156.0.8078.4; no browser errors):
`request-61e0d9c0fe1f4779b4a02c0d333c090d`. Saved artifacts at
`/private/tmp/datumco-browser-final/{delivery.png,captured.png,delivery.csv,events-payment.json,trace.zip}`
were inspected locally: CSV hash/coverage/suppression match the manual download,
exactly one payment_captured and one books_posted event exist, payment is captured
and simulated, no explorer links exist, and the trace archive is valid. These
local temporary artifacts are not committed; the script regenerates them from a
clean checkout. The screenshot shows the original canvas design with completed steps
and a clearly labeled $120 mock capture.

Offline acceptance (no server ports), repository root:

```sh
uv run --locked --directory backend python ../tools/brokerage_acceptance.py --output /private/tmp/datumco-acceptance
uv run --locked --directory backend pytest
uv run --locked --directory backend ruff check . ../tools/brokerage_acceptance.py
uv run --locked --directory backend ruff format --check . ../tools/brokerage_acceptance.py
cd frontend
npm run generate:check
npm test
npm run typecheck
npm run build
npx react-doctor@latest --verbose --scope changed
```

The offline runner creates a fresh subdirectory per invocation and preserves previous
outputs. It saves report.json, per-case order/payment/ledger JSON, event traces, CSVs,
immutable source/authority/coverage files and the temporary DB. Observed output:
`/private/tmp/datumco-acceptance-final/broker-eok8knnc/report.json` — conforming capture booked
once with null tx; explicit producer fault corrected once; independently accepted/
funded Oakland delivery; cited yoga resolution with no fee.

## Validation status

Merged baseline before new work: 561 backend tests passed. The final combined
suite passed **615 tests in 80.29 seconds**, with one upstream websockets deprecation
warning. It includes the original catalog/invoice, Jeff broker/question/resume/improvement,
new dataset and Prompt 7 payment-readiness regressions. An obsolete primary API
name assertion was deliberately updated; legacy financial/clock checks were retained.

Observed frontend checks: 88 tests pass, strict typecheck passes, all five generated
contract families plus root OpenAPI are fresh, and isolated production build passes
with Node 24.14.1. Ruff lint/format passes across 147 Python files including the runner.
The development and production live browser journeys above both pass. The merged
payment lab's 27 subprocess commands also pass (capture, void and expiry/reclaim);
log: `/private/tmp/datumco-payment-examples-final.jsonl`. Lab Ruff lint/format passes
for all five files. All four required ancestry checks passed; Prompt 7-owned paths
are byte-identical to its completed commit.

React Doctor's changed-file scan reports eight hypotheses; its remote score API is
unreachable, so no numeric score comparison is claimed. Review confirmed one
maintainability warning (the live panel's control-flow complexity). The remaining
reports are covered by explicit behavior: the proxy preserves upstream HTTP status;
manual cursor polling is intentional; timers and requests are cleared/aborted;
post-await state updates check abort/generation; switching runs intentionally clears
busy state. Delayed-response, cancellation, backend-failure and 409 tests pass.
No diagnostic was suppressed. Consider splitting panel rendering in a later UI refactor.

No paid application models, live RPC, broadcasts, wallet access, push, deployment or
main merge occurred in this migration. Authenticated wallet availability does not
alter its offline scope. Prompt 7's separately recorded readiness evidence is in
its unchanged handoff; it is not a live application settlement. Real buyer signing,
full testnet application settlement and hosted authentication remain separate milestones.

## PR-ready description

**Title:** Make aggregate dataset brokerage the primary funded live workflow

New DatumCo requests now create immutable synthetic aggregate data contracts and
produce independently checked CSV/JSON through the existing funded worker. Eight
server-owned checks, a frozen coverage registry, safe suppressed counts and explicit
review/deadline budgets guard capture. Source deficiencies, provider correction,
additional scope and replacement consent retain distinct treatment.

Lucas's canvas consumes transactionally persisted run events from intake through
mock settlement, with generated contracts, resumable polling, resolving citations,
separate quote/funding controls and current-binding reviewer decisions. The trusted
loopback Next bridge keeps worker and reviewer credentials server-only; recorded
rehearsal remains separate. Historical catalog, invoice/jobflow, broker v0.3 and
improvement profiles retain their accepted policies. Reviewed main and Prompt 7's
completed lab-only commit are integrated without duplicate feature-branch merges.

Validation: 615 combined backend tests, 88 frontend tests, locked dependency setup,
Ruff lint/format, all generated clients, typecheck, production build, 27 offline lab
commands, offline brokerage acceptance and real development/production browser
journeys pass. Production smoke records one $120 mock capture/booking, reload
identity and a matching downloaded CSV, with screenshots/trace. React Doctor's
remote score is unavailable; diagnostics and their code-level triage are recorded
above. No live application settlement, hosted authorization, full x402 compliance
or post-capture refund support is claimed. No push or deployment is included.
