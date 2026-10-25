# Groundhog — aggregate order-to-cash

Current bounded qualification: [final evidence and reproduction](docs/HYPHENATE_FINAL_QUALIFICATION.md)
and [judge defense / three-minute demonstration](docs/HYPHENATE_JUDGE_DEFENSE.md).
Real Claude investigation, approved persistent source knowledge, verified artifacts and mock
settlement have run together. The qualified local launcher uses an explicitly registered
budget-only model grant; default startup remains offline. Synthetic sources and simulated
roles are disclosed. This is not production readiness or a newly verified on-chain trial.
Historical offline/catalog statements below describe their earlier milestones, not the newer live trials.

Turn Summit Fitness's request into a frozen data contract, fund it explicitly, deliver
independently checked synthetic aggregate CSV/JSON, then settle under the review rules.
The primary app at `/` (also `/live`) shares a full-screen customer conversation and
the agent's Run canvas, both driven by the same durable aggregate order. Claude calls
and Base Sepolia payments use the configured backend; checkout requests one buyer
signature after connection. The retained broker/recorded rehearsal lives at `/demo`.
Mock payments are the default; no live testnet settlement success is claimed.

Start with [product policy](HACK.md), [migration and runnable acceptance](docs/workstreams/06-data-broker.md),
[domain language](CONTEXT.md) and [migration decision](docs/adr/0001-aggregate-brokerage.md).
The migration handoff contains exact backend/frontend production commands, trusted
local-demo configuration, explicit acceptance/funding steps, and browser-test setup.
No private .env, wallet or existing database is needed.

```sh
uv sync --locked --project backend
uv run --locked --directory backend python ../tools/brokerage_acceptance.py --output /private/tmp/datumco-acceptance
cd frontend
npm ci
npm run generate:check
npm test
npm run build
```

Use Node 24 (minimum 22.12). The offline runner saves source/authority/coverage
artifacts, event traces, CSVs and final payment bookings in a fresh directory.
The live development and production browser flows passed against a fresh mock backend:
explicit quote acceptance, funding, all eight checks, CSV download, reload and capture.
See the handoff for reproducible commands and saved evidence.

The payment rail is direct Base Commerce Payments on Base Sepolia, with a trusted
platform operator; no x402 facilitator or CDP server-wallet operator is implemented.
Accepted historical catalog, invoice/jobflow, broker-review-v0.3 and improvements
remain compatible under their existing policies.

## Historical catalog reference (compatibility only)

# Catalog order to cash

A CalHacks backend for a company selling custom data deliverables: turn a prompt into an
accepted, priced specification; fulfill a cited supplier-catalog shortlist; repair evidence;
and settle only after verification and customer review gates pass.

**Local demo; mock payments by default.** Four synthetic supplier PDFs, 48 products, real PDF generation/parsing,
offline model substitutes and mock money. No catalog customer authentication, production
tenancy, live supplier attestation, observed testnet settlement or deployment is claimed.
The payment direction is Base Commerce Payments on Base Sepolia with a dedicated platform
operator controlling capture/void; escrow holds funds and the backend applies accepted rules.
Buyers/providers trust that operator. Automatic catalog dispatch, the Base transport and
asynchronous settlement are integrated and tested offline, including the actual transport
with injected RPC. Separately authorized live validation remains outstanding. No x402 or separate verification fee.

Start with [product policy](HACK.md), [ownership](docs/responsibilities.md),
[API](docs/API.md), [implementation status](docs/IMPLEMENTATION_STATUS.md) and
[integration checkpoint](docs/INTEGRATION_CHECKPOINT.md).

## Run

Python 3.12+ and uv, from the repository root:

```sh
uv sync --locked --project backend
uv run --locked --directory backend uvicorn app.main:app --reload
curl --fail http://127.0.0.1:8000/health
```

`/docs` and `/openapi.json` expose typed contracts. Independent background lanes automatically
compile requests, run eligible catalog jobs, process one payment operation per turn, run invoice
jobs and sweep both policies' deadlines. Defaults use the offline compiler and mock money;
funding still requires explicit authorization. One application owns the database worker lock;
shutdown drains active calls. Trusted manual endpoints remain available. The server initially has no corpus. Seed a
local database using the journey below, then point ORDER_DB_PATH/ARTIFACT_ROOT at its
`orders.sqlite3` and `evidence` directory to inspect that saved journey.

