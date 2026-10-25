# Enabled, persistent source learning in the local DataPact app

Branch: `feature/live-source-learning-20261024`, based on GitHub main `af1a0e8`
(merged PR #24). This is an enabled controlled local application feature, not
an unrestricted production deployment. The historical sandbox report remains in
[SOURCE_KNOWLEDGE.md](SOURCE_KNOWLEDGE.md).

## Running application and observed result

- Frontend: **http://127.0.0.1:3026/live**. Open **Learning active** at bottom left.
- Backend: http://127.0.0.1:8026; ordinary brokerage worker is running.
- `SOURCE_LEARNING_MODE=controlled_local`; persisted approved version is active.
- Synthetic source data, simulated source-owner/controller identities, explicit
  customer acceptance and mock funding. No paid model calls or real broadcasts.
- Lucas's animated `/` route is unchanged. The learning panel is additive on `/live`.

Two independent source-owner corrections supply the count-column operations for
two disjoint ZIP partitions. The composed procedure normalizes both partitions,
rejects overlap, and joins their fresh rows. It contains evidence-bound operations,
not prior output rows or hardcoded final answers.

| Observed case | Stateless internal reviews | Approved learner reviews | Assessment operations, baseline -> learner |
| --- | ---: | ---: | ---: |
| Different order, new batch | 2 | 0 | 14 -> 20 |
| Another new batch after backend restart | 2 | 0 | 14 -> 20 |

Both arms saw the identical source/authority bindings in each pair. A separate
read-only audit reopened immutable records, source bytes and owner evidence, checked
the stateless holds and the learned normalization, and verified all **27 delivered
CSV rows** for each order. These count the initial source-assessment decision;
preparation revalidation, composition, shadow verification, HTTP and delivery are
outside that counter. They are not total CPU cost, elapsed human time, or claimed
financial savings.

The final qualification used **six fresh engineering cases**, not the old nine-case
suite: new values, permuted rows, current public definitions, conflicting definitions,
revoked authority and changed schema. Both arms were independently byte-verified in
6/6 cases. Reviews were **10 -> 6** and assessment operations **80 -> 92**. The
stateless arm uses current authoritative definitions when supplied; it is not an
intentionally ignorant baseline. These are not independent human evaluation labels.

The first live HTTP authority-conflict counterexample recorded two required holds
and no accepted order. Its evidence remains preserved. The final build additionally
passes fresh conflict/revocation/schema-change qualification and safety regressions.
After correcting attribution and qualification pin preservation, fresh owner evidence
and explicit controller approval established the final version on authority revision 3;
the app was left on valid current inputs, not the conflict fixture.

## Exact evidence and identities

All paths below are relative to the repository. Generated sources, databases,
credentials, traces and screenshots are ignored; they are not committed datasets.

Final live evidence directory:
`.local/live-learning/evidence/3afcc202f4684b9895d9ed34cfe1ed89/`

- `http-trace.json`: actual ordinary HTTP commands and responses, without credentials.
- `owner-ui.json`, `approval-ui.json`, `inspect-ui.json`: actual frontend actions,
  visible events and zero observed page errors; not playback.
- `owner-before.png`, `approval-after.png`, `live-comparison.png`: rendered UI proof.
- `training-order.json`, `later-order.json`, `after-restart-order.json`: real persisted
  explicit-acceptance/mock-funding/verified-delivery results.
- Corresponding `*-source.json`, `*-delivery.csv`, `*-events.json` and `*-result.json`.
- `session.json`: initial/restarted process identities and run/order IDs.
- `independent-audit.json`: separate read-only verification of both actual arms.
- `status-result.json`: enabled and current active-version observation.

| Artifact | Exact ID |
| --- | --- |
| Active version | `institutional-adf1216bd2fc6e632bc584248cec0c9210290849eab589baa298ce9bb3043e5b` |
| Composed candidate | `institutional-f67aaa9ccfb79b78787d0b65d9c3273ffca4fdfa9876480ada5d92cb32429fdf` |
| Qualification | `institutional-2e5be8979bd2ad6a67723c678e15fcc9a7bf31c57ad84a88962c44437a332e9f` |
| Qualification capsule SHA-256 | `a30c760c31965a818d81c690fe68b03c7f6c50c5b776613c5dce137db78f0342` |
| Component 1 | `institutional-4cc1757372ca4c3b7f398789912a7633832a9b563714dd7bab94219a36d012fb` |
| Component 2 | `institutional-e75f5a876c388b509d701082fd10a5d56588adde242b524a957dd6886fca2cf9` |
| Owner resolution 1 | `institutional-3fb89ebb60f8b43493d1e0eb6b028965c89be33fcee9681d3b776e68f27b2a17` |
| Owner resolution 2 | `institutional-00144599ca2c5eebe74d71e17658c56d9ddd9ce740772da7cbf895ea18306dd4` |

Owner-evidence SHA-256 values are respectively
`b237e1cd0781fa9c1d168656ceb674d4ce284c2e4a44e1512d2a05efc3287806` and
`52ff160cfc6482b5fb48f0f43708b9e04f641628995745d801d8c0f40c34e91e`.
Each evidence record pins its own original source bytes, authority, schema, scope,
actor, semantic column and unit. Source-owner identity is
`simulated:DatumCo-local-source-owner`; controller identity is the trusted local
demo reviewer `reviewer:local-trusted`.

Final successful requests:

- Training: `request-ce276102148b44c18a1ddef088a6ca07`.
- Later: `request-5571915659664f5a8c608ca46818a826`, CSV SHA-256
  `210e584a89da89b748e6194ce4bdc9dd2d2c6a86c627fa967528ad197e360cdb`.
- After restart: `request-ee5de4ad6f5a45f998995938e0d16d77`, CSV SHA-256
  `2bba58e02f0165d9ba62209b00c1b6864880a6f5a677f75eb0fddc48743813e1`.

Earlier live evidence, including the blocked HTTP conflict request
`request-22576db4dc9a49b6b1878d79ded49a7b`, is retained under
`.local/live-learning/evidence/9c7b84fe2002445da64b538dc6663973/`.
Its earlier approved version is superseded, not deleted or silently reinterpreted.

## Launch, restart and stop (Windows)

Prerequisites: Python 3.12/uv, Node 22.12+ (tested Node 24), npm, Windows Task Scheduler.
Run from this feature worktree root:

```powershell
uv sync --locked --project backend
npm --prefix frontend ci
npm --prefix frontend run generate
$env:BACKEND_URL = 'http://127.0.0.1:8026'
npm --prefix frontend run build
powershell -NoProfile -File tools\local_learning.ps1 -Action Install
powershell -NoProfile -File tools\local_learning.ps1 -Action Start
```

`Install` generates distinct private local worker/controller/source-owner credentials
without printing them. They stay server-side in ignored
`.local/live-learning/demo-credentials.json`. Do not commit or paste that file.
The launcher forces loopback, mock payments and paid-model calls off, and uses Next's
supported standalone build. No public-host mode is enabled.

```powershell
powershell -NoProfile -File tools\local_learning.ps1 -Action Status
powershell -NoProfile -File tools\local_learning.ps1 -Action RestartBackend
powershell -NoProfile -File tools\local_learning.ps1 -Action RestartFrontend
powershell -NoProfile -File tools\local_learning.ps1 -Action Stop
```

Task names: `DataPact-Learning-backend-20261024` and
`DataPact-Learning-frontend-20261024`. They are current-user, on-demand tasks with
three failure restarts and no logon trigger. Task ownership is checked before actions.
The application and evidence survive terminal/chat closure. After login, use `Start`.
`Stop` retains the tasks, SQLite database, artifacts, approvals and credentials;
one-command rollback is `Start`. No database reset is needed for restart.

An actual stop test exposed orphaned child servers in the first launcher. The fix
binds the task action and descendants to a Windows kill-on-close Job Object before
spawning; children use `CREATE_NO_WINDOW`. Both a child/grandchild regression and
actual task stop/start verified cleanup. No unrelated process was stopped.

## Operate through the app

1. Open `/live` and **Source learning**. Receive a typed synthetic source-bundle JSON
   with two disjoint source partitions covering the existing SF registry.
2. Create an ordinary brokerage request in the existing Agreement panel. The normal
   worker discovers missing source meaning and records source-owner review requests.
3. The simulated source owner chooses each count column and supplies its explanation
   in the learning panel. Each resolution resumes the same intake automatically.
4. Derive the composed procedure. Qualify it on fresh cases. The controller explicitly
   approves and activates the passing version using separate controls.
5. Receive a genuinely new batch, preserving unchanged authority bytes, then create a
   new ordinary request. The worker automatically retrieves the active version.
   No harness, manual rule injection or per-order restart is needed.
6. Accept the new server quote and explicitly authorize mock funding separately.
   Inspect the delivered dataset and the actual learning events/comparison.

Changed authority is a real invalidation, not a cue to force reuse. New authority
requires fresh evidence and qualification. A resolution can prepare its own order
before global activation, but that is not mislabeled as reuse of an older version.

For a reproducible HTTP demonstration in a fresh application database:

```powershell
uv run --locked --directory backend python ../tools/live_learning_demo.py prepare
# Use the returned evidence directory as SESSION below.
node frontend/scripts/live-learning-ui.cjs owner SESSION
uv run --locked --directory backend python ../tools/live_learning_demo.py finish-training --session SESSION
node frontend/scripts/live-learning-ui.cjs approval SESSION
uv run --locked --directory backend python ../tools/live_learning_demo.py later --session SESSION
powershell -NoProfile -File tools\local_learning.ps1 -Action RestartBackend
uv run --locked --directory backend python ../tools/live_learning_demo.py after-restart --session SESSION
node frontend/scripts/live-learning-ui.cjs inspect SESSION
uv run --locked --directory backend python ../tools/audit_live_learning.py SESSION
# Optional final counterexample; leaves current source authority conflicted:
uv run --locked --directory backend python ../tools/live_learning_demo.py conflict --session SESSION
```

The UI test uses an isolated headless installed Edge (`PLAYWRIGHT_CHANNEL` may select
another installed supported channel). It clicks the real owner/controller controls.
The HTTP driver supplies source bytes and ordinary order/quote/funding commands only.
For repeated demonstrations in the same retained DB, choose unused source versions
with `prepare --start-batch N`; never overwrite or delete the previous evidence.

## Safety, implementation and verification

The integration reuses `SourceKnowledge`, `InstitutionalMemory`, request-local
preparation, `im_records`/`im_state`/`im_active`, existing command receipts, the ordinary
catalog worker, run events, acceptance and payment gates. No second ledger, research
service, executable learned code, paid AI dependency or external dataset was added.

- Only explicit controlled-local mock startup enables this profile. Non-loopback
  clients are rejected, and source-owner/controller/worker credentials differ.
- Candidate fields and primitives cannot alter price, accepted scope, consent,
  capture/refund authority or financial policy. Each order still needs acceptance
  and funding; historical accepted snapshots remain unchanged.
- Exact source/authority/schema/scope pins and owner grants constrain each component.
  Conflicting retained resolutions block even if the conflicting component is not
  approved. Current public definitions remain available to the competent baseline.
- Activation requires a passing qualification bound to candidate and implementation,
  controller approval, and an unchanged previous active version. Code changes disable
  reuse until requalification; stale versions remain inspectable/revocable.
- Source selections stay request-local across clarification and idempotent retries.
  The bounded source-pin limit is 24 to retain all multi-part evidence; required
  coverage, suppression and financial checks are not removed.
- Independent shadow assessments are stored in a separate stateless scope and never
  become source-owner training evidence. Old nine-case/109-case/negative experiments
  are not training inputs and were not overwritten. The original operational trace
  still hashes to `f98b2bc9e05ce6382140344d2d261e02d72b9c9ede899f8259d3101be18719d9`.

Observed checks: 369 catalog/dataset/worker/source-learning integration tests passed;
the final authority-pin regression and final focused set passed 52 tests. Frontend:
123 tests, generated-client check, TypeScript and production build pass. Real owner,
approval and inspection UI runs report zero page errors. Read-only live audit passes.
The whole repository suite was not rerun for this feature; the earlier documented
16 Windows baseline failures have not been hidden or claimed fixed.

```powershell
uv run --locked --directory backend pytest tests/source_learning tests/catalog tests/dataset tests/runtime/test_catalog_worker.py ../evals/source_learning/test_source_knowledge.py
uv run --locked --directory backend ruff check . ../tools/learning_examples.py ../tools/live_learning_demo.py ../tools/local_learning_process.py ../tools/audit_live_learning.py
uv run --locked --directory backend ruff format --check . ../tools/learning_examples.py ../tools/live_learning_demo.py ../tools/local_learning_process.py ../tools/audit_live_learning.py
npm --prefix frontend run generate:check
npm --prefix frontend run typecheck
npm --prefix frontend test
```

This demonstrates persistent, approved institutional source learning in a running
controlled application. It does not establish unrestricted production readiness,
general-purpose self-improvement, real human labor savings or real commercial history.
