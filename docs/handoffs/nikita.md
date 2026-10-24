# Review remediation and remaining shared payment work

[Workstream 08](../workstreams/08-review-remediation.md) records R1/R2/R5/R6 fixes,
tested historical replay and Jeff-owned R3/R4 blockers. Continue on the reviewed
combined commit; Prompt 07's four files remain byte-identical to `f8a929a`.

Live execution remains blocked. Separately scope two shared-runtime changes:
fenced claim renewal with a total deadline budget, and an explicitly authorized,
audited exact-persisted-byte recovery operation. The existing 136-second/120-second
lease reproduction and crash-after-submitted-before-send reproduction still pass
as demonstrations of limitations. Do not alter lab fixtures to hide them, increase
timeouts blindly, remove fencing, reset identities/nonces or auto-rebroadcast.
Workstream 08 lists acceptance cases and the measured public preflight prerequisites.
No real RPC, testnet receipts or deployment are claimed by remediation.

# Aggregate brokerage migration handoff

Current primary product: `aggregate-brokerage-v1`; historical profiles retain their
accepted policy. Start with [workstream 06](../workstreams/06-data-broker.md): complete
migration map, route/examples, demo commands, mock signing boundary and validation.

The shared worker, Base setup, transport, journal, signing flow and terminal executor
remain the only financial path for new runs. Narrow owner hooks append run events
inside existing transactions and revalidate dataset bytes at capture. The new
scheduling policy adds a 120-second submission margin and reserves full potential
review/dispute/correction windows; already submitted actions still reconcile.
Broker deadline sweeps and improvement recovery coexist with independent catalog,
payment and invoice lanes. Prompt 7 owns its isolated lab files; do not retrofit
its synthetic terms as a customer application agreement. Completed Prompt 7 commit
`f8a929a` is integrated unchanged by local merge `6a714cf`; its four owned files
were not rewritten by this migration.

## Historical catalog handoff

# Nikita — integrated runtime and payments

The three completed workstreams are integrated on `codex/backend-integration`; see
[exact SHAs and validation](../workstreams/04-integration.md). All validation is offline.
**No observed live testnet receipt, paid model call, deployment or push.**

`CatalogWorker(service).run_once()` selects one draft/job attempt. Lifespan owns five bounded
independent lanes and drains in-flight calls before releasing its process lock. Compilation
exhaustion now invalidates an in-flight fourth result and persists exact exhaustion replay.
`CatalogService(..., payment_mode, payment_config, payment_transport)` injects the payment layer.
`BasePaymentTransport(config, rpc=...)` implements PaymentTransport and verified_usdc_domain().
`payments.work(limit=0..20)` handles bounded submission/reconciliation; deferred operations yield
so disabled signing cannot starve another payment's receipt. Confirmed effects and bookings share
the catalog SQLite transaction, regardless of the isolated lab's PAYMENT_JOURNAL_PATH.

`payments.catalog_payment_setup()` runs only during lifespan, defaults to mock, and performs
read-only preflight only when Base is selected. Missing signer/config or failed preflight leaves
Base unavailable with submission disabled; restart after fixing it. Receipt inspection can
continue with an available transport. Import/schema export has no configuration, RPC or .env
side effects. Invoice mock policy and adapter selection remain separate.

Own configuration/signers, operator execution, outbox/nonces, reconciliation, lifecycle gates,
provider dispatch and backend deployment. Preserve current evidence/consent/dispute/review/
amount/expiry gates and immutable accepted terms. A submitted capture cannot be cancelled;
parent replacement void must confirm before child funding/work. No AI wallet authority.

Remaining live milestone requires separate authorization and fresh disposable setup: follow
[runbook](../PAYMENT_RUNBOOK.md) and [payment spike](../PAYMENT_SPIKE.md) for two independent
100000-atomic-USDC payments, fund/restart/capture and fund/void. Verify actual deployment,
RPC historical support, gas, balances, canonical evidence and provider non-authority. No ordinary
catalog USD 15 order is funded by the lab's 0.10 test-USDC amount. Orphaned/crash-around-broadcast
operations need explicit manual recovery; no rebroadcast/fee-bump/refund implementation exists.

[Lucas's concrete backend/bridge handoff](lucas.md) is ready. Catalog UI and wallet integration,
customer authentication/tenancy, independent quality evaluation and sponsor verification remain
with their assigned owners; no public deployment is part of this integration.
