# Payment lease renewal follow-up

[Review amendment in workstream 09](../workstreams/09-payment-lease-renewal.md#review-amendment--finite-http-and-initial-buyer-authorization)
continues local `9622fe0ecff1bcae01e4b7104f053c9d58e2e393` and closes R9-A/R9-B.
The original Web3 15-second timeout was inactivity-only: the saved 100 ms streaming
probe took 678 ms. The new HTTP-only child has one elapsed 15-second allowance,
including a reserved 250 ms kill/reap interval, and checks cancellation/time at
most 25 ms apart. It performs one direct POST, no retry/redirect, with no inherited
environment or journal/signer code; all waits/cleanup remain outside SQLite locks.
Responses are capped at 4 MiB, default TLS verification remains on, and proxy
environment discovery is disabled. Process scheduling is not a real-time guarantee.

Initial funding now checks after buyer signing and inside the existing reservation
transaction, including write-lock wait time. A late new authorization leaves no
operation or private capability; a concurrent durable operation/nonce/bytes survives.
The API-adapted saved probe now stops at 78 ms and the late signer returns status 3
with zero operations/broadcasts. Loopback HTTP and deterministic signing/lock tests
cover cleanup, cancellation and financial expiry. Validation: **63 focused passes**,
**377 payment/runtime/dataset/API passes**, **720 full-backend passes**, with the
same two compiler xfails; all **27** offline lab examples, backend/tools/lab Ruff,
Node **24.14.1** generated-contract freshness and whitespace checks passed. The
original 695-pass record remains historical; exact commands/timings are in 09.

Submitted identity remains unresolved on timeout; inspection after financial expiry
uses that same saved identity without resend. No transaction recovery or live proof
is added. No main merge/push occurred; preserve newer Lucas main changes and integrate
Jeff's exact reviewed compiler commit separately. Public contracts/frontend and
Jeff's two strict expected failures remain unchanged.

[Workstream 09](../workstreams/09-payment-lease-renewal.md) implements fenced renewal
and finite shared attempts from reviewed main `62fe03542f18d9f7514550bcff25968ae2557c08`.
A 120-second lease renews cooperatively every 30 elapsed seconds; submission has a
300-second total budget including lab preflight/staging, and receipt inspection a
180-second budget independent of financial expiry. Presign/send and durable-write
checks preserve accepted financial cutoffs, ownership and current policy. Shutdown
signals active attempts, then drains synchronous calls. Lease loss is not a payment
outcome. Transient stops retain the original reservation/nonce; submitted bytes stay
unresolved and are never automatically resent.

The historical sections below describe their original checkpoints. Prompt 07's
readiness test and lab call sites were narrowly adapted as listed in 09; historical
reports remain unchanged. Exact-byte recovery, live latency/deployment/receipt proof
and Jeff's R3/R4 compiler blockers remain outstanding. No live run is authorized.

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
