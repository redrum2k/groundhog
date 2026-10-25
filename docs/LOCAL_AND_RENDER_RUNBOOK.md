# Brokerage end-to-end validation: local first, Render second

This is the post-06/07 run plan, prepared October 24, 2026. It is not a claim that
the unfinished brokerage canvas has passed end-to-end testing or been deployed.
Use the final workstream 06 handoff for any new fixture, bridge-mode or signing UI
settings. The commands below use the existing Python/uv and Next.js entry points.

## Current checkpoints and what must finish

- Backend integration: `39dd58602b3f8ac0a7906b4db4ddbbdb57b3d981`.
- Jeff and Lucas are integrated into the migration branch at `41ecf61`; at this
  inspection, workstream 06 still has uncommitted implementation work.
- Payment readiness completed at `f8a929a7fab2ac10ffee2a0aca112ca93a72fb2d`.
  Its handoff reports 169 payment tests and 27 offline CLI processes passing.
  Public RPC preflight and observed testnet transactions remain unperformed.
- The final combined branch must include that payment-readiness commit. Let the
  migration owner integrate it in their worktree; do not merge into an actively
  edited checkout from a separate conversation.

Before calling 06 complete, its handoff must provide these concrete details:

1. Exact final commit and the synthetic dataset/authority/coverage registration
   command, or an explicit statement that registration happens automatically.
2. Every server-only environment variable needed for the local runs bridge,
   including how trusted local-demo access is enabled. Do not guess a flag name.
3. The actual browser URL/control for backend mode, creation and reload/resume;
   mock funding, quote acceptance and any scripted-buyer harness must be explicit.
4. Exact backend and browser acceptance commands against a fresh database, with
   expected outcomes for clean delivery, correction, Oakland and yoga.
5. Exact generated-contract freshness commands and where screenshots, event traces,
   artifact hashes and final order/payment/ledger state are saved.

Until these details exist, starting two HTTP servers only verifies startup. The old
root canvas defaults to recorded playback, its old "live" mode uses `/api/run-stub`,
and `frontend/scripts/acceptance.cjs` tests the invoice workbench with Microsoft Edge.
Neither is brokerage end-to-end evidence. Do not reuse that invoice script as a
broker acceptance claim or silently widen its localhost restriction for Render.

## 1. Select the completed combined code

After 06 finishes and incorporates 07, run from the original repository:

```sh
git status --short
git log -1 --oneline codex/data-broker-migration
git merge-base --is-ancestor 39dd58602b3f8ac0a7906b4db4ddbbdb57b3d981 codex/data-broker-migration
git merge-base --is-ancestor 5c8dc726326bb9e3539cdb51e5aec221868223bc codex/data-broker-migration
git merge-base --is-ancestor f8a929a7fab2ac10ffee2a0aca112ca93a72fb2d codex/data-broker-migration
```

All ancestry checks must exit 0. If one fails, integration is unfinished. Use the
owner's reviewed final commit if the branch has subsequently moved. Do not start
from the old local `main`, and do not reset another worktree.

Create an isolated test checkout from that completed branch (only if this path
does not already exist; otherwise inspect the existing checkout first):

```sh
git worktree add --detach ../order-to-cash-e2e codex/data-broker-migration
cd ../order-to-cash-e2e
git rev-parse HEAD
```

Keep this checkout free of existing private `.env` files, wallets and databases.
Next.js can load `.env` files automatically, so a clean checkout matters. Use
Python 3.12+, uv and Node 24; integration previously tested Node 24.14.1. Install
dependencies once, from the test checkout root:

```sh
uv sync --locked --project backend
npm --prefix frontend ci
```

## 2. Start the local mock backend and frontend

In terminal A, from the test checkout root:

