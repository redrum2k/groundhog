# Main integration — October 24, 2026

Integrated remote main `c2f5619` with `codex/review-remediation` at `086b5ba`.
This retains 06, 07 and 08 plus Lucas's newer broker demo and visual changes.
The user explicitly authorized merging and publishing main. Work was prepared
in an isolated checkout; the remediation worktree was left unchanged.

## Merge resolution

The aggregate `LiveRun` remains the default. Recorded rehearsal exposes the
older `/api/broker` workflow as **Legacy broker demo**, labeled scripted parties
and mock payments. Its source generator, translator, routes and fixture tests
are retained. It requires `JOBFLOW_DEMO=1` on the loopback backend; the aggregate
bridge separately requires `BROKER_LOCAL_DEMO=1` and distinct server-only tokens.

Generated Pydantic wire types remain authoritative. The shared display schema
adds the legacy `contract_line_asked` event and `mock` rail. This does not alter
accepted payment terms or payment execution. The fold retains pending interview
lines and server review windows while preserving 08's event deduplication,
bindings and payment-state handling. Legacy authorization remains distinct from
confirmed aggregate funding. Lucas's logo and layout changes are retained.

Two checks exposed issues that were fixed before the merge:

- The existing concurrent request test intermittently failed because artifact
  publication created the final path before writing its bytes. Another writer
  could read an empty file and report a collision. A new deterministic test
  pauses one writer before its write and reproduces that failure. Publication
  now writes and flushes a private temporary file, then atomically hard-links it
  into place without replacing an existing object. Parallel identical writes
  converge; corrupt existing bytes remain unchanged and rejected. Both the new
  regression and the existing request concurrency test pass.
- Lucas's legacy source generator reused the aggregate rehearsal rows, where a
  suppressed count is now null. The numeric-only legacy source upload returned
  422 and stalled intake. The legacy demo now offers only released rows and
  freezes that same coverage at intake. It never replaces nulls with invented
  counts or exposes the old suppressed value. A regression failed before this
  adjustment; both the source checks and the actual legacy browser journey pass.

## Validation

All data was newly created synthetic state. Paid models, testnet broadcasts and
deployment remained disabled.

| Check | Result |
| --- | --- |
| Full backend pytest after artifact fix | 658 passed, 2 expected failures, 92.23 seconds |
| Artifact publication and existing concurrency regression | 3 passed; corruption still fails closed |
| Ruff lint and format | Passed, 154 Python files formatted |
| Frontend tests | 104 passed in 15 files |
| Typecheck, generated-contract freshness, production build | Passed under Node 24.14.1 |
| Aggregate production browser | Mock funding, delivery, reload, safe CSV and capture passed; no page errors |
| Targeted coverage complaint browser | Correct ZIP/column/intent reached the backend; independently refuted; no page errors |
| Legacy production browser | Scripted no-dispute order reached mock capture; no page errors |
| React Doctor full-source comparison | Score 38 before and after; pre-existing diagnostics remain, not a clean scan |
| Prompt 07 preservation | Its four owned files remain byte-identical to `f8a929a` |
| Whitespace / conflict markers | Passed |

The React Doctor baseline was an archive of tracked `086b5ba` source, excluding
local build artifacts. Its existing polling/cleanup and other diagnostics are
not claimed fixed by this merge. The merged translator's non-null-assertion
warning is inherited from main. No diagnostics were suppressed.

Browser evidence is local at `/private/tmp/order-to-cash-main-e2e.3to2whwb`,
including `final-happy`, `final-coverage`, `legacy-smoke.json` and
`legacy-captured.png`. Temporary databases, browser artifacts and dependencies
are not committed. The upstream websockets deprecation warning remains.

## Next work

R3/R4 compiler bugs remain strict expected failures; Jeff's
[handoff](../handoffs/jeff.md) now starts from `origin/main`. R7 remains the
separate [08b task](../codex-prompts/08b-polling-recovery.md); this merge does not
claim to fix unavailable-preview polling or complaint handling. Payment recovery
and measured live preflight remain separate work as documented in
[workstream 08](../workstreams/08-review-remediation.md).

Before starting 08b in the existing **clean** remediation worktree, fetch and
fast-forward to the reviewed main integration:

```sh
git fetch origin
git merge --ff-only origin/main
```

If an 08b session has already started, preserve its work and integrate main after
that task's commit instead. There is no need to recreate the worktree or remerge
07. Merge publication does not establish live-payment or public-deployment readiness.
