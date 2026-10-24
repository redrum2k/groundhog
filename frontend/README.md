# OBJECTION — job-level workbench

Lucas owns presentation and PDF highlight display; Jeff supplies source coordinates.
Base-order financial policy follows [HACK.md v0.2](../HACK.md): server-driven
ten-minute review, independent authorization expiry, held unresolved disputes and
bounded free regeneration. Additional work requires its own accepted scope and
payment authorization. Follow the [shared checkpoint](../docs/INTEGRATION_CHECKPOINT.md).

Local-first Next.js / React / TypeScript frontend for the canonical
[`API_CONTRACT.md`](../API_CONTRACT.md). This V4 lane fills the previously empty
frontend; Lucas remains the team handoff owner. No backend schemas, root
dependencies, deployments or old V3 UI were imported.

## Start locally

Use Node 24 (tested with 24.14.0), npm, and uv. From the repository root, start the
**integrated jobflow backend** using its documented local demo settings
(`JOBFLOW_DEMO=1`). The scaffold-only backend in the initial UI worktree does not
yet implement `/api/jobflow`; frontend connection errors are real errors, not
replaced with fake application state.

For PowerShell, set `$env:JOBFLOW_DEMO = "1"` in that backend terminal first; for a
POSIX shell, use `export JOBFLOW_DEMO=1`. This is local-demo configuration only.

```sh
uv sync --locked --project backend
uv run --locked --directory backend uvicorn app.main:app --host 127.0.0.1 --port 8000
```

In another terminal:

```sh
cd frontend
npm ci
npm run dev
```

On Windows, use `npm.cmd` if PowerShell blocks the npm script shim. Open
http://127.0.0.1:3000. Choose a backend-registered **Local demo identity**, then use
**New Northwind case**. The backend creates the synthetic case and its stored
artifacts, events and financial state. A browser-selected role is never submitted
as authority. Tokens live in sessionStorage for this tab, not localStorage.

All API calls use `/api/jobflow` and the Next same-origin rewrite. The server-only
`BACKEND_URL` environment variable defaults to `http://127.0.0.1:8000`. Set it
before starting development or **before building** production; Next rewrites are
compiled at build time. Do not put backend credentials in browser environment
variables. Demo session endpoints must not be enabled on a public deployment.

## Verify

```sh
cd frontend
npm run generate:check
npm test
npm run typecheck
npm run build
```

`npm run generate` exports `ContractExport.model_json_schema()` using the locked
backend environment, then uses pinned `json-schema-to-typescript` to produce
`lib/jobflow.generated.ts`. The generator removes field-title naming collisions
and translates 2020-12 `prefixItems` into equivalent draft-07 tuples for the
compiler. It does not manually reproduce fields or change constraints. Generated
request-default fields remain optional. `generate:check` detects drift. Runtime
validation and all command authorization remain backend responsibilities.

Tests use explicit synthetic test fixtures (never bundled into production), not
hidden evaluation data. They cover disputed failures, original denominators,
correction bounds, acceptance independence, role affordances, stale citations,
question/thread binding, bounded traversal, exact mutation retries, 409 behavior,
session changes, late polling responses and read-only replay.

## Workflow

- Provider: correct failed original jobs within backend bounds. Inspect recorded
  attempts and new validated artifacts; correction never records customer acceptance.
- Customer: accept validated originals, open a dispute, answer the exact issue's
  question, accept/decline a quote, and separately accept the extra delivery.
- Investigator: run clearly labeled deterministic/scripted investigation, or choose
  Anthropic only when the backend reports model access. No model call runs on mount.
- Controller: answer internal questions, approve/decline exception proposals or
  record a reasoned handoff. Executor: execute an independently approved proposal,
  record simulated receipts or reconcile the existing UNKNOWN operation.
- Evidence & amendments: attach a bounded PDF/TXT/JSON/CSV as an unverified party
  assertion; record independent customer/provider signatures and an effective time.
  A signature does not automatically make a future amendment effective.

Processing, dispute, obligation and finance stay separate. Green means validated
and undisputed, not paid or accepted. The matrix denominator is the agreement's
original document count. Added scope and correction attempts do not inflate it.
Money cards and receipts use only returned financial balances and postings.

Every deliberate mutation has a unique key and the displayed expected revision.
Response-loss retries preserve its exact body. Other mutations and identity changes
pause while that response is uncertain. A 409 clears retry eligibility, shows the
conflict, and refreshes without resubmission. Polling is abortable, scoped to the
order/session, serial, revision-monotonic and event-ID-deduplicated.

Only persisted correction queue/start and successful validation events move the
procedural courier. Replay snapshots the existing event list and never executes a
request. Manual input/click/focus pauses opt-in auto-follow. Next unresolved captures
one bounded list, visits each entry once and stops; waiting issues require an
explicit next click. Reduced-motion keeps all information and controls usable.

## Evidence and accessibility

Check/finding citations show exact quoted text, locator, immutable source version
and full SHA-256. Stale citation version/hash/text is blocked. **Load verified
artifact** uses authenticated fetch, verifies the actual bytes, and creates a
revocable blob URL. PDFs open at the cited page, with an embedded inspection view
and a separate open/download link. Field citations render an authenticated,
hash-bound source-page image with a normalized rectangle overlay.

Radix Dialog supplies modal focus trapping, Escape dismissal, title/description
semantics and return focus. Native buttons/forms, visible focus rings, labeled
inputs, arrow-key matrix navigation and a skip link cover the rest. Layout has
1280×720 and 1440×900 breakpoints plus a single-column narrow layout. Real-backend
browser acceptance covers both sizes, three colors, correction, quote authorization,
source inspection, reload and read-only replay. Run `node scripts/acceptance.cjs`
against the local app; use ACCEPTANCE_ORIGIN to override the default localhost:3000.

## Production packaging (not deployed)

```sh
cd frontend
npm run build
npm run start
```

An optional `Dockerfile` builds Next standalone output. Set Railway's frontend root
to `frontend`, provide the backend URL at build time, and expose the service's
`PORT`. Example local build (replace backend URL with the reachable backend):

```sh
docker build --build-arg BACKEND_URL=http://backend:8000 -t objection-ui .
docker run --rm -p 3000:3000 -e PORT=3000 objection-ui
```

No deploy, public authentication integration, paid model calls or financial
transactions were performed. The demo sessions and synthetic money/provider labels
are intentional. Production authentication is an integrator-owned gap.

Implementation references: [Next.js installation](https://nextjs.org/docs/app/getting-started/installation)
and [Radix Dialog accessibility](https://www.radix-ui.com/primitives/docs/components/dialog).