```sh
export OTC_DEMO_DIR="$(mktemp -d "${TMPDIR:-/tmp}/otc-demo.XXXXXX")"
export ORDER_DB_PATH="$OTC_DEMO_DIR/orders.sqlite3"
export ARTIFACT_ROOT="$OTC_DEMO_DIR/artifacts"
export PAYMENT_ADAPTER=mock
export ENABLE_TESTNET_BROADCAST=false
export ENABLE_PAID_MODELS=false
export JOBFLOW_ANTHROPIC_MAX_CALLS=0
export JOBFLOW_DEMO=1
export INTERNAL_API_TOKEN=local-only-worker
export REVIEWER_API_TOKEN=local-only-reviewer
printf 'Fresh local demo data: %s\n' "$OTC_DEMO_DIR"
```

These two token values are deliberately public localhost-only test values. They
must differ. Use independently generated private credentials for hosting. Set any
additional local-demo flag documented by 06, and run its synthetic-source setup
command using these same absolute paths, before starting the backend:

```sh
uv run --locked --directory backend uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 1
```

One backend process runs the API, durable workers, deadline sweeps and payment
reconciliation. Do not add a second worker service or use multiple Uvicorn workers.
Avoid `--reload` during restart/deadline acceptance testing. `JOBFLOW_DEMO=1` enables
legacy local identities; it is not a substitute for 06's new bridge access setting.

In terminal B, from the same test checkout root:

```sh
export BACKEND_URL=http://127.0.0.1:8000
export INTERNAL_API_TOKEN=local-only-worker
export REVIEWER_API_TOKEN=local-only-reviewer
export NEXT_TELEMETRY_DISABLED=1
cd frontend
```

Set the exact local bridge-mode setting from 06 in this terminal too if required,
then start Next:

```sh
npm run dev
```

Open **http://127.0.0.1:3000/** for the brokerage canvas. `/jobflow` is the preserved
invoice workbench. Backend docs are **http://127.0.0.1:8000/docs**. Verify startup
in a third terminal:

```sh
curl --fail --silent --show-error http://127.0.0.1:8000/health
curl --fail --silent --show-error http://127.0.0.1:8000/openapi.json > /tmp/otc-openapi.json
curl --fail --silent --show-error http://127.0.0.1:3000/ > /dev/null
```

Check that OpenAPI contains `/runs`, `/runs/{id}/events` and
`/runs/{id}/decisions`. In browser Network, the backend-mode canvas must use the
new same-origin bridge, not `/api/run-stub`. Health must show mock payments with
live settlement disabled. A health response does not prove a completed order.

## 3. Prove the user journey

Use 06's real persisted command flow and explicit synthetic fixtures. Do not use
a browser-selected ending to manufacture a verdict. Record run/order IDs so that
reload and restart inspect the same work.

| Exercise | Required result |
| --- | --- |
| Request SF adults 25–34 interested in fitness, grouped by ZIP | Persisted draft and any clarification; server quote shows $120 and exact accepted requirements. |
| Accept quote, stop before funding | No fulfillment job runs. Acceptance alone does not hold funds. |
| Explicitly simulate funding | Exactly one job runs; payment is visibly mock, without hash or explorer link. |
| Open delivery | Downloaded CSV agrees with JSON preview; all expected ZIPs accounted for, stable citations resolve, suppressed counts are null and never leaked. |
| Review then settle | No capture on verification alone. Current acceptance or undisputed server review expiry permits one mock capture and one corresponding booking. |
| Missing 94110 fixture | Independently detected; a provider-fault fixture permits one free correction and a new review. A source-only defect does not spend it. |
| Oakland request | Separate $60 offer/acceptance/order/funding; no expanded work before funding. |
| Yoga complaint | Supported conclusion or a bounded question/human handoff. Only a separately accepted expansion is billable at $30. |
| Reviewer actions | Approve/reject/ask/escalate respect available actions, exact binding, reason and evidence. A stale action gets 409 and needs another deliberate action. |
| Reload/restart | Same run, events, artifacts and payment identity; no duplicate jobs, effects or bookings. |
| Backend outage | Visible failure/waiting, with no successful stub fallback. |

Open a second browser tab to exercise stale bindings. For backend restart, stop
terminal A and rerun only the Uvicorn command in that same shell: retain the same
`ORDER_DB_PATH` and `ARTIFACT_ROOT`. Do not rerun `mktemp` for this test. Deadlines
continue across downtime; an expired order may truthfully remain unresolved.

