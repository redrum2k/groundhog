# Frontend and reviewed payment integration — October 24, 2026

Implementation merge: **`4a24c9f91962c2924770614e38b6e6edee905a94`**. This combines
reviewed 09/09b, the existing local frontend/schema fixes and latest fetched main.
The combined offline checks below passed before publication. No paid models, real
chain RPC, wallet/private-database access, broadcasts or deployment were used.
Documentation commit `676b4e258098a2be75c5aeec8b3d3033307fedeb` records these results
without changing runtime code. The final fetch kept main at `04756e1`; only Jeff's
separate branch advanced, as recorded below. The session reports the normal push
and verified local/remote SHA.

## Exact inputs and preservation

| Input | Exact revision / result |
| --- | --- |
| Local main and cached origin/main at start | `dbf9006f4578196e93652b6de838f2e83d94b794`; the earlier fast-forward from `62fe035` was already complete |
| First fetched origin/main | `04756e131233d47739dfa6c3eb89b917f2b60284`, adding Lucas's route instructions through `3fb6a4b` |
| Local change checkpoint | `384c21e`; ten explicitly named frontend/schema/policy/handoff files |
| Latest-main merge | `e2307e4`; normal merge, preserving the local checkpoint |
| Payment worktree / branch | `../order-to-cash-payment-lease-renewal`, `codex/payment-lease-renewal`, clean at `593e02fcbc63b45d95d252e7314289eda39d4fb0` |
| Original 09 commit | `9622fe0ecff1bcae01e4b7104f053c9d58e2e393` |
| 09 base / merge base with local main | `62fe03542f18d9f7514550bcff25968ae2557c08` |
| Reviewed payment merge | `4a24c9f91962c2924770614e38b6e6edee905a94`; exact `593e02f` is an ancestor |
| Separate Jeff branch, first fetch | `origin/feature/aggregate-intake-integration-20261024` at `e774495192f903d0c1191590cf13cfc4a9439977`, unmerged |
| Separate Jeff branch, final fetch | `849e98a791551546ee29fda67392041301bf1a43`, still unmerged and unreviewed |
| Jeff/main merge base | `31ad60b9a95b73e0c788752030edc0c0f195f441` |
| Remote | `origin`, `https://github.com/redrum2k/order-to-cash.git` |

Status, history, all nine worktrees and remotes were inspected before mutations.
All starting modified/untracked files were copied with SHA-256 manifest and binary
diff to `/private/tmp/datapact-integration-x50g8eqi/starting-files/`. No worktree
was stashed, reset or cleaned. Existing user servers on 8016/8028 and 3016/3017/3028
were left running. Test servers used 8049/3049 and fresh temporary synthetic state.

The local checkpoint preserves the explicit typed `ErrorResponse` for 422 with
`Unprocessable Content`, changing documentation text only. Runtime/exported schema
agreement passes. Aggregate header branding is Groundhog; **Run canvas** returns to
`/`. Both aggregate smoke scripts append `/live` to a bare smoke origin. Frozen
parties, pricing IDs (including `datumco-demo-pricing-v1`), amounts, deadlines,
funding/settlement gates and historical snapshots were not changed.

Two conflicts were resolved by content:

- `frontend/AGENTS.md`: retain Lucas's specific broker driver/translator/store and
  caption-event guidance, identify the broker as retained compatibility, and
  preserve both routes and their visual design.
- `docs/handoffs/nikita.md`: retain both the earlier failed review and 09b's
  implementation report under historical headings, then add current integration
  status. Neither historical failure nor passing implementation evidence was erased.

`backend/app/main.py` merged automatically: both the shutdown cancellation hook
and explicit 422 description remain. No generated client was hand-edited.

## Independent 09b review

Reviewed the [09 task](../codex-prompts/09-payment-lease-renewal.md),
[09b amendment](../codex-prompts/09b-payment-attempt-boundaries.md),
[original failed review](09-results-review.md), and
[implementation handoff](../workstreams/09-payment-lease-renewal.md).
The original review/probe remain historical evidence, not a claim that 09 was
already correct. Inspection covered the actual HTTP child boundary, reservation
transaction, attempt/claim checks, journal/executor, final-send checks, reclaim,
shutdown and preserved readiness/crash cases.

