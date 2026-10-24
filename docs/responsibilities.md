# Ownership and independent workflows

Start with [AGENTS.md](../AGENTS.md), [HACK.md](../HACK.md), [API.md](API.md) and
[INTEGRATION_CHECKPOINT.md](INTEGRATION_CHECKPOINT.md). Run from the repository root:

```sh
uv sync --locked --project backend
uv run --locked --directory backend uvicorn app.main:app --reload
uv run --locked --directory backend pytest
```

## Nikita

Own API/orders/storage, durable orchestration, retries, authorization, payment execution
and reconciliation, provider inference jobs, persisted delivery packages and backend
deployment. Current mock API is ready for component integration. Next: wire the provider
job into publish/failure commands and investigate live CDP/Base semantics separately.

```sh
uv run --locked --directory backend pytest tests/api tests/runtime tests/payments
```

## Jeff

Own corpus generation, extraction and PDF coordinates; investigation strategy, evidence
tools, prompts, claim assessment, questions, verdicts and quality evaluation. Implement
`Investigator.investigate` against the HTTP investigation-input or its matching Python
model. Post validated results through the trusted worker API. Complete evidence can
close work early; incomplete disputed evidence gets at most two question rounds.

Next: produce the small PDF/structured fixture and region map; return a result covering
all eight invoice criteria. Keep expected answers and mutation labels out of runtime.

```sh
uv run --locked --directory backend pytest tests/investigation tests/test_contracts.py
```

## Lucas

Own frontend, PDF display/highlights, review controls and frontend deployment. Visually
review generated PDFs and classify correct, engine-failed, disputed and ambiguous
scenarios; coordinate the classification with Rehan's independent evaluation labels.
Jeff supplies coordinates and Lucas overlays them on the displayed page.

Next: scaffold Next.js/TypeScript/shadcn UI, consume the polling view every two seconds,
and implement revision/binding-aware commands. A 409 requires refetch; stop polling on
unmount and don't repeatedly resubmit stale payloads. Use server deadline/time for the
countdown. Red means operational failure. Do not put INTERNAL_API_TOKEN in the browser.

Document frontend package-manager/dev/test commands in frontend/README.md when built.
Use local fixtures until actual provider PDFs exist. Backend OpenAPI is available at /docs.

## Rehan

Own customer evidence, independent expected answers, acceptance checks, sponsor checklist,
pitch and demo. Lucas's visual labels are a separate review input; independently verify
expected outcomes. Keep keys in evals/expected or private evaluator storage, outside runtime.

```sh
uv run --locked --directory backend pytest tests/api tests/runtime
```

Acceptance cases: early evidence closure, undisputed timeout, correct extra fee after
refutation, missing fee requiring an accepted quote, free regeneration, failed regeneration,
two unanswered/inconclusive rounds, disputed cutoff hold, stale actions and engine failure.

## Shared boundaries

Nikita and Jeff jointly review future schema changes; Lucas joins UI/API reviews. Use
one fixture and the documented checkpoint. Preserve others' edits and use temporary DBs.
Tests make no paid calls. Actual model/provider calls and deployments require separate
authorization. Mock ledger entries are never live confirmed settlement.
