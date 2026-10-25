# Connected aggregate learning, dispute and settlement demonstration

Feature branch: `feature/judge-proof-order-to-cash-20261024`, based on main
`8b3b216f86963f2b002236d6e076ee13edaf3147`. No automatic main merge or hosted
activation is part of this task. The PR records the final tested commit and trace.

## What this demonstrates

`/live` uses one real aggregate backend, persisted order identities, source files,
accepted snapshots, ordinary worker, learning approvals, dispute assessments and
the existing mock payment journal. There are no injected verdicts, prerecorded
learning events, new payment adapters or paid model calls.

The simulated buyer first asks an ambiguous natural-language question. Two
independently evidenced simulated source-owner corrections resolve source meaning
during intake. The buyer answers the category clarification, receives a fully
pinned quote, explicitly accepts it and separately authorizes mock funding.
Source meaning is resolved **before** quote acceptance: the demo does not accept
an ambiguous financial agreement and silently reinterpret it later.

After verification and explicit buyer review, the first order captures once. A
controller qualifies the evidence-derived composed procedure on fresh engineering
cases, approves it and explicitly activates its version. Later orders contain new
source bytes with matching authority; the normal worker reuses that version without
another source-owner review. The same-byte stateless comparison remains separate
from training history.

The next buyer challenges possible cross-ZIP double counting. Aggregate bytes do
not establish that additional claim. The application records complaint-specific
`UNKNOWN` assessments, asks at most two evidence questions and holds payment. A
simulated controller explicitly approves return of uncaptured mock funds, without
rewriting the factual result. A stale controller binding is first rejected. The
return books once; that disputed order is never captured.

The backend restarts, exact earlier commands are replayed, and another new order
reuses the same approved version. Separate fresh cases demand extra scope and
publish conflicting, revoked and expired authority. None silently broadens a
contract or authorizes payment. Authority counterexamples deliberately leave their
intakes held; the existing positive orders and evidence remain inspectable.

`/` remains Lucas's **separate retained broker demonstration**. The smoke creates
a real compatibility run and observes its backend events, but never counts that
run as the aggregate learning transaction. Its readiness probe now checks the
actual local identity capability, not just `/health`. The launcher enables those
simulated identities only in the loopback, mock-only local environment.

## Reproduction (Windows, fresh instance)

Prerequisites: uv/Python 3.12, Node 22.12+ and Windows Task Scheduler. Run from this
worktree root. Choose unused ports and a new instance name; never reset a prior DB.

```powershell
uv sync --locked --project backend
npm --prefix frontend ci
$env:BACKEND_URL = 'http://127.0.0.1:8041'
npm --prefix frontend run build
powershell -NoProfile -File tools\local_learning.ps1 -Action Install -Instance judge-demo-NEW -BackendPort 8041 -FrontendPort 3041
powershell -NoProfile -File tools\local_learning.ps1 -Action Start -Instance judge-demo-NEW -BackendPort 8041 -FrontendPort 3041
uv run --locked --directory backend python ../tools/judge_journey.py --instance judge-demo-NEW
# Audit the exact output directory printed above:
uv run --locked --directory backend python ../tools/audit_judge_journey.py OUTPUT_DIRECTORY
```

Open `http://127.0.0.1:3041/live`. Use **Source learning** / **Learning active** to
inspect owner records, procedures and actual events. The original demo on 3026/8026
and its tasks/data are not replaced. Instance-specific task names, ports, credentials,
database and artifact directories are checked before actions. Existing instance
configuration cannot be silently retargeted.

The owner walkthroughs are explicit synthetic **training input**, separate from the
driver: [judge-owner-walkthroughs.json](examples/judge-owner-walkthroughs.json).
`--owner-walkthroughs PATH` supplies different testimony; `--objection TEXT` supplies
the buyer's actual allegation. Neither supplies a runtime verdict or cached final
dataset. The driver observes supported dispositions or bounded investigation; it
does not insert a result into the application.

Restart or stop only this instance, retaining all evidence and credentials:

```powershell
powershell -NoProfile -File tools\local_learning.ps1 -Action RestartBackend -Instance judge-demo-NEW -BackendPort 8041 -FrontendPort 3041
powershell -NoProfile -File tools\local_learning.ps1 -Action Stop -Instance judge-demo-NEW -BackendPort 8041 -FrontendPort 3041
# Rollback for Stop: the same command with -Action Start.
```

Scheduler owns service lifetime/restarts; hidden child processes are bound to the
existing Windows kill-on-close Job Object. No open terminal/chat is the supervisor.

## Inspectable evidence

Each run creates a new ignored `.local/live-learning/INSTANCE/evidence/UUID/`:

- `report.json`: actual commit, dirty-tree disclosure, instance, run/order/snapshot
  identities, active version, restart process identities and completed/failed state.
- `http-trace.jsonl`: chronological real frontend-bridge/backend commands and saved
  responses, without credential headers. Replays retain their exact keys/payloads.
