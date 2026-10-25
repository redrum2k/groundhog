# Test the platform now

Use the reviewed main checkout. The frontend route fixes and reviewed 09/09b
payment work are now integrated:

```sh
cd /Users/nikitaafanaskin/Documents/Developer/order-to-cash
git status --short
git log -1 --oneline
```

Validated integration is `4a24c9f91962c2924770614e38b6e6edee905a94`, including
published main `04756e1`, the frontend/schema checkpoint, and reviewed payment
commit `593e02f`. Later documentation commits do not change that implementation.
The browser uses the real local API, persisted state and background workers with
synthetic data and explicit mock payments. No wallet is required and no testnet
transaction is made. See [current integration evidence](reviews/frontend-payment-integration.md).
Jeff's R3/R4 compiler paths remain known failures at this baseline.

## Fast offline platform check

From that checkout:

```sh
uv sync --locked --project backend
uv run --locked --directory backend python ../tools/brokerage_acceptance.py --output /private/tmp/datumco-acceptance
backend/.venv/bin/python spikes/payments/examples.py
```

The first runner creates a fresh directory each time and saves report.json,
orders/payments/bookings, events and source/delivery artifacts. It covers conforming
capture, an explicitly injected missing-ZIP producer defect and one correction,
separate Oakland acceptance/funding and evidence-based yoga resolution. The second
runs 27 offline CLI processes for funding/restart/capture, independent void and
expiry/reclaim. Neither uses real RPC or money.

## Interactive browser journey

Terminal A — backend (leave it running):

```sh
cd /Users/nikitaafanaskin/Documents/Developer/order-to-cash
uv sync --locked --project backend
BROKER_DEMO_DIR=$(mktemp -d /private/tmp/datumco-local.XXXXXX)
printf '%s\n' "$BROKER_DEMO_DIR"
ORDER_DB_PATH="$BROKER_DEMO_DIR/orders.sqlite3" \
ARTIFACT_ROOT="$BROKER_DEMO_DIR/artifacts" \
INTERNAL_API_TOKEN=local-broker-worker REVIEWER_API_TOKEN=local-broker-reviewer \
ENABLE_PAID_MODELS=false PAYMENT_ADAPTER=mock ENABLE_TESTNET_BROADCAST=false \
JOBFLOW_DEMO=1 JOBFLOW_ANTHROPIC_MAX_CALLS=0 \
uv run --locked --directory backend python -m uvicorn app.main:app --host 127.0.0.1 --port 8028
```

Keep the printed directory for inspection. Do not copy a private `.env` or reuse
an existing database. Source datasets, authority records and the ZIP registry are
created automatically on request creation.

Terminal B — frontend (leave it running):

```sh
cd /Users/nikitaafanaskin/Documents/Developer/order-to-cash/frontend
export PATH="/Users/nikitaafanaskin/.nvm/versions/node/v24.14.1/bin:$PATH"
node --version
npm ci
npm run generate:check
BACKEND_URL=http://127.0.0.1:8028 npm run build
BACKEND_URL=http://127.0.0.1:8028 \
BROKER_LOCAL_DEMO=1 INTERNAL_API_TOKEN=local-broker-worker \
REVIEWER_API_TOKEN=local-broker-reviewer \
npm run start -- --hostname 127.0.0.1 --port 3028
```

Use a free port pair if those ports are occupied, updating BACKEND_URL and the
browser-smoke origin together. Use Node 24; the repository minimum is 22.12.
The distinct token values above are disposable local-demo credentials, not
production secrets. Both servers bind only to loopback. The current bridge
intentionally rejects hosted/public access. No deployment is required.

Open <http://127.0.0.1:3028/live> for the funded aggregate workflow in a fresh
private/incognito window. This avoids a saved run ID from an older temporary
database. The header says **Groundhog** and **mock payments**. If the
normal browser restores an obsolete run and reports 404, use **New request**.

Follow these steps:

1. Create a request with `SF adults 25–34, gym members or fitness-app users,
   grouped by ZIP.` This unambiguous input skips the optional clarification.
2. Prepare the quote, inspect its $120 terms, then explicitly accept it.
3. Open **Funding**, choose **Prepare funding**, then **Simulate mock funding**.
4. Open **Delivery & review**. Wait for the worker, inspect the eight checks and
   download the CSV. Expect 27 unique ZIPs, 94110 count 170, and 94129 suppressed
   with no exact count.
5. Reload: the same run and delivery should return. Accept the verified delivery
   before its 60-second review expires, or let an undisputed review expire.
6. Confirm captured state, one capture event/booking and the mock label, with no
   transaction hash or explorer link. Preparation and funding alone must not
   show provider receipt.

Use **New request** for another independent run. The separate Oakland/yoga offer
controls require their own quote acceptance and funding. Prompt 08 adds explicit
complaint targets, evidence references and corrected financial-state displays.
Negated yoga intake and corrected cohort answers still need Jeff's R3/R4 fixes;
08b's unavailable-preview recovery is already merged. **Run canvas** opens `/`,
which has the retained broker demo and a separately selectable **Recorded** feed.
Branding does not change accepted policy IDs such as `datumco-demo-pricing-v1`.

## Root canvas and Recorded fallback

Open <http://127.0.0.1:3028/>. This is Lucas's **Groundhog** canvas. Its **Live**
feed uses `/api/broker-run` and the retained `broker-review-v0.3` backend, scripted
parties and USDSIM mock authority. It has a 600-second review and is distinct from
`/live`'s confirmed-funding gate and 60-second aggregate review. It is not evidence
of aggregate escrow funding or live-chain success.