## Offline journeys

```sh
uv run --locked --directory backend python ../tools/offline_journey.py --scenario repaired --output artifacts/catalog-repaired
uv run --locked --directory backend python ../tools/offline_journey.py --scenario unresolved --output artifacts/catalog-unresolved
```

The first asks for net versus shipping weight, freezes a server quote, explicitly authorizes
simulated funding, dispatches through `CatalogWorker`, discovers unreadable
prices before delivery, accepts a registered replacement, rechecks the actual shortlist PDF,
waits 60 injected seconds and books one mock capture. The second receives a readable but
unregistered replacement and reaches human review without capture. An additional
`--scenario date-conflict --output artifacts/catalog-date-conflict` variant demonstrates conflicting
effective dates. Paths are relative to `backend` with these commands.

Each directory contains persistent SQLite state, approved source/output PDFs, `order.json`,
`human-review.json` and `summary.json`; the successful journey also exports `shortlist.pdf`.
An exact completed rerun returns the saved summary; choose a fresh directory to rerun revised
code. These commands do not sleep, call models, move money or read evaluator answers.

## Validation

```sh
uv run --locked --directory backend pytest
uv run --locked --directory backend ruff check .
uv run --locked --directory backend ruff format --check .
```

Tests include full HTTP/lifespan journeys with actual Base transport and synthetic RPC,
actual document checks, concurrency/restart recovery, stale results, deadlines,
repairs/consent, disputes/correction, reviewer authority and historical JSON compatibility.
`tests/legacy` verifies old DTO decoding; the old commercial mutation executor is retired.

## Optional Claude configuration

Actual key=value examples appear in `.env.example`. The app does not automatically load `.env`; use shell
variables or uv's `--env-file` with an ignored private file. Configure ANTHROPIC_API_KEY,
CLAUDE_MODEL (a structured-output-capable model) and ENABLE_PAID_MODELS=true only when
separately authorized to make paid calls. The default remains offline even if a key exists.
No paid calls were made while implementing or validating this repository.

The adapter uses Anthropic's documented
[`messages.parse` / Pydantic structured outputs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs),
with bounded inputs/outputs, a 20-second timeout, no SDK retries, and explicit refusal/
malformed-output handling. Schema validity does not establish truth. Clause drafting and
semantic findings never carry executable payment permission. Jev is optional and absent.

| Variable | Purpose |
| --- | --- |
| PAYMENT_ADAPTER | `mock` default; `base_sepolia` selects the implemented transport and startup read-only preflight. No fallback to mock on failure. |
| ORDER_DB_PATH | SQLite store; default `artifacts/orders.sqlite3`. |
| ARTIFACT_ROOT | Approved content-addressed evidence directory; default `artifacts`. Never use the repository/evaluator root. |
| INTERNAL_API_TOKEN | Server-only provider/worker credential. |
| REVIEWER_API_TOKEN | Separate server-only reviewer credential; must differ from worker token. |
| PAYMENT_JOURNAL_PATH | Isolated laboratory journal only. Catalog payment journal shares ORDER_DB_PATH so confirmation and booking commit together. |
| BASE_SEPOLIA_RPC_URL / BASE_CHAIN_ID | Base Sepolia RPC; chain ID must be 84532. |
| BASE_USDC_ADDRESS / BASE_ESCROW_ADDRESS / BASE_ERC3009_COLLECTOR_ADDRESS | Pinned deployment configuration; documentation addresses are not live deployment checks. |
| BASE_OPERATOR_PRIVATE_KEY | Dedicated disposable operator EOA, server only; never reuse another account implicitly. |
| BASE_OPERATOR_ADDRESS | Public operator address for key-free preparation; must match the signer when supplied. |
| BASE_PROVIDER_ADDRESS | Provider receiver address; no provider private key required. |
| SPIKE_BUYER_PRIVATE_KEY | Isolated runner only; frontend buyer signs through its own wallet. |
| PAYMENT_CONFIRMATIONS | Default/minimum 2 canonical receipt confirmations, not L1 finality. |
| BASE_MAX_GAS / BASE_MAX_FEE_PER_GAS | Bounded transaction ceilings; defaults 1000000 gas / 10000000000 wei. |
| ENABLE_TESTNET_BROADCAST | Default false; no broadcast is authorized by this task. |
| ENABLE_PAID_MODELS | Default disabled; exactly `true` opts into Claude. |
| ANTHROPIC_API_KEY / CLAUDE_MODEL | Explicit Claude credential and model choice. |

