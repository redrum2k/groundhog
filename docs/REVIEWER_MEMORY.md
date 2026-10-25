# Reviewer memory in the existing request-to-cash flow

Presentation status: background engineering only. The October 25 demo excludes
memory capture, reuse and before/after improvement claims. The sequence below is
an engineering rehearsal, not the presenter path; use PITCH.md for the demo.
Reliable real-model improvement remains unverified.

This is reference reuse, not a new factual-rule or payment authority. The existing
pipeline, admin actions, mandatory checks, independent review, 60-second windows,
correction allowance and settlement gates are unchanged.

## What is saved and retrieved

The optional **Guidance for similar cases** field submits with the admin decision
and its selected evidence IDs. Enter guidance and select one to eight current
citations in **Supporting evidence**. Ordinary decisions do not create memory.
The decision, memory, event receipt and exact idempotent response commit in one
existing SQLite transaction. Failed submissions show no saved receipt. Exact
replays return the original memory ID.

`catalog_records(kind='reviewer_memory')` retains reviewer actor, original
order/run/case/binding, decision ID, timestamp, explanation, guidance, exact cited
references and applicability. No separate database, service or learning loop exists.

Retrieval compares customer/provider, the full accepted scope (excluding only
request-specific intake provenance), the accepted requirement and complaint field,
and the exact frozen source descriptors: identities, editions, hashes, supplier,
authority and authority record. It considers at most 12 matching records and
selects at most three from other orders. Changed source editions are deliberately
excluded even when they look similar; this first version favors conservative reuse.
A failed current verification, changed active sources, missing source bytes or
unresolvable supporting cells excludes reuse. A prior delivery citation contributes
only its locator; its value/version/hash is rebuilt from the current delivered CSV.
Historical absence certificates are not reusable guidance citations.

The existing assessment request freezes the included memory records and current
citations before dispatch. Memory cannot displace the existing 32-reference
current evidence packet; a record that cannot fit is omitted. Completed recovery
reuses the original packet, and uncertain dispatches are not automatically retried.
Both the assessor and blind reviewer receive guidance as attributed, untrusted
reference material, never a preferred result or instruction to override policy.
Missing facts remain UNKNOWN. Guidance cannot change scope or authorize payment.

The existing finding panel displays **Prior reviewer guidance consulted** only
from that persisted assessment packet. Its expansion shows the previous explanation,
originating case and current supporting citations. Consultation is explicitly
separate from a successful answer.

## Honest example and exact words

The unchanged synthetic SF dataset has a registered authority document containing
`definition="Gym membership or fitness-app use."`, `yoga_category="Wellness"`,
and `yoga_is_gym=false`. The accepted base product excludes standalone yoga.
The ambiguity is how to navigate and interpret these different cells, not a missing
source fact. Human guidance can point to the membership cell instead of inferring
membership from a broad label. A real model may already resolve this without help.
No runtime code forces an initial failure or a later verdict.

1. Customer request, on `/` or `/live`:

   > SF adults 25-34, gym membership or fitness app users, by ZIP. Exclude yoga.

   Prepare quote, accept the agreement and simulate funding; wait for verified delivery.

2. Easy objection, in **Object**:

   > Regenerate the delivery because ZIP 94110 is missing.

   Current source and delivery cells show that ZIP. The regeneration demand does
   not establish a defect. Wait for the objection decision; do not accept delivery yet.

3. On the same delivery, **Object again**:

   > The Wellness label looks like a gym category; is standalone yoga omitted from what I bought?

   If the agent asks for evidence, use the existing **I don't have this evidence**
   response to reach human review. If a real model already answers correctly, that
   is a successful baseline, not a reason to force failure. This candidate demo
   remains unqualified for a real-model before/after claim.

4. Open **Human review**. Select the authority's `yoga_is_gym` citation (and, if
   useful, `definition`) in **Supporting evidence**. Reviewer explanation:

   > Inspect the exact taxonomy cell, not only its label.

   **Guidance for similar cases**:

   > For a yoga-as-gym interpretation, inspect the frozen authority's yoga_is_gym cell. The Wellness label alone is not membership evidence. Compare the current accepted category and definition; do not infer inclusion or a delivery defect from a label. If taxonomy is null or conflicts with scope, retain UNKNOWN or CONFLICT.

   Submit **Escalate** to retain human review for the original unresolved question.
   **Guidance saved for similar cases** confirms the atomic write. This does not
   convert the original question to a factual finding or collect funds.

5. Use **New request**, repeat the same customer request, and proceed normally
   through quote, agreement, simulated funding and verified delivery.

6. Paraphrased follow-up objection:

   > Under our accepted scope, standalone yoga counts as gym membership.

   The later assessor receives the attributed guidance and current authority
   citation. Inspect **Prior reviewer guidance consulted** in Finding. The registered
   false taxonomy cell can contradict this particular claim; historical delivery
   values cannot. Customer acceptance is still required for immediate settlement.

