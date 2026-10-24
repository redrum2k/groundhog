# Implementation status and next tasks — v0.2

Updated 2026-10-23 after the user's invoice/review/payment corrections and clarification:
unresolved disputed payments stay held at cutoff; extra processing uses the accepted
fee, or a separately accepted quote if no fee exists. This replaces the initial scaffold status.

Start with [AGENTS.md](../AGENTS.md), [HACK.md](../HACK.md), [API.md](API.md) and
[INTEGRATION_CHECKPOINT.md](INTEGRATION_CHECKPOINT.md). Optional skills remain in
[CODEX_SKILLS.md](CODEX_SKILLS.md).

## Implemented

| Area | Current behavior |
| --- | --- |
| Invoice specification | All eight explicit criteria are documented and represented by typed criterion assessments. Compliance requires cited passes for all eight; final-delivery assessment must cite the actual output PDF. |
| Order persistence | Accepted snapshot, separate lifecycle states, delivery/evidence/proposal versions, questions/answers, mock authorization and ledger are persisted in SQLite. |
| Polling and commands | Customer and trusted-worker routes, two-second polling guidance, server deadlines, available actions, revision/binding checks and 409 stale-action responses. |
| Concurrency and retries | BEGIN IMMEDIATE serializes state checks and mock bookings; exact idempotent responses persist across restart. Changed payloads under a used key conflict. |
| Base payment | Mock authorization opens on order acceptance; early complete evidence, customer acceptance or undisputed cutoff books the base once. All receipts remain mock. |
| Review cutoff | 600 seconds per delivered version/new dispute. Background sweep, startup recovery and request-time advancement. Unresolved disputes hold payment and escalate. Authorization expiry remains independent. |
| Supported claim | One reserved free regeneration; another defect or engine failure during that regeneration escalates to human review. |
| Refuted claim | Evidence is exposed in the result; exact agreed processing fee is booked. If absent, a quote must be issued and accepted before any extra booking. |
| Questions | One evidence-driven question per round, at most two total. Answers become versioned evidence; inconclusive result after the second answer or cutoff escalates. |
| Failure/version semantics | Engine failure is operational_failure (red), without inventing a PDF version. Replacement publication requires failure or a reserved supported-defect regeneration. Answers change evidence/proposal versions only. |
| Evidence delivery | Registered current-order evidence is served from approved artifact storage or persisted customer JSON, with SHA-256 checks and path-escape rejection. |
| Ownership | Jeff owns coordinates/corpus/extraction/agent; Nikita owns provider/persistence/payment execution; Lucas displays highlights and visually classifies generated PDFs; Rehan independently evaluates. |
| Agent guidance | Updated root AGENTS.md; added investigation, frontend and evaluation AGENTS.md files with the revised boundaries. |

These checks validate evidence structure, provenance and current binding. They do not
implement PDF extraction, arithmetic verification tools or establish that a synthetic
worker assessment is factually true; those remain Jeff/provider integration work.

## Verified

```sh
uv sync --locked --project backend
uv run --locked --directory backend pytest
uv run --locked --directory backend ruff check .
uv run --locked --directory backend ruff format --check .
uv build --project backend --wheel --out-dir backend/dist
```

- **111 tests passed**, including API journeys, live lifespan deadline advancement,
  concurrent dispute/capture attempts, parallel retries, restart recovery, quotes,
  question budgets, free regeneration, verdict evidence constraints and artifact isolation.
- Ruff lint/format checks passed; 31 Python files formatted.
- OpenAPI exposes 13 paths and the 600-second/strict-revision constraints.
- A real Uvicorn smoke test with an isolated temporary database returned HTTP 200 for
  /health and /openapi.json. The test server was stopped afterward.
- v0.2 wheel built; runtime package excludes evaluator keys and environment files.
  The environment example contains names only and local/private files remain ignored.

No paid calls, transaction broadcasts, infrastructure deployment or live settlement occurred.

## Remaining work and next owner tasks

| Owner | Next task |
| --- | --- |
| Nikita | Wire actual provider jobs to the persisted regeneration reservation and trusted publish/failure API. Complete customer authentication/tenant access before deployment. Run the separately authorized payment spike before any live adapter. |
| Jeff | Produce the small source/delivery PDF fixture and structured region map; implement Investigator.investigate, factual verification tools and evidence-driven questions against current contracts. |
| Lucas | Scaffold the frontend, display PDFs/highlights, visually classify cases, and connect polling/version-bound controls. Keep worker credentials out of the browser. |
| Rehan | Independently evaluate the fixture and scenarios; keep expected answers outside runtime; finish acceptance/sponsor/pitch work. |

Actual source/delivery PDFs and generator/extractor are not supplied yet. Model/provider
calls, frontend, upload flow, human-decision/refund execution, live transaction dispatch/
reconciliation and Railway deployment remain unimplemented. Human escalation is durable
state; a person-facing decision UI/API is still needed. A refund request is not a refund.

Payment-spike questions remain asset/network/precision, extra-fee authorization, expiry/
renewal, finality, and human release/refund authority. PDF crop/rotation and physical
page bounds need confirmation against the real fixture. The first checkpoint is
90 minutes after the team's split begins, with a one-invoice fallback at the 30-minute
check-in; no event deadline or scheduled automation was invented.

## Principal changed and new files

- Root: AGENTS.md, HACK.md, CONTEXT.md, README.md, .env.example.
- Contracts: backend/app/contracts/models.py and new backend/app/contracts/api.py.
- API/runtime: backend/app/main.py, new backend/app/api/orders.py,
  new backend/app/orders/service.py, backend/app/runtime/policy.py.
- Persistence/payments: new backend/app/storage/orders.py, updated mock receipt helper
  and adapter interfaces; original standalone mock journal retained.
- Investigation: protocol/prompts and new backend/app/investigation/AGENTS.md.
- Tests: new backend/tests/api/test_orders.py and investigation/test_verdicts.py;
  updated fixtures, policy/interface and health tests.
- Metadata: backend/pyproject.toml and backend/uv.lock updated to 0.2.0.
- Documentation: API.md and INTEGRATION_CHECKPOINT.md added; architecture.md,
  responsibilities.md, PAYMENT_SPIKE.md and this status rewritten to current policy.
- Frontend/evaluation: frontend/README.md updated; frontend/AGENTS.md and evals/AGENTS.md added.
