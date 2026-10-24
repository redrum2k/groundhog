# Accepted policy profiles

V5 is rebased onto `main` (`ac385a1`); its early results ZIP records the original
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
