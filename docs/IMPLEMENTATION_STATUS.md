# Implementation status and next tasks

Recorded after scaffold generation and verification on **2026-10-23**. The checkout
was empty when work began. This is an initial scaffold, not a working end-to-end
product. No paid model/API calls, transaction broadcasts, or deployments were made.

Start with [AGENTS.md](../AGENTS.md), the root coding-agent instructions (plural,
uppercase filename). Product decisions are in [HACK.md](../HACK.md). See
[CODEX_SKILLS.md](CODEX_SKILLS.md) for suggested skills and how to invoke them.

## What exists and was verified

| Area | Implemented |
| --- | --- |
| Repository / ownership | Requested directory boundaries, root agent instructions, product baseline, glossary, architecture and independent teammate workflows. |
| Backend package | Python 3.12+, uv project and lockfile; FastAPI, Pydantic, SQLite support, LangGraph and Anthropic SDK dependencies. |
| API | `GET /health` returns status plus explicit mock mode and disabled live settlement. No other product endpoints. |
| Shared contracts | `OrderSnapshot`, `EvidenceReference`, `DeliveryVersion`, `InvestigationInput`, `InvestigationResult`, `SettlementIntent`, and supporting typed models. |
| Evidence / PDF contract | Exact version/hash citations; PDF page highlight rectangles; retained structured-data references with exact source provenance. Artifact contracts remain format-independent. |
| Investigator boundary | Async protocol returning cited findings, unresolved issues, questions and recommendations; result/input validation. No agent implementation. |
| Deterministic policy | Capture gate for verification, acceptance or 60-second expiry, disputes, current version binding, exact accepted price, and separate authorization expiry. One free regeneration, then human-review decision on failure; ambiguity also escalates. |
| Payments | Authorization/execution/reconciliation interfaces; default mock only; SQLite idempotency journal that survives restarts and rejects key/payload conflicts. All mock receipts remain mock. |
| Tests | 80 passing cases covering contracts, money/versions, PDF highlights, structured provenance, citation binding, payment authority boundaries, capture rules, escalation and durable mock deduplication. |
| Secrets / packaging | Ignore rules created before configuration; names-only `.env.example`; built wheel contains application code and no evaluation keys/environment files. |

## Verified commands and observations

Run from the repository root:

```sh
uv sync --locked --project backend
uv run --locked --directory backend pytest
uv run --locked --directory backend ruff check .
uv run --locked --directory backend ruff format --check .
uv build --project backend --wheel --out-dir backend/dist
```

Results: **80 passed**, lint clean, 24 Python files already formatted, wheel built.
The generated wheel and virtual environment are ignored local artifacts.

The actual server command was also smoke-tested:

```sh
uv run --locked --directory backend uvicorn app.main:app --reload --host 127.0.0.1 --port 8765
curl --fail --silent --show-error http://127.0.0.1:8765/health
```

HTTP 200 returned
`{"status":"ok","payment_mode":"mock","live_settlement_enabled":false}`.
The smoke-test server was shut down afterward. Ignore-rule probes confirmed that
nested `.env` files, databases/journals, dependency directories and private artifacts
are ignored, while `.env.example` remains eligible for version control.

## What still needs implementation

- **Durable application runtime:** order/snapshot storage, migrations, separate state
  transitions, version allocation, persisted acceptance/verification, 60-second
  scheduling, dispute/capture race handling, retries and restart recovery. Persist
  human review and regeneration usage atomically; the current pure policy functions
  do not themselves dispatch regeneration, create a review queue, or execute payments.
- **API and access control:** order creation/acceptance, artifact retrieval, reviews,
  disputes, questions/answers, permissions and input validation at authenticated routes.
- **PDF and structured-data pipeline:** actual source/delivery PDFs, ingestion,
  extraction/generation, stable record-to-PDF region mapping, storage and a scoped
  evidence resolver. Contracts preserve references; no actual PDFs or renderer exist.