The two objections must be submitted within the existing delivery review window.
No test or demo code extends deadlines. Late objections retain the existing human
review behavior. No private environments or existing demo databases are changed.

## Launch the offline integration rehearsal

This uses an explicitly injected local model transport in a test-only module.
It exercises the real gateway, independent review, persistence and HTTP lifecycle,
but its finite fixture interpretations are **not observed model intelligence**.
Its result depends on current cited values, not on order number or memory presence.
The normal application does not import this module.

Use Node 24 and the existing backend virtual environment. From the repository root,
create a fresh temporary destination; retain the printed path for inspecting evidence:

```sh
MEMORY_DEMO_ROOT=$(mktemp -d /private/tmp/groundhog-memory-demo-XXXXXX)
printf '%s\n' "$MEMORY_DEMO_ROOT"
cd backend
env ORDER_DB_PATH="$MEMORY_DEMO_ROOT/orders.sqlite3" \
  ARTIFACT_ROOT="$MEMORY_DEMO_ROOT/artifacts" \
  INTERNAL_API_TOKEN=memory-offline-worker \
  REVIEWER_API_TOKEN=memory-offline-reviewer \
  ENABLE_PAID_MODELS=false ENABLE_TESTNET_BROADCAST=false \
  JOBFLOW_DEMO=1 JOBFLOW_ANTHROPIC_MAX_CALLS=0 \
  .venv/bin/python -m uvicorn tests.dataset.reviewer_memory_server:make_app \
  --factory --host 127.0.0.1 --port 8057
```

The test server refuses an existing database. For a new rehearsal, create another
fresh destination. Restart/replay behavior is separately exercised by the tests
below against the same temporary SQLite database.

In another terminal, from `frontend`:

```sh
env BACKEND_URL=http://127.0.0.1:8057 \
  BROKER_BUILD_DIR=.next/memory-integration BROKER_LOCAL_DEMO=1 \
  BROKER_PUBLIC_DEMO=0 \
  INTERNAL_API_TOKEN=memory-offline-worker \
  REVIEWER_API_TOKEN=memory-offline-reviewer NEXT_TELEMETRY_DISABLED=1 \
  npm run dev -- --port 3057
```

Open `http://127.0.0.1:3057/live`, or run from `frontend`:

```sh
env BROKER_SMOKE_ORIGIN=http://127.0.0.1:3057 \
  BROKER_SMOKE_OUTPUT=/private/tmp/groundhog-memory-browser-results \
  node scripts/reviewer-memory-smoke.cjs
```

The browser script checks both receipts, page reload, two normal funded requests,
repeat objections, current citations and held funds, and writes screenshots,
trace and persisted event snapshots. It refuses a nonlocal origin and verifies
mock payment terms before funding. Use it only with the isolated test server above.
Next may add the custom build directory to `tsconfig.json` and `next-env.d.ts`;
those generated build-path edits are unrelated to this feature.

## Validation and limitations

Run the focused memory tests without a socket listener:

```sh
cd backend
env ENABLE_PAID_MODELS=false ENABLE_TESTNET_BROADCAST=false PAYMENT_ADAPTER=mock \
  .venv/bin/python -m pytest tests/dataset/test_reviewer_memory.py \
  tests/dataset/test_reviewer_memory_http.py -o addopts='' -q
```

Observed: 22 focused tests pass, including atomic rollback, exact replay, restart,
completed/uncertain assessment recovery, blind-review context isolation, bounded retrieval, customer/provider/scope/
requirement/authority exclusion, missing taxonomy, rebuilt delivery values, invalid
current citations, unchanged deadlines and settlement gates. The in-process real
HTTP test includes the easy regeneration objection, repeat objection, admin save,
a second fully funded request, consulted receipt, and capture only after customer
acceptance. The easy objection exercises the existing blind-review path through
injected model responses; no paid request occurs.

The broader runnable suite passed 818 backend tests (dataset, catalog, investigation,
payments and API, excluding the socket-only file below), plus 270 frontend tests.
TypeScript, generated-contract drift checks, Ruff, and the production webpack build
passed. React Doctor found no changed-file diagnostics; its remote score API was
unreachable. A later added blind-review regression also passed in the 22-test
focused run.

The actual browser/backend rehearsal is **not yet verified in this session**:
the execution sandbox rejected localhost listeners with `EPERM` on ports 8057 and
3057. The same restriction blocked 13 socket-based tests in
`tests/payments/test_http_boundary.py`. Those tests were not changed. The browser
script is provided and syntax checked, not represented as an observed passing run.

No real-model rehearsal was performed. Any claimed before/after model improvement
remains **unverified**. No paid calls, broadcasts, deployment, push or merge occurred.
