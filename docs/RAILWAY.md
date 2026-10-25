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
