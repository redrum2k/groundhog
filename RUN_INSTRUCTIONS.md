> This document describes the preserved `/api/jobflow` invoice workbench.
> Catalog/payment handoff status is in [docs/IMPLEMENTATION_STATUS.md](docs/IMPLEMENTATION_STATUS.md);
> catalog policy is HACK.md, and invoice policy is [archived separately](docs/jobflow/INVOICE_POLICY.md).

# Run the integrated MVP

Python 3.12+, uv, Node 24 and npm. From the repository root in PowerShell:

```powershell
uv sync --locked --project backend
$env:JOBFLOW_DEMO = '1'
$env:ORDER_DB_PATH = '.local/integrated-v02.sqlite3'
$env:JOBFLOW_ANTHROPIC_MAX_CALLS = '0'
uv run --locked --directory backend uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Use a fresh database for v0.2. Old prepayment databases are not silently relabeled;
their evidence remains intact. In a second terminal:

```powershell
cd frontend
npm.cmd ci
$env:BACKEND_URL = 'http://127.0.0.1:8000'
npm.cmd run dev
```

Open http://127.0.0.1:3000/jobflow for the preserved invoice workbench. The root URL
serves Lucas's run canvas. Customer creates a Northwind case; provider corrects the
20 failures. Investigator reviews the disputed scope from actual sources; customer
answers or both parties sign an amendment. Controller approves the supported remedy;
executor executes that exact approval. For additional work, customer accepts the quote
and separately authorizes payment, executor records its mock receipt, provider fulfills
and customer accepts the new artifacts. Register verification checks eight criteria
and submits the result to the existing base-order service, without bypassing disputes.

For the complete included-field variant, sign due_date before the initial correction:
20 retries include it, then the one free field regeneration covers the remaining 80,
within the $1 compute cap. The separate four-field addition still costs $8.

The backend process owns recovery and the deadline worker; browser polling is not its
supervisor. API documentation: http://127.0.0.1:8000/docs. Worker credentials never enter
the frontend. Anthropic requires explicit backend key/model/call-cap configuration
and an intentional Anthropic investigation request; no paid call runs on startup.

## Verify

```powershell
uv run --locked --directory backend pytest -o addopts='' -q
uv run --locked --directory backend ruff check .
uv run --locked --directory backend ruff format --check .
npm.cmd --prefix frontend run generate:check
npm.cmd --prefix frontend test
npm.cmd --prefix frontend run typecheck
npm.cmd --prefix frontend run build
```

## V5 broker and improvement evidence

Catalog is the default API; the same server mounts invoice compatibility at
`/api/jobflow`, regional-data broker at `/api/broker`, and reviewer-controlled
improvement at `/api/improvements`. Each has its own `/docs` and `/openapi.json`.
Demo broker actors reuse invoice sessions; privileged catalog credentials remain
separate and server-side. See POLICY_DELTA.md for the distinct accepted profiles.

The finite, fully offline runner creates a new synthetic DB, proposes two candidates,
executes isolated 12-development/6-transfer comparisons, preserves rejected results,
activates the retained candidate, exports real artifacts and verifies rollback:

```powershell
uv run --locked --directory backend python ../evals/run_v5.py --output D:\Downloads\OBJECTION_V5_Fresh_Run
```

The output directory must not already exist. Reuse verified results unless implementation
changes require a new run; never overwrite a prior failure or relabel a result as a
different source revision. `result.json` reports model mode, actual calls, outcomes
and financial effects; `manifest.json` hashes evidence. Runtime cannot read offline
reference endpoints. Missing approved model configuration produces BLOCKED and zero
model calls; this offline command grants no paid access.

The under-512-MB results-first ZIP was delivered at 01:08 PDT on October 24, 2026:
`D:\Downloads\OBJECTION_V5_Results_20261024.zip` (3,198,759 bytes). It deliberately
preserves the earlier pre-rebase snapshot and its completion manifest. Consult
EVALUATION_RESULTS.md and HANDOFF.md for subsequent integration results.

## Deployment packaging

Use backend as its Docker build root. Mount one persistent volume at /data and set
ORDER_DB_PATH=/data/orders.sqlite3; use one worker. Railway config uses PORT and /health.
Use frontend as its Docker build root and provide BACKEND_URL at build time.
Public deployment requires team-owned customer authentication for both APIs. Keep the
demo local. Containers and Railway configuration are supplied; no deployment is run.
