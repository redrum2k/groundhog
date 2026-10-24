# Catalog order to cash

A CalHacks backend for a company selling custom data deliverables: turn a prompt into an
accepted, priced specification; fulfill a cited supplier-catalog shortlist; repair evidence;
and settle only after verification and customer review gates pass.

**Local demo; mock payments by default.** Four synthetic supplier PDFs, 48 products, real PDF generation/parsing,
offline model substitutes and mock money. No catalog customer authentication, production
tenancy, live supplier attestation, observed testnet settlement or deployment is claimed.
The payment direction is Base Commerce Payments on Base Sepolia with a dedicated platform
operator controlling capture/void; escrow holds funds and the backend applies accepted rules.
Buyers/providers trust that operator. Phase 1 supplies mock/fake contracts and frontend fixtures;
live adapter validation is a separate milestone. No x402 or separate verification fee.

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

`/docs` and `/openapi.json` expose typed contracts. Startup and background sweeps recover
deadlines. Durable jobs run through trusted `/internal/.../work` calls or the offline harness;
there is no automatic paid provider dispatch. The server initially has no corpus. Seed a
local database using the journey below, then point ORDER_DB_PATH/ARTIFACT_ROOT at its
`orders.sqlite3` and `evidence` directory to inspect that saved journey.

## Offline journeys

```sh
uv run --locked --directory backend python ../tools/offline_journey.py --scenario repaired --output artifacts/catalog-repaired
uv run --locked --directory backend python ../tools/offline_journey.py --scenario unresolved --output artifacts/catalog-unresolved
```

The first asks for net versus shipping weight, freezes a server quote, discovers unreadable
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

Tests include actual document checks, concurrency/restart recovery, stale results, deadlines,
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
| PAYMENT_ADAPTER | `mock` default; `base_sepolia` is the opt-in integration target. See capability/status reports before use. |
| ORDER_DB_PATH | SQLite store; default `artifacts/orders.sqlite3`. |
| ARTIFACT_ROOT | Approved content-addressed evidence directory; default `artifacts`. Never use the repository/evaluator root. |
| INTERNAL_API_TOKEN | Server-only provider/worker credential. |
| REVIEWER_API_TOKEN | Separate server-only reviewer credential; must differ from worker token. |
| PAYMENT_JOURNAL_PATH | Private durable payment journal; signed capabilities/transactions must never become public reports. |
| BASE_SEPOLIA_RPC_URL / BASE_CHAIN_ID | Base Sepolia RPC; chain ID must be 84532. |
| BASE_USDC_ADDRESS / BASE_ESCROW_ADDRESS / BASE_ERC3009_COLLECTOR_ADDRESS | Pinned deployment configuration; documentation addresses are not live deployment checks. |
| BASE_OPERATOR_PRIVATE_KEY | Dedicated disposable operator EOA, server only; never reuse another account implicitly. |
| BASE_PROVIDER_ADDRESS | Provider receiver address; no provider private key required. |
| SPIKE_BUYER_PRIVATE_KEY | Isolated runner only; frontend buyer signs through its own wallet. |
| PAYMENT_CONFIRMATIONS | Default/minimum 2 canonical receipt confirmations, not L1 finality. |
| ENABLE_TESTNET_BROADCAST | Default false; no broadcast is authorized by this task. |
| ENABLE_PAID_MODELS | Default disabled; exactly `true` opts into Claude. |
| ANTHROPIC_API_KEY / CLAUDE_MODEL | Explicit Claude credential and model choice. |

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
handoff for the runnable mock API and exact response/error/signature contracts. This does not
scaffold the frontend or imply that live Base execution is implemented.

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
The worker consumes invoice jobflow tasks alongside catalog deadline/payment work;
catalog PDF jobs still require explicit trusted dispatch. The current UI uses
invoice jobflow; connecting it to the catalog handoff remains separate frontend work.
