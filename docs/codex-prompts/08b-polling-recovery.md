# Continue 08 — keep run status and complaints available when an artifact fails

Continue the existing `codex/review-remediation` worktree at
`/Users/nikitaafanaskin/Documents/Developer/order-to-cash-review-remediation`.
The reviewed result is `692f500dcc00b2712c2e61f765e54cbef88632f7`, which retains
the combined 06/07 work. Inspect current status/history first; preserve any later
changes and use a reviewed descendant when applicable. Do not create another
worktree, reset another branch, remerge 07 or run this from the old main checkout.

Read AGENTS.md and applicable nested instructions, HACK.md, docs/responsibilities.md,
docs/PAYMENT_SPIKE.md and docs/workstreams/08-review-remediation.md. Read the new
review at `docs/reviews/08-results-review.md` in this worktree. The shared remote
starting point is `origin/codex/review-remediation`; it includes 06, 07, 08 and
these follow-up instructions.

This is Nikita's small API/runtime follow-up, R7. You are not alone in the
repository; preserve teammates' changes. Own the complaint-target/runtime API
fix and its regressions. Do not expand into compiler semantics, payment executor
redesign, new infrastructure or frontend redesign.

Jeff can work concurrently on a separate compiler branch/worktree from the same
published base. His scope is `backend/app/agents/dataset.py`, the R3/R4 compiler
regressions and related semantic tests; his handoff is `docs/handoffs/jeff.md`.
Your scope is `backend/app/orders/dataset.py`, necessary runtime/API regressions
and the workstream-08 follow-up record. Preserve the compiler tests and do not
merge Jeff's branch during this implementation/test pass. Integrate his exact
reviewed commit after the two tasks are independently validated.

## Reproduce the regression

With a temporary DB, synthetic sources and an injected clock, create, explicitly
mock-fund and deliver a normal aggregate order. Preserve its current revision and
binding. Then independently test these two storage faults, only on those new
temporary artifacts:

1. Overwrite the preview file with different bytes.
2. Remove the preview file.

At `692f500`, `GET /runs/{id}/events` returns 409 for the hash mismatch and 404 for
the missing preview instead of the durable events and payment state. An otherwise
valid R-ARTIFACT/dataset complaint about the missing artifact also returns 404.
At baseline `3519453`, the hash-mismatch status poll still returned 200 with the
funded state. The new unconditional preview read in
`DatasetLifecycle.complaint_targets` causes the regression.

## Required behavior

- Derive mandatory complaint targets from the immutable accepted requirements
  and coverage keys. An unreadable delivery artifact must not prevent inspecting
  an order or recording a valid complaint about the artifact. Keep exact
  requirement/field/row/column/intent and binding validation.
- Prefer removing unnecessary artifact I/O from target construction. If optional
  delivery-derived information remains, handle unavailable/corrupt content
  explicitly without exposing unvalidated bytes or losing the status response.
- Keep GET read-only and cursor-consistent. It must not advance the workflow,
  repair files, change findings, shorten review, extend authorization, emit new
  effects, capture or return money. Do not invent a returned/successful state.
- The artifact download itself must continue to fail closed with 404/409.
  Mandatory verification and capture revalidation must continue to reject
  missing/hash-mismatched bytes. Do not convert an artifact error into a PASS or
  a raw public fallback.
- Preserve append-only events, original snapshots, exact idempotent responses,
  stale-binding behavior, funding gates and the corrected R1/R2/R5/R6 paths.

## Tests and completion

Add meaningful HTTP regressions for both faults: successful bounded event polling
including final catch-up, unchanged persisted state on reads, preserved current
payment metadata, restart/replay, valid whole-dataset artifact complaint recording,
and refusal to capture unverifiable delivery. Retain negative tests for invalid
complaint targets and unsafe artifact downloads. Use the actual API/service path.

Run focused dataset/API tests, full backend pytest, Ruff lint/format and generated
contract freshness. If frontend/contracts change, run frontend tests/typecheck
and both production browser smoke scripts. The two R3/R4 compiler tests remain
explicitly unresolved unless an independently reviewed Jeff fix is available;
do not remove or weaken their expected results.

Update docs/workstreams/08-review-remediation.md with R7's cause, fix, commands
actually run and remaining blockers. Commit only task-owned changes locally and
return the SHA plus test/startup instructions. No push, main merge, deployment,
private environment/wallet/database access, paid model calls or broadcasts.
