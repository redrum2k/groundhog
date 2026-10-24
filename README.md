# Invoice order to cash

Cal Hacks invoice-processing orders with PDF evidence inspection, disputes and
policy-bound settlement. Start with [AGENTS.md](AGENTS.md), [HACK.md](HACK.md),
[API contract](docs/API.md) and [implementation status](docs/IMPLEMENTATION_STATUS.md).

## Run locally

Python 3.12+ and uv; from the repository root:

```sh
uv sync --locked --project backend
uv run --locked --directory backend uvicorn app.main:app --reload
curl --fail http://127.0.0.1:8000/health
```

`/docs` describes the polling and mutation API. `/health` reports mock mode and disabled
live settlement. Startup opens a local SQLite DB and recovers expired reviews. A worker
advances deadlines independently of browser polling. There is no frontend yet.

```sh
uv run --locked --directory backend pytest
uv run --locked --directory backend ruff check .
uv run --locked --directory backend ruff format --check .
```

## Configuration

`.env.example` lists names only. Privately supply values through the shell or a local
`.env` loaded with uv's `--env-file`; the application does not automatically load it.

| Name | Meaning |
| --- | --- |
| PAYMENT_ADAPTER | Only `mock` is supported. |
| ORDER_DB_PATH | Defaults to `artifacts/orders.sqlite3`, relative to backend when using the commands above. |
| MOCK_PAYMENT_DB_PATH | Defaults to `artifacts/mock-payments.sqlite3` for the standalone adapter. |
| ARTIFACT_ROOT | Approved local evidence directory; defaults to `artifacts`. Never point at the repository or evaluator keys. |
| INTERNAL_API_TOKEN | Backend-only token for trusted delivery/failure/verdict/quote routes; never expose through NEXT_PUBLIC variables. |
| ANTHROPIC_API_KEY | Reserved for future authorized model integration; unused now. |

The API currently has no customer authentication and is for local mock development.
Use localhost. It does not generate PDFs, invoke a model/provider, move money or deploy.
Set a private worker token to exercise producer routes; tests inject their own local
values and temporary databases. No credentials are needed for the test suite.

The [uv lockfile](backend/uv.lock) is pinned. See [independent workflows](docs/responsibilities.md),
[the shared checkpoint](docs/INTEGRATION_CHECKPOINT.md), and [suggested skills](docs/CODEX_SKILLS.md).
