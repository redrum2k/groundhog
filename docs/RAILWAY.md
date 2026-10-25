# Railway: two-service hosted aggregate demo

Deploy `redrum2k/order-to-cash`, branch `main`, to two services in the **same
Railway project and environment**. This uses the checked-in Dockerfiles. The
frontend provides a browser password prompt and the backend stays private.

| Railway setting | Backend | Frontend |
| --- | --- | --- |
| Root directory | `/backend` | `/frontend` |
| Config file path | `/backend/railway.toml` | `/frontend/railway.toml` |
| Builder | Dockerfile | Dockerfile |
| Build / start overrides | Clear; use Dockerfile | Clear; use Dockerfile |
| Health check | `/health` | `/api/health` |
| Replicas | 1 | 1 |
| Persistent volume | Mount at `/data` | None |
| Public networking | None; remove public domain/TCP proxy | HTTPS domain, target port 3000 |

Keep backend serverless/app sleeping disabled: its background workers advance
reviews, deadlines and payment reconciliation. One backend process owns the SQLite
database and jobs. Do not add another worker service or replicas. Preserve any
existing backend volume; never initialize a replacement over existing order data.
Local `.env` files, SQLite databases and artifacts are ignored and are not uploaded
by a Git push. A fresh volume starts with fresh orders.

## Backend variables

Paste into Railway's Variables → Raw Editor, replacing the token placeholders:

```dotenv
PORT=8000
ORDER_DB_PATH=/data/orders.sqlite3
ARTIFACT_ROOT=/data/artifacts
MOCK_PAYMENT_DB_PATH=/data/legacy-mock-payments.sqlite3
PAYMENT_ADAPTER=mock
ENABLE_TESTNET_BROADCAST=false
ENABLE_PAID_MODELS=false
ENABLE_DATASET_MODEL_ASSESSMENT=false
ENABLE_BROKER_DISPUTE_ASSESSMENT=false
JOBFLOW_ANTHROPIC_MAX_CALLS=0
JOBFLOW_DEMO=0
INTERNAL_API_TOKEN=REPLACE_WITH_RANDOM_WORKER_TOKEN
REVIEWER_API_TOKEN=REPLACE_WITH_DIFFERENT_RANDOM_REVIEWER_TOKEN
```

Remove `SOURCE_LEARNING_MODE` if set: `controlled_local` rejects non-loopback
backend requests and is not a hosted feature. API keys, wallet private keys and
RPC credentials are unnecessary for this mock deployment. Paid models and live
testnet payments require their separately scoped configuration and authorization;
deploying this build does not enable either.

## Frontend variables

Use the backend's actual private networking hostname from Railway Settings →
Networking. If its service is named `backend`, it normally appears as below:

```dotenv
PORT=3000
HOSTNAME=0.0.0.0
BACKEND_URL=http://backend.railway.internal:8000
BROKER_HOSTED_DEMO=1
BROKER_LOCAL_DEMO=0
APP_ORIGIN=https://YOUR-FRONTEND.up.railway.app
DEMO_USERNAME=demo
DEMO_PASSWORD=REPLACE_WITH_RANDOM_DEMO_PASSWORD
INTERNAL_API_TOKEN=EXACT_SAME_WORKER_TOKEN_AS_BACKEND
REVIEWER_API_TOKEN=EXACT_SAME_REVIEWER_TOKEN_AS_BACKEND
```

`APP_ORIGIN` must exactly match the public browser origin: HTTPS, no path and no
trailing slash. When using a custom domain, use that domain and access the app
through it. `BACKEND_URL` must have no path; set it before the frontend build as
well as at runtime, because legacy Next rewrites are compiled at build time. The
Dockerfile already declares its build argument. Never prefix credentials with
`NEXT_PUBLIC_`. Worker and reviewer tokens must differ and match across services.

Generate **three separate values** locally with `openssl rand -hex 32`: one worker
token, one reviewer token, one demo password. The demo password must be at least
20 characters and differ from both API tokens. Store them only in Railway
variables (and a password manager), not in this repository or build arguments.
Only `BACKEND_URL` is needed as a build argument.

Railway variable references are optional. For a service literally named `backend`,
`BACKEND_URL=http://${{backend.RAILWAY_PRIVATE_DOMAIN}}:${{backend.PORT}}` and
`INTERNAL_API_TOKEN=${{backend.INTERNAL_API_TOKEN}}` avoid duplicate values; use
the equivalent reviewer reference. Substitute the actual case-sensitive service
name in these references.

## Public demo: real Claude calls, no wallet or browser password

Use a separate backend service/volume for a second demo so live orders retain their
original payment configuration. Both demo services still belong to the same Railway
project/environment. Do not change or delete the live service's database to build it.

On the mock-payment backend, use these overrides (keep the two API tokens):