Use injected-clock/RPC tests for cutoff equality, late disputes, slow funding,
pending/uncertain capture and confirmed parent-return dependencies. Do not change
the computer clock or use real broadcasts to test those cases.

## 4. Automated acceptance and production-build smoke

Reuse passing results for the exact final tree. If 07 or other fixes were integrated
after that test run, run the combined checks again. From the test checkout root:

```sh
uv run --locked --directory backend pytest
uv run --locked --directory backend ruff check .
uv run --locked --directory backend ruff format --check .
backend/.venv/bin/python spikes/payments/examples.py
npm --prefix frontend run generate:check
npm --prefix frontend test
npm --prefix frontend run typecheck
```

Also run the catalog/OpenAPI and new run-client freshness checks listed by 06;
the older `generate:check` script alone only covers its listed schema exports.
Run the new brokerage browser acceptance command from 06, with its documented
browser dependency, while the real backend and Next server are running.

To smoke-test a production frontend locally, stop `npm run dev` in terminal B,
keep its backend URL and server-only settings, then run from `frontend`:

```sh
npm run build
mkdir -p .next/standalone/.next
cp -R .next/static .next/standalone/.next/
if [ -d public ]; then cp -R public .next/standalone/; fi
HOSTNAME=127.0.0.1 PORT=3000 node .next/standalone/server.js
```

