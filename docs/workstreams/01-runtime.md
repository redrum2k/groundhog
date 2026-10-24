# Catalog execution and orchestration handoff

Base commit: `ac385a1abf1ce66dfd1f792cac021cfa5286d7ae`.
Branch/worktree: `codex/catalog-runtime`, `order-to-cash-runtime`.
The worktree was clean at entry. Work stayed within this conversation's ownership.
No pushes, merges, paid model calls, broadcasts, deployments, private databases or `.env`
files were used. All execution evidence below is offline and synthetic.

## Files

| File | Change |
| --- | --- |
| `backend/app/runtime/catalog_worker.py` | New synchronous `CatalogWorker(service).run_once() -> bool` selector. |
| `backend/app/storage/catalog_dispatch.py` | Additive private compilation dispatch history and leases. |
| `backend/app/runtime/background.py` | Independent background lanes and draining shutdown. |
| `backend/app/main.py` | Lifespan wiring for catalog, payments, invoice execution and both deadline sweeps. |
| `backend/app/agents/gateway.py` | Transport limits and redacted timing/outcome diagnostics; no semantic prompt changes. |
| `backend/tests/runtime/test_catalog_worker.py` | Offline compilation, funding, consent, restart, concurrency, stale-result and budget tests. |
| `backend/tests/runtime/test_catalog_lifespan.py` | Automatic application execution, lane isolation, shutdown/ownership and redaction tests. |
| `backend/tests/runtime/test_catalog_gateway.py` | SDK configuration, input bound and transport redaction tests. |
| `docs/workstreams/01-runtime.md` | This handoff. |

No changes to `orders/catalog.py`, `payments/catalog.py`, `runtime/catalog_policy.py`,
payment journal/executor/transport, Jeff's semantic implementations, public DTOs/endpoints,
frontend, shared handoff/status documentation or existing test assertions.

## Entry point and configuration

```python
from app.runtime.catalog_worker import CatalogWorker

worker = CatalogWorker(service)  # An ordinary CatalogService; defaults work unchanged.
did_attempt = worker.run_once()
```

One invocation selects at most one compilation or job attempt, or observes one unowned
compiler reservation. It returns `False` when idle. A `True` result means an attempt or
observation occurred, not that a delivery succeeded. The worker alternates draft/job
priority and rotates order selection. It calls `compile_request` and `run_one`; existing
service methods retain all claim, result, policy and financial authority.

`create_app` enables workers by default. `run_worker=False` (and the existing `worker=False`
compatibility alias) disables background consumption. No new environment settings or
public routes are needed. The existing database path and artifact-root configuration apply.

Five independent lanes run off the application event loop, with five available thread slots:

- Catalog and invoice deadline sweeps: each every 1 second.
- Catalog: one `run_once()` attempt, then 0.25 seconds.
- Payments: existing `payments.work(limit=1)`, then 0.25 seconds.
- Invoice: existing async `jobflow_worker.run_once`, executed with a thread-owned event loop,
  then 0.25 seconds. Existing invoice recovery remains in place.

Intervals begin after each attempt finishes. Failures in one lane do not skip another lane's
sweep. The process still uses the existing single-application-worker advisory lock. On graceful
shutdown, selection stops and active calls drain before that lock is released. Cancelling an
async wrapper does not abandon a still-running synchronous call. Hard process loss leaves
the durable service/dispatch leases for recovery.

Paid calls still require `ENABLE_PAID_MODELS=true` plus an explicitly configured `CLAUDE_MODEL`.
The SDK has zero automatic retries and a 20-second timeout; every parse also receives that
timeout and the 4,096 output-token limit. The 50,000-character bound now includes the system
instruction and serialized evidence/customer payload. Existing typed contexts, resolved
evidence allowlists and citation validation remain unchanged. No model tools were added.
Logs contain identifiers, stage, candidate attempt, elapsed milliseconds and categorical
outcome; exception bodies, document contents and credentials are omitted. A candidate attempt
can be rejected before a model/job runs, so logs are not usage accounting; persisted service
counters are authoritative.

## Request to finding to lifecycle

A customer request becomes a persisted draft. The worker notices a compiling draft and
reserves a private dispatch lease. `compile_request` commits its revision and spent-call
counter before extracting the allowed sources and invoking the compiler. It then checks the
current revision and deadline before saving a clarification or specification. A customer answer
makes that same draft eligible again, without extending its original deadline. A ready draft
still needs an explicit server quote and customer acceptance.

Acceptance creates an immutable order and a blocked job. Buyer authorization and confirmed
funding are separate steps. The independent payment lane processes the existing bounded
entry point; only a current funded order is selected for execution. `run_one` atomically claims
the job, runs Jeff's source extraction/verification/document/investigation implementations,
then applies their result through the existing lease and evidence-binding checks.

Those service methods persist verification reports and semantic findings. They may request
evidence, wait for both required consents, publish a verified PDF, or escalate to human review.
An evidence upload or answer changes the binding and makes old results inapplicable. Approved
repair queues a current recheck; it does not alter the accepted agreement. Publication starts
the existing 60-second review. Findings themselves do not authorize payment; deterministic
service settlement gates and the payment layer retain that responsibility.

