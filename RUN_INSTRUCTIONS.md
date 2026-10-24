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

Open http://127.0.0.1:3000. Customer creates a Northwind case; provider corrects the
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

## Packaging

Use backend as its Docker build root. Mount one persistent volume at /data and set
ORDER_DB_PATH=/data/orders.sqlite3; use one worker. Railway config uses PORT and /health.
Use frontend as its Docker build root and provide BACKEND_URL at build time.
Public deployment requires team-owned customer authentication for both APIs. Keep the
demo local. Containers and Railway configuration are supplied; no deployment is run.
