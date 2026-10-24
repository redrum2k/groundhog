# Order to cash

Cal Hacks scaffold for document-processing orders, PDF evidence inspection,
dispute investigation, and authorized settlement. Start with [AGENTS.md](AGENTS.md),
[HACK.md](HACK.md), and [docs/responsibilities.md](docs/responsibilities.md).

## Run locally

Use Python 3.12+ and uv. From the repository root:

```sh
uv sync --locked --project backend
uv run --locked --directory backend uvicorn app.main:app --reload
```

In another terminal:

```sh
curl --fail http://127.0.0.1:8000/health
```

Expected response:

```json
{"status":"ok","payment_mode":"mock","live_settlement_enabled":false}
```

`/docs` exposes the health API. Product endpoints and a frontend do not exist yet.
No credentials, model calls, chain access, or database are needed for `/health`.

```sh
uv run --locked --directory backend pytest
uv run --locked --directory backend ruff check .
uv run --locked --directory backend ruff format --check .
```

The [lockfile](backend/uv.lock) pins resolved dependencies; `--locked` checks it
without updating it ([uv documentation](https://docs.astral.sh/uv/concepts/projects/sync/)).

## Configuration

`.env.example` deliberately lists names only, with no assignments or credentials.
Defaults work without `.env`; the application does not automatically load it.
For local overrides, set environment variables in your shell or use uv's
`--env-file .env` from the appropriate working directory after privately adding values.

| Name | Meaning |
| --- | --- |
| `PAYMENT_ADAPTER` | Defaults to `mock`; every other value fails closed. |
| `MOCK_PAYMENT_DB_PATH` | Local mock journal; defaults to `artifacts/mock-payments.sqlite3` relative to the running process. |
| `ANTHROPIC_API_KEY` | Reserved for Jeff/Nikita's future authorized implementation; unused now. |

Mock adapter instances must be closed by their callers. Its SQLite journal persists
idempotency across restarts but is not a live payment executor. See
[architecture](docs/architecture.md), [payment spike](docs/PAYMENT_SPIKE.md), and
[current status / next tasks](docs/IMPLEMENTATION_STATUS.md).