## Durability and recovery

`catalog_compile_dispatch` is an additive private table with an index, storing dispatch token,
request ID, expected revision, candidate attempt, lease expiry and outcome. Its creation does
not rewrite public records, historical commands, payment obligations or schema versions.
Claims serialize using the repository's existing SQLite transaction mechanism. No transaction
is held across compiler, PDF or model execution by the new code.

Compilation dispatch leases last 45 seconds. After interruption, the persisted compiler-call
reservation stays spent. A partial saved command response is never treated as completion.
After lease expiry, recovery uses a fresh command at the current revision, which makes an older
completion stale. An unfinished compile started through the existing internal endpoint is
recognized by its compile-command fingerprint and reserved response; on first observation it
gets a 45-second wait, not an immediate extra model call. Clarification responses are excluded
from this detection.

The service owns the four-call/three-question/300-second draft limits and the three-attempt/
45-second job leases. Failed PDF jobs remain failed until the existing explicit retry command;
the scheduler does not manufacture a replacement job. Expired running jobs recover through
`claim_job`, and an old lease cannot publish after replacement. Funding, evidence, consent,
human-review and historical-order gates remain closed to automatic work.

An uncertain fourth compiler call is left pending until its original deadline; there is no
fifth model call. The deadline service invalidates it and escalates. This avoids an existing
service race described below while preserving the consumed budget and original deadline.

## Validation actually run

- `uv sync --locked --project backend` succeeded. The initial sandbox denied access to uv's
  global cache; the same sync succeeded with approved cache access. Subsequent checks used
  `UV_CACHE_DIR=/private/tmp/catalog-runtime-uv-cache`.
- `uv run --locked --directory backend pytest tests/runtime tests/api/test_merged_runtime.py
  tests/investigation/test_gateway.py`: 37 passed before the final additional edge tests.
- `uv run --locked --directory backend pytest`: final full suite **317 passed in 37.51s**.
  An earlier full run also passed 315 tests before the last two worker edge tests were added.
- `uv run --locked --directory backend pytest tests/runtime`: 28 passed, including all final
  runtime tests.
- `uv run --locked --directory backend ruff check .`: passed.
- `uv run --locked --directory backend ruff format --check .`: passed, 101 files formatted.
- `git diff --check`: passed.

Temporary databases and generated fixture artifacts are used throughout. Injected compiler
and assessor outputs, clocks, thread events and fake SDK clients provide the evidence; there
are no long timing sleeps or paid calls. Demonstrated behavior includes:

- Initial compilation and post-answer compilation, including a full lifespan journey through
  explicit mock funding to one verified delivery without internal work calls.
- No work before funding confirmation, while awaiting evidence, or after only one of two
  required approvals; automatic resumption after eligible evidence/consent changes.
- Spent compiler budgets across restarts, three clarification rounds, unchanged deadlines,
  conservative observation of an interrupted manual compilation, and no fifth model call.
- Competing consumers, expired leases, one delivery despite late completion, job-attempt
  exhaustion, explicit operational retry and stale semantic findings rejected after an answer.
- Persisted assessor findings and at most two investigation questions, without extra deliveries
  or resetting the dispute deadline.
- Blocked/failing compilation and payment calls while catalog deadlines, invoice deadlines,
  invoice work and both HTTP surfaces remain responsive.
- Normal and cancelled shutdown retain worker ownership until active calls finish; lane
  failures remain redacted and retry without taking down other lanes.

## Integration requests and limits

1. **Conversation 3, compiler service edge:** in `CatalogService.compile_request`, the
   `compiler_calls >= 4` branch sets `human_review` without incrementing `draft.revision`, and
   result application checks revision/deadline but not `status == "compiling"`. Source review
   shows that a manual fifth compile request can mark a still-running fourth call exhausted
   without invalidating its eventual result. Please advance the revision on that terminal
   transition and require a compiling current status when applying the result. The automatic
   worker avoids that branch for an uncertain fourth call and waits for the original deadline.
   No edit to the owned service file was made here.
2. **Conversation 3, settlement integration:** preserve `run_one(order_id)` and atomic
   `claim_job`/completion gates, including funded-current-state checks. Keep
   `payments.work(limit=1)` a bounded synchronous entry point. RPC/model/PDF I/O must remain
   outside SQLite write transactions; independent threads cannot overcome a long-held
   database write lock. Extend payment/state gates in the owned service/policy, not here.
3. **Conversation 4:** integrate this additive private table and lifespan wiring with the other
   branches. Update shared API/status/handoff docs to describe automatic compilation and work;
   internal manual endpoints remain compatible. Re-run the whole suite after settlement/Base
   changes. This branch makes no claim about those branches or real testnet execution.

The scheduler selects by scanning stored catalog records, appropriate to the bounded local
demo rather than a production queue. One application's catalog lane is serial; competing
standalone consumers are fenced by durable service leases. An uncooperative injected function
or native call can prolong graceful shutdown because Python cannot safely kill its thread;
the process retains ownership until it returns. A forced process exit uses durable recovery.
No new production authentication, tenant isolation, distributed worker platform or payment
transport is provided.