- `*-source.json`, `owner-walkthroughs.json`: clearly simulated supplied evidence.
- `*-quote.json`, `*-unfunded.json`, `*-delivered.json`, `*-final.json`: distinct
  agreement/funding/delivery/settlement boundaries for the same order identities.
- `*-delivery.csv/json`: actual downloaded immutable bytes, not reconstructed rows.
- `*-events.json`: complete paginated durable streams, including >100-event cases.
- `later-investigation-*.json`, `later-held.json`, `later-after-restart.json`:
  evidence requests, unresolved hold, controller/financial effects and persistence.
- `independent-audit.json`: read-only SQLite/source-byte/financial verification.

The independent audit does not call runtime normalization, verdict or settlement
code. It reopens source and owner-proof bytes by hash; checks content-addressed
learning records; recomputes all rows from the recorded owner-defined columns;
checks accepted source pins, CSV/JSON agreement, suppression and scope; and joins
orders to actual payment operations/effects and event sequences. It checks one
funding and one terminal operation per funded order, one booking, no premature
capture, no capture on the unresolved case, and exact replay across restart.

No database, credentials, raw transaction capabilities or generated dataset is
committed or uploaded in the PR. Evidence remains on the local machine; the PR
provides a sanitized summary and exact paths/IDs. This is not an independent human
evaluation or a claim about measured labor savings.

## Failures found and repaired

The unmodified-main probe completed the aggregate learning/fulfillment/hold/return
cycle, but the compatibility session endpoint returned `404 Local demo is disabled`.
The frontend's generic health probe still advertised readiness. The launcher and
capability probe now agree about the actual service required by `/`.

Adversarial HTTP regressions found the default offline assessor wrongly dismissed
both a compound yoga/deduplication allegation and a present-but-duplicated ZIP
allegation as `FAIL`. It used keyword/row-presence heuristics, bypassing the durable
assessment path. The default path now uses the existing whole-claim independent
evidence certificate and the same persisted attempt/recovery machinery. Unsupported
qualifiers remain `UNKNOWN`; known predicates can be explicitly rule-settled.

Preserved baseline evidence directories under this worktree:

- `.local/baseline-2aa4fd72c7cf48139abbb30724dcd0aa`: the probe's guessed requirement
  ID was correctly rejected; this was a driver mistake, not a backend defect.
- `.local/baseline-df8ef6235d85423bb996fdbae467fc38`: the probe failed to paginate
  beyond 100 of 123 events; again a driver error, fixed without weakening the API.
- `.local/baseline-4e44fb11feea4617b08e41965c6c2c6b`: corrected unmodified-main probe
  completed, retaining the genuine compatibility-session failure.
- `.local/live-learning/judge-proof-20261024/evidence/0228f88ba9d64787a64b0155f943109c`:
  initial **dirty-worktree development** HTTP/audit success. Its base HEAD is not
  asserted to be the executed final code. The final clean-commit run is in the PR.

| Required attack | Evidence |
| --- | --- |
| Unsupported scope / no complaint fee | Actual `scope-change` HTTP case; accepted snapshot and amount unchanged, no child order |
| Wrong delivered values | `test_wrong_delivered_values_are_rejected_then_corrected_once_via_worker_api`; valid-hash corrupted CSV is withheld, one correction, repeated work cannot duplicate output |
| Unresolvable or composite allegation | Actual later-order hold plus two formerly failing composite-claim HTTP regressions |
| Changed/conflicting/expired authority | Three fresh HTTP intake holds plus existing source-learning scope/pin regressions |
| Stale controller binding | Actual 409 before valid return approval, no ledger effect |
| Retry/interruption/restart | Real scheduler restart; exact command replay; `test_default_assessment_survives_interruption_and_public_worker_retry` preserves completed work after lease reclaim |

The earlier nine-case, 109-case and negative experiments are not training inputs and
are untouched. No financial policy, accepted deadline, privacy threshold, refund
implementation, payment rail or paid-model authorization is changed.

## Verification commands

```powershell
uv run --locked --directory backend pytest tests/source_learning tests/dataset tests/catalog tests/runtime/test_catalog_worker.py tests/payments/test_catalog_settlement.py ../evals/source_learning/test_source_knowledge.py
uv run --locked --directory backend ruff check . ../tools/judge_journey.py ../tools/audit_judge_journey.py ../tools/local_learning_process.py
uv run --locked --directory backend ruff format --check . ../tools/judge_journey.py ../tools/audit_judge_journey.py ../tools/local_learning_process.py
npm --prefix frontend run generate:check
npm --prefix frontend run typecheck
npm --prefix frontend test
# A separate build output avoids touching a running local frontend:
$env:BROKER_BUILD_DIR = '.next-broker-production'
npm --prefix frontend run build
```

The full journey uses mock funding and rules/abstention, not a live LLM. Hosted
authentication/tenant isolation, unrestricted learning activation, real Base
settlement and human productivity validation remain outside this demonstration.