- **Provider:** inference-job adapter, status/retry handling and output verification.
- **Investigator:** Jeff's tools, strategy, prompts, implementation, question/resume
  flow and quality evaluation. SDKs are installed but not called.
- **Frontend:** Lucas's Next.js setup, PDF source/result panes, linked highlights,
  review timer/controls, dispute/human-review views and explicit mock payment display.
- **Payments:** isolated CDP/Base spike, live adapter, durable execution reservations,
  release authority, reconciliation worker and finality proof. Live mode currently
  fails closed. The mock journal is not a live financial executor.
- **Evaluation / demo:** seeded corpus tools, independently reviewed cases and answer
  keys, offline evaluator, acceptance journey, sponsor checklist, pitch and backup.
  Restrict runtime workspaces to allowlisted evidence before enabling an investigator;
  package exclusion alone does not isolate a process with repository access.
- **Hosting:** Railway backend/frontend configuration, persistent SQLite storage and
  deployment checks. No infrastructure or public application exists yet.

## Remaining interface decisions

1. Nikita + Jeff approve initial schema semantics and how a provider defect becomes
   verified application evidence. No joint approval is claimed by this scaffold.
2. Nikita + Jeff + Lucas agree PDF crop/rotation transforms and page-count validation.
   Proposed highlights use one-based pages and normalized top-left coordinates.
3. Nikita + Jeff agree structured record/field serialization, PDF-region mappings,
   version allocation and question/answer resumption. Retained structured data must
   not contain evaluation answers or mutation labels.
4. Decide whether new evidence restarts the review clock. Current guard uses each
   delivery's timestamp and invalidates prior verification/acceptance on version changes.
5. Resolve payment network/asset/precision, authorization duration, escrow semantics,
   live release authority, confirmation/finality and human-review settlement policy.
6. Additional charging for unsupported complaints remains unresolved and unimplemented.

## First task for each teammate

| Teammate | Start here |
| --- | --- |
| Nikita | Review contracts with Jeff; persist immutable snapshots and separate states in SQLite, including an atomic operation reservation. Use mock payments while the spike remains open. |
| Jeff | Review contracts with Nikita; create one synthetic PDF/structured-data fixture with linked regions, then implement the investigator protocol against it. |
| Lucas | Scaffold Next.js/TypeScript/shadcn UI and build PDF source/delivery panes with citation navigation using local fixtures. Document frontend run/test commands. |
| Rehan | Independently review one defect case and one ambiguous case; separate runtime-safe inputs from private expected answers and draft acceptance criteria. |

See [responsibilities.md](responsibilities.md) for runnable independent backend
checks and [CODEX_SKILLS.md](CODEX_SKILLS.md) for optional workflow assistance.

## Files created

All source files below are new; existing teammate work was not present or overwritten.
Generated `.venv`, caches and wheel output are intentionally excluded.

```text
.gitignore
.env.example
AGENTS.md
CONTEXT.md
HACK.md
README.md
backend/
  pyproject.toml
  uv.lock
  app/
    __init__.py
    main.py
    api/__init__.py
    contracts/__init__.py
    contracts/models.py
    orders/__init__.py
    runtime/__init__.py
    runtime/policy.py
    storage/__init__.py
    storage/mock_journal.py
    payments/__init__.py
    payments/interfaces.py
    payments/mock.py
    provider/__init__.py
    investigation/__init__.py
    investigation/interface.py
    investigation/tools/__init__.py
    investigation/prompts/README.md
  tests/
    conftest.py
    test_health.py
    test_contracts.py
    runtime/test_policy.py
    payments/test_mock.py
    investigation/test_interface.py
docs/
  architecture.md
  responsibilities.md
  PAYMENT_SPIKE.md
  CODEX_SKILLS.md
  IMPLEMENTATION_STATUS.md
frontend/README.md
tools/corpus/README.md
evals/cases/README.md
evals/expected/README.md
spikes/payments/README.md
```
