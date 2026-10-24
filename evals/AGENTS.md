# Independent evaluation — Rehan

Follow root AGENTS.md and HACK.md. Rehan owns customer examples, independent expected outcomes,
acceptance scenarios, usefulness/failure analysis, sponsor validation, pitch/demo/backup and
judge questions. Jeff owns assessment semantics and evaluation tooling; Lucas's PDF visual
review provides additional input, not replacement ground truth.

## Authorized aggregate tooling exception — Prompt 10

The user and Jeff delegated general aggregate evaluation infrastructure to Nikita:
`tools/aggregate_eval.py`, `evals/aggregate/`, focused `backend/tests/evals/`, and
the [workstream 10 handoff](../docs/workstreams/10-aggregate-evaluation.md).
This narrow exception supersedes the older all-tooling assignment above. Nikita
owns isolated execution, requirement scoring, byte/citation audit integration and
JSON/Markdown reports. Rehan retains independent expectations, rationales, review
and development/held-out classification; bundled engineering labels are not gold.
Jeff retains compiler R3/R4, conversational interpretation, scope consent, Claude
wiring, evidence enforcement and developer regressions. Do not alter runtime
contracts or semantics for an evaluator result. Lucas retains all frontend work.
Keep the existing acceptance smoke, legacy v5 evaluator and frozen historical
reports unchanged. Evaluator labels/recipes never enter runtime DTOs or prompts.

First label clean, defective, repaired, substantively amended and unresolved catalog cases by
independently inspecting actual source/output PDFs. Keep labels, generator truth and mutation
metadata in expected/private evaluator storage, unavailable to runtime tools/prompts/manifests.
Runtime-safe cases may contain only selected artifacts/customer evidence. A second model agreeing
with the producer is not independent truth. Optional Jev must be assessed for false passes,
missed contradictions, abstention, latency and cost before adoption; no arbitrary confidence cutoff.

Do not invent Hyphenate/Coinbase/Microsoft requirements. Deadline: October 25, 2026, 9 a.m.
America/Los_Angeles. Follow docs/INTEGRATION_CHECKPOINT.md. No paid calls or deployments authorized.
