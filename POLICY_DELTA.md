# Accepted policy profiles

V5 is rebased onto `main` (`46f6c07`, including the `ac385a1` payment handoff); its early results ZIP records the original
pre-integration `150dab9` revision separately. No accepted order is migrated.
Catalog remains the default product, with CatalogService, catalog-payments-v1,
schema-4 funding terms and the existing payment journal unchanged. Its review is
60 seconds, and verified funding, current checks, the review trigger and all original
payment gates remain required. Substantive catalog amendments retain confirmed
parent-void-before-child-funding. Catalog root OpenAPI is unchanged byte-for-structure.

The existing compatibility `OrderService` now lives in `orders/invoice_compat.py`;
its pure guards live in `runtime/invoice_policy.py`. The broker adapter reuses that
mock authority, the `orders` table, command receipts and base ledger with invoice
jobflow. Catalog, invoice and broker share the application's DB but never dispatch
one profile's policy against another's records. Unrelated historical rows remain
read-only. `/api/broker` and `/api/improvements` have separately mounted schemas.

| Rule | Accepted invoice v0.2 | New broker v0.3 |
| --- | --- | --- |
| Authorization | At accepted-order creation | Only after both parties accept exact specification, sources, price and policy |
| Verification PASS | May capture early with all eight cited checks | Opens customer review; no capture by itself |
| Customer acceptance | Existing policy | Current complete PASS, exact bindings, amount and unexpired authority required |
| 600-second cutoff | Existing undisputed-delivery policy | Current PASS and no unresolved dispute/defect required |
| UNKNOWN / unresolved dispute | Existing hold/escalation | Held immediately; persistent controller task at cutoff |
| Refuted complaint | Actual agreed fee, otherwise accepted authorized quote | NO_REMEDY; no default fee |
| Additional work | Existing V4 change order | Separate linked draft/offer, acceptance and base authorization; original order unchanged |
| Correction | One included regeneration | One included regeneration; changed artifact version must be revalidated |

Authorization expiry remains independent from review expiry, including while a case
is already held. SUBMITTED/UNCERTAIN authority is retained for reconciliation, never
resent. A dispute after capture preserves `payment_phase=booked`; it neither invents
a hold nor creates another base booking. Evidence-based resolution of that paid
case does not require renewing unused capture authority.

The new accepted profile also records a finite 1,800-second overall case bound and
two total evidence-question rounds. A new validated correction starts its own
600-second review inside that bound. Answers never extend the deadline. At the hard
case cutoff, automated work stops with an owned human task; no automatic renewal or
new charge follows. Intake clarification precedes acceptance and is a separate phase.

Capture rechecks the current effective specification, every required check, exact
evidence/delivery bindings, immutable stored-byte hashes, financial state, accepted
amount, independent expiry and idempotency. New evidence and effective-dated,
mutually accepted clarifications invalidate old proposals. Already accepted values
cannot be loosened by an improvement patch or a party's answer.

All broker/invoice receipts remain explicitly mock. The existing catalog payment
architecture was preserved, not replaced. No live transaction, deployment or billing
configuration was enabled.

## V6 catalog integration and resource amendment

V6 starts from actual main5c8dc72 and retains every accepted profile above. Catalog remains
canonical: catalog-v0.3/catalog-payments-v1, 60-second review/dispute, exact$15/15000000 atomic
mock USDC, current PASS plus review/acceptance and independent authority before capture.
Invoice/broker records are not migrated and keep their separately accepted semantics.

The one new typed procedural edit only schedules an existing registered same-edition evidence
acquisition capability. It cannot change accepted facts, terms, price, scope, roles, mandatory
checks, consent or finance. New drafts pin the current tested procedure; accepted pins remain
immutable. Source changes prevent stale approved execution, and revocation affects future work
only. Shared PDF-association, precision and conflicting-repair fixes apply equally to all arms.

The user explicitly enabled bounded Anthropic application calls for V6. CLAUDE_MODEL selects
claude-opus-5-5. The later user amendment removed ALL aggregate request-count ceilings, replacing
120/500 limits with the previously authorized$45 cumulative expenditure ceiling, concurrency<=2,
durable pre-dispatch reservations/usage reconciliation, original10:10Pacific cutoff, bounded
outputs/timeouts/retries, rate-limit cooldowns, loop guards and a measured final-evaluation reserve.
Contractual per-case safety limits are unchanged. No billing/autorecharge setting, deployment,
purchase, real payment or chain broadcast was enabled or performed.