`/health` keeps the existing schema: `live_adapter=disabled` means implemented but not selected;
`unavailable` means selected Base lacks required configuration/signer or failed startup preflight;
`ready` means configured with a signer and successful read-only startup preflight.
`live_settlement_enabled` additionally requires ENABLE_TESTNET_BROADCAST=true. These are
startup capabilities, never proof of funds or live success. Each operation rechecks exact terms.
Restart after repairing unavailable configuration. Missing signer/preflight failure disables
submission while available receipt inspection can continue. See the [runbook](docs/PAYMENT_RUNBOOK.md).

Keep privileged credentials out of browser bundles and NEXT_PUBLIC variables. Local customer
actor names are demo audit labels, not authenticated identities. Bind to localhost.

Deadline: **October 25, 2026, 9 a.m. America/Los_Angeles**. Tracks: Hyphenate, Coinbase,
Microsoft; actual sponsor requirements remain to be verified. See the
[payment laboratory](docs/PAYMENT_SPIKE.md), [Lucas handoff](docs/handoffs/lucas.md) and
[runnable payment fixtures](frontend/fixtures/README.md). No real testnet receipt is claimed.


## Frontend contract generation

Regenerate the authoritative API snapshot and complete TypeScript schema types from the root:

```sh
uv run --locked --directory backend python ../tools/export_openapi.py --output ../docs/openapi.json
npx --yes openapi-typescript@7.10.1 docs/openapi.json --output frontend/api.generated.ts --default-non-nullable false
```

`frontend/contracts.ts` imports these generated types for focused helpers. See the Lucas
handoff for the runnable mock API and exact response/error/signature contracts. Use Node >=22.12.0
(validated with 24.14.1). The catalog generator is separate from the invoice-only
`frontend/scripts/generate-contracts.mjs`. `npm run generate:check`, `npm run typecheck`,
`npm test` and `npm run build` in `frontend` check the existing invoice workbench.
No catalog UI is implemented by this backend integration.

## Existing invoice workbench

The merge also preserves Jeff's invoice jobflow and Next.js workbench on
`/api/jobflow`. Start it with `JOBFLOW_DEMO=1` and follow
[frontend setup](frontend/README.md) and [invoice API](API_CONTRACT.md).
Its OpenAPI/interactive docs are `/api/jobflow/openapi.json` and `/api/jobflow/docs`.
The catalog API and schema remain at `/openapi.json` and `/docs`.

These are separate workflow contracts. The invoice demo retains its
[versioned invoice policy](docs/jobflow/INVOICE_POLICY.md), isolated in
`orders/invoice_compat.py` and `runtime/invoice_policy.py`. It does not authorize
catalog payments, inherit catalog funding states, or migrate historical orders.
Independent lanes consume invoice and funded catalog tasks alongside deadline/payment work,
including compatibility broker expiry. Startup recovers invoice and improvement work.
The invoice workbench is at `/jobflow`; Lucas's run canvas stays at `/`.
Its recorded/stub feed remains distinct from real backend execution.

## Broker review and improvement workflow

The additive broker profile accepts typed regional-data requirements, produces and
checks actual data/PDF artifacts, handles bounded evidence questions and human holds,
and gates mock capture on the accepted review policy. Its improvement loop proposes,
tests, approves and activates prospective intake changes, preserving rejected results
and supporting rollback without rewriting accepted orders.

Start the existing backend with `JOBFLOW_DEMO=1` for local demo identities. The new
interactive APIs are `/api/broker/docs` and `/api/improvements/docs`; existing catalog
and invoice APIs remain unchanged. Next proxies those routes with the existing local
session boundary. No existing screen, component or stylesheet is replaced.

- [Policy profiles](POLICY_DELTA.md) and [API contracts](API_CONTRACT.md#v5-broker-and-improvement-interfaces)
- [Measured results and negative findings](EVALUATION_RESULTS.md)
- [Offline runner and setup](RUN_INSTRUCTIONS.md#v5-broker-and-improvement-evidence)
- [Current handoff](HANDOFF.md)