1. Choose **Play live** and wait for **Summit's turn: approve the contract**.
2. Open that customer action and choose **Approve and authorize $120**. The view
   returns to the agent. This profile's authorization is mock and is not capture.
3. After delivery, open **Summit's turn: accept or object**, choose **Object**, and
   send `Counts look low. Oakland should be in there.` The view returns to the agent.
4. Inspect the answer and its contract/coverage citations. Return to the customer
   action and choose **Accept delivery**. The view returns to the agent again.
5. Reopen **Customer view** and confirm **mock capture**, one capture event, and
   no transaction/explorer link. Do not describe the retained broker as the new
   aggregate payment journey.

For fallback, select **Recorded** and use **Play/Pause/Replay**. This works when
broker health is unavailable and creates no backend run. It is a rehearsal.
The retained broker's Next-process run handle is ephemeral; aggregate restart
persistence applies to `/live`, not to a new claim about this compatibility driver.

## Two more manual scenarios

Use **New request** and repeat the normal quote/funding steps for each scenario.
A delivery review lasts 60 seconds, so prepare complaint text before funding.

**Unsupported factual complaint:** In **Delivery & review**, select:

- Accepted requirement: `R-COVERAGE`.
- Dataset row: `94110`.
- Dataset column: `zip`.
- Request type: **Dispute delivered facts**.
- Complaint: `ZIP 94110 is missing from the delivery`.

Click **Record complaint** before review closes. Expect an unsupported/disagree
finding because the actual CSV contains 94110, with no unrelated yoga question or
extra complaint fee. Inspect the persisted evidence. This tests the form, target
validation and independent backend assessment together.

**Additional paid scope:** Choose **Request provider oakland offer**. Expect a
separate $60 offer. Choose **Review separate offer** and inspect it before accepting.
The child run must require its own explicit acceptance and mock funding before
work starts. Reload and verify the separate run ID and payment state remain intact.

For the missing/corrupt-preview scenarios, the focused HTTP tests fault only their
own temporary artifacts and verify polling, valid complaints and capture refusal:

```sh
# Repository root; independent of the demo servers' database.
uv run --locked --directory backend pytest tests/dataset/test_review_artifact_availability.py
```

## Repeatable production browser test

With both servers running, terminal C in `frontend`:

```sh
export PATH="/Users/nikitaafanaskin/.nvm/versions/node/v24.14.1/bin:$PATH"
npx playwright install chromium
BROKER_SMOKE_ORIGIN=http://127.0.0.1:3028 \
BROKER_SMOKE_OUTPUT=/private/tmp/datumco-browser-check \
node scripts/brokerage-smoke.cjs
BROKER_SMOKE_ORIGIN=http://127.0.0.1:3028 \
BROKER_SMOKE_OUTPUT=/private/tmp/datumco-coverage-check \
node scripts/review-remediation-smoke.cjs
```

Keep `BROKER_SMOKE_ORIGIN` as the bare origin: both scripts append `/live`.
These tests use the actual frontend bridge, API, durable worker and mock settlement.
It refuses live payment mode, checks reload identity, downloads the CSV and waits
for capture. The second script checks a real coverage complaint through the new
form and backend, including no unrelated yoga question. Happy-path output: `delivery.png`, `captured.png`, `delivery.csv`,
`events-payment.json`, `trace.zip`. Inspect the trace with:

```sh
npx playwright show-trace /private/tmp/datumco-browser-check/trace.zip
```

The current integration validated both aggregate browser smokes against a production
build, the root broker objection/acceptance journey, and Recorded fallback. Both
aggregate runs retained identical events, payment identity, terms and deadlines
after a backend restart; browser reload and downloaded CSV hashes also matched. The `.next` build directory is
ignored. Stop each server with Ctrl-C when finished. Restarting the backend against
the same printed `BROKER_DEMO_DIR` preserves its data; rerunning `mktemp` deliberately
starts a new database and should be paired with a fresh browser run.

## Full regression checks

```sh
# Worktree root
uv run --locked --directory backend pytest
uv run --locked --directory backend ruff check . ../tools
uv run --locked --directory backend ruff format --check . ../tools
backend/.venv/bin/ruff check --config backend/pyproject.toml spikes/payments
backend/.venv/bin/ruff format --check --config backend/pyproject.toml spikes/payments
backend/.venv/bin/python spikes/payments/examples.py
git diff --check
cd frontend
npm test
npm run typecheck
npm run generate:check
```

Current combined-tree results: **720 backend tests passed, two unchanged strict
R3/R4 expected failures; 109 frontend tests passed; 27 offline lab commands passed**.
Focused payment/runtime/dataset/API cases: 377 passed and the same two expected
failures. Build, typecheck, generated contracts, lint/format and whitespace passed.
React Doctor remained at full-tree score 38 (preexisting findings), with changed-file
score 92 and no findings. No suppression or compiler marker change was made.
The earlier `62fe035` record remains historical: 666 backend passes, two expected
failures and 104 frontend passes; see the earlier integration record.

Real-money mechanics are a separate future test: follow the combined worktree's
`docs/workstreams/07-payment-readiness.md`. It calls for explicit public
configuration, exact-byte recovery work and separately authorized testnet execution. Fenced lease
renewal and bounded attempts are integrated; recovery of an unsent submitted
transaction is still unimplemented.
The 0.10 test-USDC laboratory fixture does not fund a $120 dataset order.