The saved [historical probe](repro_09_lease_boundaries.py) accesses 09's removed
private Web3 provider. The temporary adapted copy changes only its timeout injection:
`HttpRpc(url, timeout=0.1)` replaces `_provider._request_kwargs['timeout'] = 0.1`.
The twenty bytes at 30 ms intervals and 250 ms attempt remain the same. It exercises
production `HttpRpc` and `BasePaymentTransport`, not an unbounded fake.

| Requirement | Independently observed on exact `593e02f` |
| --- | --- |
| Continuously streaming HTTP | `AttemptStopped` after **0.078 seconds** under the scaled 0.100-second HTTP allowance |
| Buyer signing consumes 301 seconds of 300-second attempt | CLI status **3**, **zero new operations**, no persisted authorization and zero broadcasts |
| Cancellation/cleanup and late-result fencing | Real loopback regressions pass; child reaped and pipes closed before return; no late result |
| Signing / SQLite-lock deadline checks | Budget, cancellation and financial-expiry cases pass, including preservation of a concurrent existing signed reservation |
| Lease and nonce fencing | Wrong/expired/exact-boundary tokens, stale owner/successor, two workers, nonce serialization, 136-second renewal and expired-lease negative cases pass |
| Immutable financial boundaries | Original funding/capture/aggregate cutoff checks pass; renewal grants no financial extension; inspection remains available after expiry |
| Ambiguous send / unsent-submitted gap | Durable bytes/hash/nonce stay unresolved; subsequent work inspects the same identity without resend, new salt or invented booking |
| Focused boundary suite | **63 passed**, 3.17 seconds |
| Offline lab | All **27** commands passed before merging |

The actual default HTTP allowance remains 15 seconds, with 0.25 seconds reserved
inside it for kill/reap. Submission/inspection budgets remain 300/180 seconds;
the 120-second lease renews at cooperative 30-second checkpoints. No SQLite lock
spans HTTP, signing or helper cleanup. A killed send may already have reached the
endpoint: timeout cannot prove absence. OS scheduling is not a real-time guarantee;
synchronous signer results are checked on return. The change passed independent
review for integration. Exact-persisted-byte recovery is still separate work.

## Final combined-tree validation

Locked Python dependencies and Node **24.14.1** dependencies installed successfully
without lockfile changes. Every application test used fresh temporary synthetic
state; all lab subprocesses use their empty-environment offline mode.

| Check | Result |
| --- | --- |
| `uv sync --locked --project backend` | Passed |
| `pytest tests/payments tests/runtime tests/dataset tests/api --tb=short --show-capture=no` | **377 passed, 2 xfailed**, 46.88 seconds |
| `pytest --tb=short --show-capture=no` | **720 passed, 2 xfailed**, 97.82 seconds; complete successful teardown |
| `backend/.venv/bin/python spikes/payments/examples.py` | **27 commands passed** again on the combined tree |
| Backend + `tools/brokerage_acceptance.py` Ruff lint/format | Passed; **160** files formatted |
| Backend + entire `tools/` Ruff lint/format from backend cwd | Passed; **165** files formatted |
| `spikes/payments` Ruff lint/format using backend config | Passed; **5** files formatted |
| Node 24 `npm ci` | Passed; 184 packages installed, audit reported zero vulnerabilities |
| `npm test` | **109 tests passed**, 16 files |
| `npm run generate:check` | Passed; all generated contracts fresh |
| Runtime/exported OpenAPI test | Passed separately and in both backend suites; explicit typed 422 description agrees |
| `npm run build` | Passed with isolated `.next/integration-x50g8eqi` output |
| `npm run typecheck` | Passed with isolated build and again after restoring only Next's automatic temporary config additions |
| React Doctor changed scan | **92**, no findings, before checkpoint and after integration |
| React Doctor full scan | **38**, matching reported pre-integration baseline; preexisting findings retained, exit 1; no suppressions or general UI cleanup |
| `git diff --check` | Passed |