This exercises the standalone server used by the existing Docker image. Its static
assets must be copied alongside it; see the official
[Next standalone-output instructions](https://nextjs.org/docs/app/api-reference/config/next-config-js/output).

Repeat clean creation, reload, evidence access and a reviewer action. If the bridge
intentionally rejects production mode, record that deployment gap; do not remove
the guard or label the dev-only result production-ready. The existing Next rewrites
compile `BACKEND_URL` at build time, so set it before both build and start.

Save the final commit, exact commands, browser errors, run IDs, event cursor replay,
delivery hashes, final checks and payment/ledger results in 06's handoff. The lab
examples prove isolated payment mechanics, not the connected brokerage UI.

## 5. Render layout and remaining prerequisite

Local testing is the immediately supported target. As scoped, 06 only guarantees
a trusted local-demo bridge. Interactive hosted testing needs an implemented and
tested protected demo login/access boundary for every exposed mutation, plus
authorized actor mapping in the server bridge. Keeping service tokens server-side
does not authenticate whoever can call that bridge.

The current legacy `/api/jobflow/sessions` route explicitly rejects non-loopback
clients. Do not solve a Render 403 by disabling this check, spoofing localhost, or
publishing demo session creation. A private backend still needs a protected public
frontend. Keep legacy demo session creation disabled on Render. If 06 has no hosted
access implementation, report Render interactive testing as blocked on that small,
separate deployment task; continue using the local demo.

Once that prerequisite is met, the proposed layout is:

Browser -> authenticated Next web service -> private FastAPI service -> SQLite
and artifacts on that backend's persistent disk. Use the existing Dockerfiles.

| Setting | Backend | Frontend |
| --- | --- | --- |
| Render type | Paid, always-on Private Service | Web Service with server-side Next routes; always-on for a reliable demo |
| Region/workspace | Same as frontend | Same as backend |
| Source | Reviewed combined commit, pushed only when authorized | Same reviewed commit |
| Root directory | `backend` | `frontend` |
| Runtime | Docker | Docker |
| Dockerfile/context relative to root | `./Dockerfile` / `.` | `./Dockerfile` / `.` |
| Start | Existing CMD: Uvicorn on `0.0.0.0`, one worker | Existing CMD: `node server.js`, host `0.0.0.0` |
| Port | Set `PORT=8000` | Set `PORT=10000` |
| Storage | Persistent disk mounted at `/data` | No application database |
| Health | Default TCP probe; separately call `/health` from inside Render | HTTP path allowed by the access layer, without exposing privileged data |

Next needs a web service for its server routes, not a static-site deployment.
Root directory, Dockerfile and context behavior follow Render's
[Next.js](https://render.com/docs/deploy-nextjs-app),
[Docker](https://render.com/docs/docker) and
[monorepo](https://render.com/docs/monorepo-support) documentation. Private-service
health checks are TCP-only; HTTP health probes are available for web services.
[Health-check documentation](https://render.com/docs/health-checks).

Backend environment:

```text
PORT=8000
ORDER_DB_PATH=/data/orders.sqlite3
ARTIFACT_ROOT=/data/artifacts
PAYMENT_ADAPTER=mock
ENABLE_TESTNET_BROADCAST=false
ENABLE_PAID_MODELS=false
JOBFLOW_ANTHROPIC_MAX_CALLS=0
JOBFLOW_DEMO=0
INTERNAL_API_TOKEN=<new private worker credential>
REVIEWER_API_TOKEN=<different new private reviewer credential>
```

Frontend environment: set `BACKEND_URL` to `http://<backend internal hostname>:8000`
from Render's Connect/Internal panel, plus the matching server-only worker/reviewer
credentials and the implemented hosted-access configuration. Never use `NEXT_PUBLIC`
for privileged credentials. Render services in the same workspace/region can use
the private network; the browser continues calling its own Next origin.
[Private-network documentation](https://render.com/docs/private-network).

Set `BACKEND_URL` before the frontend image build as well as at runtime; the
existing Dockerfile declares its build argument. Render supplies service variables
as build arguments, but do not add secret ARG/ENV declarations that bake tokens
into the image. Rebuild the frontend if its compiled rewrite target changes.
[Docker environment-variable behavior](https://render.com/docs/docker).

Keep the API, worker and journal in one backend instance. Render disks are attached
to one service instance and unavailable during builds, pre-deploy commands and
one-off jobs. Run additive database initialization and any required idempotent
synthetic registration at service runtime or through the reviewed authenticated
setup path. Ensure 06's synthetic source assets are included by the Docker build;
the existing backend image copies `app`, not repository `tools` or `evals`.
[Persistent-disk documentation](https://render.com/docs/disks).

Do not use a Free backend for this durable demo: it sleeps after 15 idle minutes,
loses local state across restarts/spin-down and cannot attach a persistent disk.
That conflicts with SQLite persistence and continuously running deadline work.
[Free-instance limits](https://render.com/docs/free).

After deploying an explicitly approved commit, repeat the local acceptance matrix
through the protected hosted frontend. Verify a backend restart preserves the
same IDs, artifact bytes, deadlines and bookings; verify anonymous mutation requests
fail. Disk-backed redeployments have downtime, so test recovery rather than assuming
an uninterrupted review clock. No new authorization is created to hide downtime.

## 6. Real Base Sepolia validation is a separate milestone

Mock end-to-end can finish locally or on the protected Render setup without a
wallet, RPC endpoint or paid model. A working Render URL is not chain evidence.

For later explicitly authorized testnet work, follow
`docs/workstreams/07-payment-readiness.md` in the combined checkout. It contains
public preflight inputs, exact commands and matching-event/state evidence gates
for two independent 100000-atomic-unit (0.10 test-USDC) lab fixtures. It also records
the unresolved RPC/lease and crash-before-broadcast recovery limitations.

Then validate the application buyer-wallet path separately using the order's exact
accepted amount: the $120 demo order is 120000000 atomic USDC under the 1:1 demo
conversion. The lab's 0.10 payment cannot fund it. Backend buyer private keys are
not part of the app flow. Inspect pending and confirmed funding, fulfillment,
review and terminal reconciliation; only observed matching chain evidence permits
a real transaction hash/explorer link or confirmed-payment claim.

## What this preparation actually validated

Inspected committed integration, Dockerfiles, package scripts, configuration names,
local-demo authority checks, the old browser acceptance script, the active migration
status and the completed readiness handoff. Checked current official Render docs.
No private configuration/database was read; no server, Docker build, application
test suite, deployment or transaction was executed for this runbook. Final 06
fixture/mode/browser commands remain a required handoff, not invented commands.