```dotenv
PAYMENT_ADAPTER=mock
ENABLE_TESTNET_BROADCAST=false
ENABLE_PAID_MODELS=true
ENABLE_DATASET_MODEL_ASSESSMENT=true
ENABLE_BROKER_DISPUTE_ASSESSMENT=true
ANTHROPIC_API_KEY=YOUR_ANTHROPIC_KEY
CLAUDE_MODEL=claude-opus-5-5
APPLICATION_MODEL_BUDGET_PATH=/data/model-budget.sqlite3
APPLICATION_MODEL_BUDGET_USD=30
APPLICATION_MODEL_CONCURRENCY=1
APPLICATION_MODEL_FINAL_RESERVE_USD=0
APPLICATION_MODEL_CUTOFF_AT=2026-10-27T21:41:30-07:00
```

This is the user's $30 Railway model allocation, expiring October 27 at 9:41 p.m.
Pacific. Use one durable budget ledger for that allocation: if it is already running
in another service, migrate/reuse its existing ledger and preserve usage and grants;
do not create another $30 allocation just by duplicating an environment. Leave
`APPLICATION_MODEL_WINDOW_ID` unset for a fresh timed allocation. A budget already
bound to an older authorization cannot be extended by editing its environment.
Remove `SOURCE_LEARNING_MODE`; controlled learning remains local-only.
No wallet private keys or blockchain RPC are needed on this mock backend.

On its frontend:

```dotenv
BROKER_HOSTED_DEMO=1
BROKER_PUBLIC_DEMO=1
BROKER_LOCAL_DEMO=0
APP_ORIGIN=https://YOUR-DEMO-FRONTEND.up.railway.app
BACKEND_URL=http://YOUR-MOCK-BACKEND.railway.internal:8000
```

Keep matching `INTERNAL_API_TOKEN` and `REVIEWER_API_TOKEN` on both services.
`DEMO_USERNAME` and `DEMO_PASSWORD` are not needed in public mode. Every live bridge
request checks the backend's `/health` capabilities and refuses to forward to a
live-payment or unverified backend. Public legacy API routes are blocked; `/` and
`/live` are the supported workflow. HTTPS, exact host and same-origin writes remain
required. All visitors share demo controls and can consume the configured Claude
budget. Use only synthetic demo data; this mode has no per-user isolation.

The customer still explicitly accepts a quote and clicks **Simulate** to authorize
mock funding. No browser wallet is required, and payment results remain labeled mock.
For a visible processing beat on a hosted mock demo (Railway or Render), set
`MOCK_PAYMENT_DELAY_SECONDS=3` on the **backend** and deploy the updated frontend
and backend. Funding and capture remain genuinely pending for at least three seconds
after reservation; polling may add a little time. The default is 0, the maximum is 10.
The delay survives restarts without resetting, does not delay returns, and is ignored
in Base wallet mode. It never skips consent or extends payment or review deadlines.
Real model calls and mock payments are independent settings. For a password-protected
wallet-free demo, keep `BROKER_PUBLIC_DEMO=0` and the original login credentials while
using the same backend mock/model configuration.

If using a public backend URL, use `https://<domain>` without `:8080` or an `/api`
suffix. The domain's Railway target port must match the backend's `PORT` (for example,
change a target of 8080 to 8000 if `PORT=8000`). Public HTTPS transport is supported,
but private networking avoids exposing unauthenticated backend customer endpoints.

## Deploy and check

1. Configure the backend volume, settings and variables. Deploy the backend.
2. Configure the frontend domain, settings and variables. Deploy/rebuild the frontend.
3. `/api/health` should return `{"status":"ok"}` without a password. This only
   checks frontend liveness; it does not prove backend connectivity.
4. Open `/` in a fresh/private browser window. Sign in through the browser prompt
   using `DEMO_USERNAME` / `DEMO_PASSWORD`. Create a request, clarify, approve its
   quote and explicitly simulate mock funding. Verify delivery, review and mock
   capture, then reload to check persisted state.
5. Requests without the password must receive 401 on pages and `/api/live/...`.
   Cross-origin writes must receive 403. Server API tokens are injected only by
   the allowlisted live bridge and never sent to the browser.

All password holders share the trusted demo operator role, including reviewer
controls. This is not tenant isolation or per-user authorization. Keep the backend
private: several customer APIs intentionally have no customer authentication, so
a public backend would bypass the frontend password. Basic authentication requires
HTTPS at Railway's public edge. Controlled source learning remains local-only.
The hosted acceptance target is the aggregate workflow at `/` and `/live`;
legacy `/jobflow` bearer-token sessions are not supported by this Basic-auth gate.

For a 503, check credentials, `APP_ORIGIN`, and `BACKEND_URL`. For a 403, check the
browser hostname, exact Origin, and `BROKER_HOSTED_DEMO=1`. For a 502, check backend
health, its private hostname/port and that both services share an environment.
New Railway environments support private IPv4 and IPv6; this Dockerfile listens
on IPv4. An environment created before October 16, 2025 may be IPv6-only and needs
an IPv6 listener or migration to a current environment.

Railway setup references: [monorepo roots and config paths](https://docs.railway.com/deployments/monorepo),
[Dockerfiles and build variables](https://docs.railway.com/builds/dockerfiles),
[private networking](https://docs.railway.com/networking/private-networking/how-it-works),
[persistent volumes](https://docs.railway.com/volumes).