Python commands used `uv run --locked --directory backend`. Ruff commands were:

```sh
uv run --locked --directory backend ruff check . ../tools
uv run --locked --directory backend ruff format --check . ../tools
backend/.venv/bin/ruff check --config backend/pyproject.toml spikes/payments
backend/.venv/bin/ruff format --check --config backend/pyproject.toml spikes/payments
```

The upstream websockets deprecation warning remains. The first full React Doctor
attempt failed sandbox DNS; the approved retry completed. No failed/interrupted
run was counted as a pass. An extra root-cwd Ruff invocation with explicit backend
config classified `app` imports differently and reported 63 import-order findings;
the documented backend-cwd check over the whole backend/tools passed without edits.
Lab checks retain their own documented root invocation. Next's isolated build temporarily adjusted `tsconfig.json`
and `next-env.d.ts`; exact saved originals were restored after verifying those
were the only edits. No user build directory was removed or replaced.

## Production browser evidence and restart

Fresh backend: loopback `127.0.0.1:8049`, explicit mock payments, broadcasts/paid
models disabled, `JOBFLOW_DEMO=1`, model-call allocation zero, distinct disposable
server-only worker/reviewer tokens. Production Next: `127.0.0.1:3049`, matching
`BACKEND_URL`, `BROKER_LOCAL_DEMO=1`. Neither server loaded private configuration.
Chromium **156.0.8078.4** was launched with disposable contexts.

```sh
# frontend, Node 24; keep the origin bare
BROKER_SMOKE_ORIGIN=http://127.0.0.1:3049 \
BROKER_SMOKE_OUTPUT=/private/tmp/datapact-integration-x50g8eqi/aggregate \
node scripts/brokerage-smoke.cjs
BROKER_SMOKE_ORIGIN=http://127.0.0.1:3049 \
BROKER_SMOKE_OUTPUT=/private/tmp/datapact-integration-x50g8eqi/coverage \
node scripts/review-remediation-smoke.cjs
```

- `/live` funded journey: run `request-1c156099a9ac41669fb9d364d77d719a`, explicit
  quote acceptance and mock funding, delivery/download, suppressed-null disclosure,
  reload identity and one mock capture. No browser errors or explorer links.
- `/live` targeted coverage complaint: `request-d43e390f48a34127b2d43b9dc078fa28`,
  `R-COVERAGE` / ZIP 94110 / column zip / factual-dispute intent preserved. Actual
  backend finding was disagree because the exact ZIP is present; no unrelated
  yoga question, fee or chain claim. No browser errors.
- Backend stopped cleanly and restarted against the same temporary database.
  Both runs retained exactly the same events, bindings, accepted terms, financial
  deadlines and payment/operation identities. Browser reloads made zero POSTs,
  retained both IDs, and downloaded bytes matched the original delivery hashes.
- `/` retained broker journey: Groundhog branding, contract approval, delivery,
  Oakland objection, two evidence events, acceptance and one mock capture.
  All three customer actions returned to the agent view. Browser errors: zero.
  This is `broker-review-v0.3` with its own mock authority, not aggregate escrow.
- Recorded fallback: health deliberately unavailable, Recorded selected, playback
  and pause worked, zero live-run POSTs and zero page errors. An initial temporary
  probe used a nonexistent `.msg` selector; correcting it to the existing `.chat
  .bub` verified fallback without product changes. The successful root journey
  was already complete before that probe-only failure.

Evidence (local, uncommitted): `/private/tmp/datapact-integration-x50g8eqi/` contains
logs, starting copies, adapted probes, browser scripts/traces/screenshots, downloaded
CSV and restart snapshots. Representative root/aggregate screenshots were inspected.
The isolated build and runtime artifacts remain ignored. Only task-owned servers
are stopped after validation. Current startup instructions and distinct routes:
[manual testing guide](../TEST_PLATFORM_NOW.md).

## Separate Jeff work and remaining blockers

