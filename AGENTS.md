# Coding-agent instructions

Read [HACK.md](HACK.md), [docs/PAYMENT_SPIKE.md](docs/PAYMENT_SPIKE.md), and any
nested `AGENTS.md` before editing. Product decisions live in HACK.md; terminology
lives in CONTEXT.md. Preserve teammates' changes. Inspect `git status` first and
edit only your task's scope; never reset, revert, or overwrite unrelated work.

## Commands (from repository root)

```sh
uv sync --locked --project backend
uv run --locked --directory backend uvicorn app.main:app --reload
uv run --locked --directory backend pytest
uv run --locked --directory backend ruff check .
uv run --locked --directory backend ruff format --check .
```

Use `pytest tests/runtime`, `pytest tests/payments`, or `pytest tests/investigation`
after the same `uv run --locked --directory backend` prefix for focused checks.
No credentials are required. Frontend commands belong to Lucas once he scaffolds it.

## Architecture and ownership

- Python/uv, FastAPI, Pydantic, SQLite; LangGraph and Anthropic SDK are available
  for later implementation. Next.js/React/TypeScript/shadcn UI is Lucas's scope.
  Railway is planned; add no infrastructure without a concrete need.
- Nikita: `backend/app/{api,orders,runtime,storage,payments,provider}`, durable
  orchestration, retries, authorization, reconciliation, backend deployment,
  and `spikes/payments`. Provider is the inference-job adapter.
- Jeff: `backend/app/investigation`, its tools/prompts, `tools/corpus`, investigation
  strategy, evidence tools, claim assessment, questions, recommendations, and quality
  evaluation. Those design choices are his.
- Lucas: `frontend`, PDF source/delivery inspection with linked evidence highlights,
  review controls, and frontend deployment. Leave frontend scaffolding to him.
- Rehan: customer evidence, `evals/cases`, independent `evals/expected` answer keys,
  acceptance testing, sponsor checklist, pitch, and demo.
- Nikita and Jeff jointly agree on `backend/app/contracts` and investigator/payment
  interfaces. Initial schemas are proposals for their review. Do not silently change
  fields or semantics; document changes and update consumers and tests together.

## Boundaries and invariants

- Keep order, delivery, case, and payment state separate. Freeze accepted snapshots.
  Financial rules are deterministic application code, never investigator authority.
- Enforce the 60-second review window, dispute block, passing verification, and
  acceptance-or-expiry capture gate. Authorization expiry is a separate deadline.
- Bind verification, acceptance, recommendations, and settlement intents to current
  snapshot/delivery/evidence/proposal versions; invalidate stale approvals.
- One verified provider defect permits one free regeneration per order. A failed
  regeneration or ambiguity escalates to human review. No automatic additional debit.
- Persist idempotency keys and exact requests before effects. Reconcile submitted or
  uncertain payments before retrying. Recheck/reserve against authoritative state
  atomically; pure policy functions alone are not a durable executor.
- PDF is the inspection surface; retain versioned structured data for reproducible
  checks. Keep artifact contracts format-independent. No workbook renderer or extra
  artifact formats in scaffold work.
- Runtime/investigator gets only allowlisted order evidence. Never expose
  `evals/expected`, grading labels, mutation recipes, or expected verdicts through
  prompts, tools, runtime mounts, public bundles, or fixture metadata.

## Tests, secrets, and disclosure

Test contract validation, stale versions/citations, review/authorization boundaries,
disputes, regeneration escalation, and retry idempotency without paid calls. Use
temporary databases and synthetic fixtures. Run focused tests plus Ruff after edits.
Read docs/responsibilities.md for each teammate's independent workflow.

Keep `.env`, `.env.*` (except `.env.example`), private/generated artifacts, local DBs,
and dependencies ignored. `.env.example` contains variable names only. Never print
credentials or put backend secrets in `NEXT_PUBLIC_*` variables.

The default adapter is explicitly mock and never confirms settlement. Label mock
payments, synthetic evidence, scripted components, and unimplemented flows in demos.
A submitted transaction is not confirmed settlement. Do not make paid API calls,
broadcast transactions, or deploy infrastructure without separate authorization.
