# Review of prompt 08 results

Reviewed October 24, 2026. Result: prompt 08 completed its intended runtime fixes,
but one new failure-path regression needs a small follow-up. Two explicitly
deferred compiler bugs remain. Full mock startup is usable; release/live payment
readiness is not established.

## Reviewed result

- Worktree: `../order-to-cash-review-remediation`.
- Branch: `codex/review-remediation`.
- Commit: `692f500dcc00b2712c2e61f765e54cbef88632f7`.
- Clean working tree before and after this review; no application code changed.
- Verified that combined baseline `3519453` and prompt 07's `f8a929a` are ancestors.
  The four prompt-07-owned files are still byte-identical to `f8a929a`.
- After code review, GitHub reported no PR for this branch, so there was no PR
  review discussion to incorporate.

## Original findings

| Finding | Review result |
| --- | --- |
| R1: malformed JSON exposes suppressed counts | Addressed. Every public dataset JSON object must match a strict allowed schema; duplicate keys and unsafe values are blocked. HTTP regressions cover malformed sources and retained historical PDF access. |
| R2: answer references disappear | Addressed at the promised transport boundary. Typed answers persist atomically with their binding and references; an injected assessor receives the resolving passage after restart. Interpretation remains Jeff's responsibility. |
| R3: negated yoga expands scope | Still broken and accurately disclosed. Strict expected-failure test reproduces it. |
| R4: clarification cannot correct original cohort | Still broken and accurately disclosed. Strict expected-failure test reproduces it. |
| R5: returned money shown as held | Addressed. Typed payment-state effects override the current financial display while preserving capture/booking history. Whole-component transition tests cover returns and reorg hold. |
| R6: every browser complaint targets category | Addressed on the normal path. Explicit requirement/row/column/intent controls and server validation replace hardcoded category submissions. Its target builder introduces R7 below. |

R3/R4 were intentionally excluded from prompt 08's semantic ownership, so leaving
them open is consistent with the task. They are not passing tests: running the
two tests with `--runxfail` produces exactly two failures. Do not describe the
full suite as completely green or remove these tests to claim completion.

## R7 — P2: unavailable preview blocks status polling and valid complaints

Location: `backend/app/orders/dataset.py:15`, called from
`backend/app/orders/runs.py:199` and `validate_dataset_complaint`.

The new `complaint_targets` function reopens and parses the delivered preview
every time a caught-up run page or complaint is processed. If this file disappears
or no longer matches its frozen hash, the exception aborts the whole status page
and rejects a complaint about that very artifact failure. Existing order/payment
state and persisted events are still readable in SQLite, but the live browser
cannot obtain them or the current review/release controls.

Fresh baseline/treatment reproduction with temporary synthetic state:

| Fault after a normal funded delivery | `3519453` | `692f500` |
| --- | --- | --- |
| Overwrite preview bytes; GET `/runs/{id}/events` | 200, funded state remains visible | 409, `artifact does not match frozen hash`, no payment metadata |
| Delete preview file; GET `/runs/{id}/events` | Not rerun for this variant | 404, `approved artifact unavailable` |
| Delete preview; submit otherwise valid R-ARTIFACT/dataset complaint with current binding | Not rerun for this variant | 404, no complaint recorded |

The first row proves this is a regression introduced by 08. Only newly created
temporary artifacts were modified/deleted; no existing user data was touched.

Suggested repair: derive complaint identities from the accepted requirement and
coverage snapshot without requiring readable delivery bytes. If optional
delivery-derived rows are retained, failures must not suppress the durable status
page or a valid whole-dataset artifact complaint. Preserve strict artifact hash
checks, source validation and independent capture revalidation. GET must remain
read-only; it must not repair files, extend deadlines, change findings, return
funds or fabricate new events.

Add HTTP regressions for missing and hash-mismatched previews, pagination/catch-up,
restart, unchanged read state, valid complaint recording and capture refusal.
The unavailable artifact endpoint should still return 404/409. Do not restore a
raw-byte fallback or treat missing bytes as verified output.

## Fresh checks

| Check | Result |
| --- | --- |
| Locked Python sync | Passed |
| Full backend suite | 656 passed, 2 expected failures, 82.16 seconds; one upstream websockets deprecation warning |
| Compiler blockers with `--runxfail` | Exactly R3 and R4 failed, as disclosed |
| Frontend under Node 24.14.1 | 100 tests passed in 13 files |
| Frontend typecheck and all generated-contract freshness | Passed |
| Ruff lint and format, including brokerage runner | Passed; 153 files formatted |
| Additional artifact-failure probes | Reproduced R7 against baseline and remediation |

The prompt-08 handoff separately records production build and both browser
smokes passing. Those browser/build results were not rerun in this review; the
fresh checks above are distinct from that earlier evidence.

## Recommended next actions

1. Run [08b-polling-recovery.md](../codex-prompts/08b-polling-recovery.md) in the
   existing remediation worktree. It is a small continuation of 08, not a reason
   to repeat the entire task or merge the old main.
2. Give Jeff the top section of the remediation worktree's `docs/handoffs/jeff.md`
   and the two compiler regression tests. Request an exact tested commit fixing
   R3/R4; integrate it before claiming the whole intake flow is corrected.
3. Run full local mock startup from the remediation checkout. Its
   `docs/workstreams/08-review-remediation.md` has commands for backend 8028 and
   frontend 3028 plus both `brokerage-smoke.cjs` and `review-remediation-smoke.cjs`.
   The ordinary happy path can be exercised now; include the repaired failure
   paths and compiler inputs in the final acceptance pass.
4. Nikita's next independent payment milestone is fenced lease renewal, total
   operation deadlines and audited exact-byte recovery, followed by measured
   read-only preflight. These are the still-open shared-runtime items from 07/08.
   Actual testnet broadcasts require separate authorization. The backend is not
   ready for a public deployment without the documented hosted access boundary.

No additional Lucas blocker remains among the original six: the basic target
and evidence controls were implemented in 08. Row/cell-click UX and visual polish
remain his optional next frontend work, not prerequisites for testing the
existing mock journey.