The fetched feature branch is not merged or cherry-picked. Available commits:
`d2b6ba126f0c8fa0ba37b7b0be38eaa269a4645c`,
`5946378555e1966b45de34c684a60c4eac83af68`, and
`ef8c99afb9cf5f3b6928f505242f2d622fce2c3e`.
Reported `0983c1b` remains an unavailable object and is not substituted for another
revision. The final fetch now exposes additional published intake-consent/Claude
wiring at `706f41e`, frontend integration at `37a8bf1`, and handoff `849e98a`.
Only their history/diff scope was inspected; this task did not review or qualify
them. Publication alone is not semantic qualification. The branch remains unchanged
and unmerged; its inclusion of newer main does not authorize the remaining feature.

For prompt 10, available audit tooling is `tools/audit_primary_evidence.py` at
`ef8c99a`; blob **`51acbf86a90ff8f1cc3e7397db3fd7776ad2fc68`** is identical at
`e774495` and final fetched `849e98a`. This identifies provenance, not completed
evaluation qualification.
Do not execute its private-path entry point. Review/reuse pure audit logic in the
separately scoped task, with attribution and compatibility tests.

R3/R4 are present in the actual starting and combined main baseline and remain
unchanged strict expected failures. Compiler/intake qualification, general aggregate
evaluation, exact-byte transaction recovery, observed chain receipts, hosted
identity/tenancy and deployment are not completed by this integration. No pricing,
accepted party, review window, payment authority or historical snapshot was altered
to obtain passing tests. No automatic resend or new financial ledger was introduced.

## Starting untracked files, individually classified

Only the reviewed manual guide and the 09 review's directly linked provenance are
selected for the final scoped documentation commit. Other drafts remain untouched
and untracked; a local file's existence does not imply reviewed publication.

| Starting untracked path | Disposition |
| --- | --- |
| `docs/LOCAL_AND_RENDER_RUNBOOK.md` | Preserve local; older broad deployment/runbook draft, outside this offline integration |
| `docs/TEST_PLATFORM_NOW.md` | Update and commit; reviewed current manual guide linked above |
| `docs/codex-prompts/01-agent-runtime.md` | Preserve local; historical runtime prompt |
| `docs/codex-prompts/02-base-transport.md` | Preserve local; historical transport prompt |
| `docs/codex-prompts/03-catalog-settlement.md` | Preserve local; historical settlement prompt |
| `docs/codex-prompts/04-integration.md` | Preserve local; earlier integration prompt |
| `docs/codex-prompts/05-run-canvas-integration.md` | Preserve local; earlier canvas task |
| `docs/codex-prompts/06-data-broker-migration.md` | Preserve local; earlier migration task |
| `docs/codex-prompts/07-payment-readiness.md` | Preserve local; earlier laboratory task |
| `docs/codex-prompts/08-review-remediation.md` | Preserve local; historical remediation task |
| `docs/codex-prompts/09-payment-lease-renewal.md` | Commit unchanged; directly reviewed acceptance requirements |
| `docs/codex-prompts/09b-payment-attempt-boundaries.md` | Commit unchanged; directly reviewed amendment requirements |
| `docs/codex-prompts/10-aggregate-evaluation.md` | Preserve local; separate future implementation prompt |
| `docs/codex-prompts/README.md` | Preserve local; broader prompt index with historical/future jobs |
| `docs/codex-prompts/integrate-local-and-main.md` | Preserve local; input draft, superseded for status by this evidence record |
| `docs/pr-drafts/10-aggregate-evaluation.md` | Preserve local; separate future PR draft |
| `docs/reviews/06-07-thermo-nuclear-review.md` | Preserve local; older review draft |
| `docs/reviews/09-results-review.md` | Commit unchanged; historical independent failure evidence linked above |
| `docs/reviews/repro_09_lease_boundaries.py` | Commit unchanged; original reproducible failure probe, adaptation described above |

The earlier local modifications to Nikita/Jeff handoffs and responsibilities were
checkpointed before merges, then reconciled with current status while retaining
their historical findings. No whole-repository staging or forced push is used.
