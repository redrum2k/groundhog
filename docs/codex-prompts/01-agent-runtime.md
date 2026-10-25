# Conversation 1 — agent execution and catalog orchestration

Implement Nikita's agent execution harness and automatic catalog dispatch in this
repository. Complete the code and offline validation; do not stop at a plan.

First inspect git status and the current branch/commit. Read AGENTS.md, applicable
nested instructions, HACK.md, CONTEXT.md, docs/PAYMENT_SPIKE.md,
docs/responsibilities.md, docs/handoffs/nikita.md, docs/handoffs/jeff.md and
docs/INTEGRATION_CHECKPOINT.md. Treat code as evidence of current behavior and HACK.md
as product policy; investigate discrepancies instead of inventing new policy.

Work only in this assigned worktree. If detached or on the selected base, create
`codex/catalog-runtime`; if already on that branch, continue. Do not reset an
existing branch or switch another worktree. You are not alone in this repository:
preserve teammates' changes and accommodate their interfaces. Do not edit the
original checkout or the other conversations' worktrees.

## Scope and ownership

Own new catalog scheduling modules under backend/app/runtime/, new private dispatch
storage helpers if required, backend/app/main.py startup/shutdown wiring, and
transport/budget handling in backend/app/agents/gateway.py. Own dedicated runtime
tests and docs/workstreams/01-runtime.md. Do not broadly refactor these directories.

Jeff owns compiler/investigator prompts, document generation, verification and
amendment semantics. Preserve those implementations and their typed interfaces.
Conversation 3 owns orders/catalog.py, payments/catalog.py, runtime/catalog_policy.py,
and payment journal/executor changes. Use existing service/repository APIs; record
any essential extension request in your handoff instead of editing their files.
Conversation 2 owns Base transport/configuration/runner. Conversation 4 integrates
the branches and updates shared API/status/handoff documentation. Keep public DTOs
and endpoints unchanged; preserve the separate /api/jobflow workflow.

## Implement

1. Inspect existing request compilation, claim_job/run_one, lease recovery, budgets,
   stale-result checks and background loops. Reuse them; do not replace the runtime
   with a new framework or recreate Jeff's agent implementation.
2. Add app/runtime/catalog_worker.py exposing CatalogWorker(service, ...), with
   synchronous run_once() -> bool for one bounded attempt or idle. Optional injected
   settings/clock/test doubles are fine. It must work with the existing CatalogService
   defaults and later settlement changes without importing the Base transport.
3. Automatically select eligible draft compilation and funded catalog work. Persist
   any additional dispatch bookkeeping needed for restart/concurrency safety, using
   additive private storage. Respect current clarification rounds, compiler-call
   budgets, deadlines, job leases and attempt limits. Recovery must not fabricate
   completion or assume a model call never ran after an interrupted request.
4. Work must pause for funding, evidence or consent, and resume only on eligible
   current state. Reuse service mutation/result application gates. A model result
   never directly mutates money, changes accepted terms or overrides stale bindings.
5. Wire bounded catalog consumption into application lifespan. Keep deadline sweeps,
   catalog execution, payment processing and invoice work responsive to one another:
   slow model/PDF/payment work must not block deadline advancement. Preserve the
   existing bounded payments.work entry point; conversation 3 will change its internals.
   Handle shutdown/restart without abandoning ownership in an unsafe state.
6. Preserve explicit paid-model opt-in, timeouts, token/input limits, evidence/tool
   allowlists and failure handling. Add only missing harness behavior and useful
   redacted diagnostics: IDs, stage, attempt, timing and outcome, not document bodies,
   secrets or evaluator labels. Do not add broad model tools or a new agent platform.

## Acceptance evidence

Use offline injected compiler/assessor responses and temporary databases/artifacts.
Prove initial compilation and post-answer compilation progress automatically; funded
orders dispatch without manual /internal work calls; unfunded/waiting orders do not
run; restart and competing consumers cannot publish duplicate deliveries; stale
completion cannot apply; budgets/deadlines survive retries. Exercise a slow/failing
worker while deadline processing and invoice compatibility remain operational.
Use injected clocks/events rather than long real-time sleeps.

Run uv sync --locked --project backend, relevant existing and new tests, and Ruff
lint/format checks. Do not weaken existing assertions to conceal lifecycle changes.
No paid model calls, broadcasts or deployment. Do not read/copy existing .env files
or use private local databases. Do not implement Lucas's frontend or production auth.

Self-review the diff against ownership and acceptance criteria. Write
docs/workstreams/01-runtime.md with the base commit, modified files, worker entry
point/configuration, tests actually run, demonstrated behavior, unresolved gaps and
precise integration requests. Explain the request -> agent run -> persisted finding
-> lifecycle flow in plain language. Commit only your changes locally, then return
the final commit SHA and handoff summary. Do not push, merge main or claim another
branch's work is complete.
