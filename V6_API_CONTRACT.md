# V6 additive integration contract

Catalog remains the root API. Its frozen OpenAPI component names and existing financial command
contracts are preserved. New schemas are separately mounted. This is a localhost synthetic demo,
not production authentication or tenant isolation. Privileged tokens are server-side only.

## Committed read-only events

| Route | Behavior |
| --- | --- |
| GET /api/runs/ | Saved catalog-order summaries |
| GET /api/runs/{order_id}/events?after={seq} | Committed events, next_cursor and server time |

Events append in the SAME SQLite transaction as catalog state/payment projection. Each includes
stable event_id, monotonic database seq, run/order ID, authoritative aggregate revision, accepted
snapshot SHA, exact evidence/delivery binding, actor/operation/correlation, procedure_version,
exact CatalogOrder and PaymentView. Sequence is database-wide; do not assume consecutive per-order
numbers. Deduplicate byseq/event_id, retain actual revisions, and paginate using next_cursor.
Polling and replay never invoke get-with-expiry, work, model calls, payments or synthetic endings.
Mode live_backend distinguishes actual domain state from the separately labeled recorded sample.

## Scoped improvement records and commands

| Route | Role / operation |
| --- | --- |
| GET /api/catalog-improvements/scopes/{corpus_id} | Read immutable records, statuses and stored active pointer |
| POST /api/catalog-improvements/orders/{order_id}/observe | Worker; exact OrderCommand binding |
| POST /api/catalog-improvements/commands | Worker; propose or isolated probe |
| POST /api/catalog-improvements/review | Distinct reviewer; approve, activate or revoke |

Worker requires X-Internal-Token; reviewer requires a different X-Reviewer-Token. Browser code
never receives either. CatalogImprovementCommand contains idempotency_key, corpus_id, verb,
expected_active_version, reason and the exact incident_ids/patch_id/probe_id/version_id needed.
cycle 1/2 and the max2 candidates per cycle are scientific bounds, NOT mission request ceilings.
Model mode is explicitly ANTHROPIC; deterministic/injected controls are labeled separately.

Only operation retrieve_registered_same_edition on REQUIRED_VALUE_UNREADABLE is accepted.
Schema denies price, capture, source-truth, role, history, scope and arbitrary-code edits.
Retrieval invokes ordinary request-bound upload, authority/edition/known-value/conflict checks,
consent and revalidation. selectable controls initial source selection, not repair entitlement.
Conflicting valid registered restorations hold; a newer edition or changed known fact is not
evidence-only. No retrieved copy can grant capture authority.

Approval binds candidate, implementation/dependencies, baseline, probe/report and scope.
Activation is a separate exact command. New drafts pin the tested version; accepted pins never
change. Execution-time implementation checks block stale versions. Revocation returns only
future drafts to the previous version. Exact replay returns the stored response; changed
payload under a reused key and stale versions return409. Running/interrupted generation returns
UNKNOWN rather than silently issuing another model call. Completed output cannot be rerolled in
the same scientific cycle; pre-response technical failure may recover without hiding the attempt.

## Existing order and financial commands

Reuse root requests/clarification/quotes/acceptance, /orders/{id} commands, /internal worker routes
and /reviewer/orders/{id}/decisions. Every order mutation carries expected_revision,
expected_binding and idempotency_key. The frontend uses these exact server values, never event
count or UI state as a binding. Customer quote acceptance, funding authorization, work, delivery
acceptance, reviewer decision and procedure approval are distinct commands.

Reviewer actions remain request_evidence, propose_exception or release_authorization, with a
reason and at least one resolvable source span. No reviewer capture/expiry override exists.
Archived verification/amendment citations remain selectable after invalidation. Proposing an
exception changes neither facts nor accepted terms; new agreement is still required. Release of
uncaptured authorization is not an implemented refund.

## Same-origin frontend bridge

Public /api/catalog/* maps only allowlisted catalog/event reads and customer commands.
worker/* maps to /internal/* or the mounted improvement commands; reviewer/* maps to the
corresponding distinct reviewer route. Privileged demo controls require
ENABLE_CATALOG_DEMO_CONTROLS=true. Mutations require a local Host and matching Origin; forwarded
host values are not trusted. Redirects are rejected, request size bounded, responses no-store.
The proxy timeout is75s; SDK request timeout is at most60s and clipped by remaining mission time.

Opening panels, overview, saved runs, replay, refresh and reconnect never POST. Explicit
commands retain the exact key/body after an uncertain response;4xx conflicts require inspection,
not silent reauthorization. The recorded sample remains separate from live catalog data.

## Application API budget

CLAUDE_MODEL and ENABLE_PAID_MODELS are the repository's configuration variables. All real SDK
paths use the shared SQLite ModelBudget; BEGIN IMMEDIATE serializes reservations. Costs reserve
before transport and reconcile after reported input/output/cache usage. Thinking is included in
output tokens. Unknown usage keeps its maximum reservation. No aggregate request-count cap
remains; counts are telemetry. Concurrency<= 2, original cutoff, per-request output caps, SDK
retries0, Retry-After cooldown and repeated-identical/failure guards remain enforced.

The final evaluator has an explicit frozen-plan digest and reserved dollars. Reaching the
dollar ceiling prevents new paid dispatch, not independent engineering. Never change the ledger
path, cutoff, billing or recharge settings to bypass the authorized envelope. CONFIGURED in the
view denotes installed configuration, not a fresh authentication/balance/readiness claim.

Generated types: frontend/lib/run.generated.ts and catalog_improvement.generated.ts. Run
npm run generate:check after schema work. Root catalog policy, journal and accepted records
must not be replaced by invoice/broker or recorded-sample assumptions.
