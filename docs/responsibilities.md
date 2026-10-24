# Ownership and independent workflows

Run commands below from the repository root. Everyone can first run
`uv sync --locked --project backend`; no paid service, secret, or other teammate's
component is needed for scaffold tests. `frontend/` is an ownership placeholder.

| Teammate | Owned scope | First actionable task |
| --- | --- | --- |
| Nikita | Durable runtime, API/orders/storage, retries, authorization, payments/reconciliation, provider inference adapter, backend deployment, payment spike | Review contracts with Jeff, then persist accepted snapshots and separate lifecycle states in SQLite with version checks and one durable operation reservation. |
| Jeff | Investigation strategy, evidence tools, prompts, claim assessment, questions/recommendations, quality evaluation, synthetic corpus generation/mutation | Review contracts with Nikita, then produce one PDF evidence fixture with structured records and highlight mappings; implement the investigator protocol against that fixture. |
| Lucas | Frontend, source/result PDF inspection, review controls, frontend deployment | Scaffold Next.js/TypeScript/shadcn UI; build two PDF inspection panes opening cited versions/pages/regions from local fixtures. |
| Rehan | Customer evidence, independently reviewed cases/answer keys, acceptance testing, sponsor checklist, pitch and demo | Write one independently reviewed defect case and one ambiguous case; store runtime-safe inputs separately from expected answers. |

Jeff owns his investigator design choices. Nikita and Jeff jointly approve shared
schemas and their evolution; Lucas joins review of PDF coordinates and API payloads.
Rehan's expected answers remain independent from Jeff's mutation recipe labels.

## Nikita

```sh
uv run --locked --directory backend uvicorn app.main:app --reload
uv run --locked --directory backend pytest tests/runtime tests/payments tests/test_health.py
```

Use `MockPaymentAdapter` and temporary local journals without CDP or chain access.
Implement the provider adapter independently using a fake job runner before any
authorized paid inference. The isolated payment spike is still unrun; record results
in PAYMENT_SPIKE.md before choosing a live adapter. Health is the only route today.

## Jeff

```sh
uv run --locked --directory backend pytest tests/investigation tests/test_contracts.py
```

`backend/tests/conftest.py` provides synthetic contract fixtures. Implement
`Investigator.investigate` and validate returned results with `validate_for`.
The protocol can be tested with local fakes and synthetic evidence before connecting
Anthropic/LangGraph. Never read `evals/expected` or accept gold labels in tool inputs.
Add corpus generation/mutation code under `tools/corpus`; pin random seeds and retain
structured source/output records plus PDF provenance. Corpus tooling has no CLI yet.

## Lucas

```sh
uv run --locked --directory backend uvicorn app.main:app --reload
curl --fail http://127.0.0.1:8000/health
uv run --locked --directory backend pytest tests/investigation tests/test_contracts.py
```

There is deliberately no frontend package or runnable UI yet. Choose and document
the package manager and dev/test commands in `frontend/README.md` when scaffolding.
Develop inspection/review views against local fixtures independently of the API.
Use `Citation.highlights` for exact PDF versions; show separate lifecycle statuses,
the review countdown, open disputes, and explicit mock payment labeling. Coordinate
authentication, artifact serving, and review endpoints before integration.

To inspect a contract as JSON Schema without starting the API:

```sh
uv run --locked --directory backend python -c 'import json; from app.contracts.models import InvestigationResult; print(json.dumps(InvestigationResult.model_json_schema(), indent=2))'
```

## Rehan

```sh
uv run --locked --directory backend pytest tests/test_contracts.py tests/runtime
uv run --locked --directory backend pytest tests/payments
```

These verify current contracts/policy, not a complete customer journey. Put reviewed
runtime-safe scenario inputs in `evals/cases` and private expected verdicts in
`evals/expected`. An offline evaluator may read both only after the investigator
returns; runtime never gets grading metadata. Generated/private PDFs and datasets
belong in ignored `artifacts/` or `private/`; deliberately reviewed public synthetic
fixtures may be committed under cases without answer leaks in names or metadata.

Write acceptance scenarios for clean delivery, verified defect, failed free
regeneration, ambiguity, unsupported complaint without extra debit, dispute at
expiry, stale approval, expired authorization, and uncertain settlement. Record
sponsor claims and distinguish synthetic/mock/scripted behavior in the demo.

## Shared checks

```sh
uv run --locked --directory backend pytest
uv run --locked --directory backend ruff check .
uv run --locked --directory backend ruff format --check .
```

Change only your scope. Do not overwrite others' edits or run schema migrations
against a teammate's database. Contract edits need joint review, consumer updates,
and focused regression tests. No actual customer or financial data belongs in tests.
