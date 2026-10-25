# Parallel task — Nikita's isolated Base payment readiness

Prepare the existing Base Commerce Payments laboratory for an observed testnet
validation run. This task can run alongside the data-broker migration: payment
mechanics are independent of dataset semantics and canvas events. Complete offline
checks and a concrete run plan. Do not claim live success without observed evidence.

## Baseline and ownership

Use a separate worktree/branch `codex/payment-readiness` based on
`39dd58602b3f8ac0a7906b4db4ddbbdb57b3d981`, the completed backend integration.
If this worktree/task already exists, continue it and preserve its uncommitted lab
work; do not recreate/reset it or edit the migration worktree.
Inspect status, ancestry and instructions before editing. Preserve teammates' work;
do not edit another worktree. Read AGENTS.md, applicable nested instructions,
HACK.md, docs/PAYMENT_SPIKE.md, docs/PAYMENT_RUNBOOK.md, docs/handoffs/nikita.md,
docs/workstreams/02-base.md, docs/workstreams/04-integration.md and
spikes/payments/README.md.

Integration context: Jeff's PR #4, "Add broker review and improvement workflow",
merged to main at `5c8dc726326bb9e3539cdb51e5aec221868223bc` after Lucas's PR #3.
Prompt 6 owns merging that commit/current reviewed main into the existing backend
integration and reconciling startup in `backend/app/main.py`. This isolated task
does not need that application merge and must not substitute origin/main for the
`39dd586` baseline: main does not yet contain its integrated Base adapter/runtime.
Read Jeff's HANDOFF.md and POLICY_DELTA.md at that commit with `git show` if absent
here. His `/api/broker` uses a separate USDSIM/mock compatibility profile, 600-second
reviews and a 1,800-second case bound. Its authorization, capture and test results
are not Base readiness evidence or permission to change this lab's payment terms.
PR #4 changes no `app/payments` or `spikes/payments` files; keep this work independent.

Own only spikes/payments, dedicated lab-readiness tests, and
docs/workstreams/07-payment-readiness.md. Reuse BasePaymentTransport, PaymentExecutor
and PaymentJournal as implemented. Do not edit the shared transport/configuration,
executor/journal, application orders/lifecycle/policy, public DTOs, frontend or
generated artifacts. If a shared fix is necessary, demonstrate the failure and
write an exact proposed change for coordination rather than silently changing the
interface. Prompt 6 owns application review/capture deadline scheduling.

The user relayed judges' option 2 guidance allowing the direct Commerce Payments
approach; record it as relayed guidance, not verified eligibility or full x402
compliance. Do not introduce an x402 facilitator, CDP wallet migration, custom
contract or second ledger.

## Work

1. Run the existing offline lab examples and relevant payment/lab tests with temporary
   journals and synthetic keys. Verify the documented command flags against --help.
   Confirm independent fund → restart → capture, fund → void and expiry → payer
   reclaim flows, exact retries and pending/uncertain outcomes. Reuse tests; add
   targeted cases only for an actual gap. Fix lab-only defects within ownership.
2. Prepare a names-only configuration checklist: RPC endpoint, public payer/operator/
   provider addresses, signer roles, test USDC and gas requirements, journal location,
   confirmation threshold and gas ceilings. Do not load existing private .env files,
   wallets or databases, print credentials, or ask for keys in chat. The normal app
   uses buyer-wallet signatures; a payer key is confined to this isolated lab.
3. If the user supplies an explicit public RPC endpoint and public test addresses
   for this task, run read-only preflight with signing/broadcast disabled. Otherwise
   document the missing inputs and continue all offline preparation. Check chain
   84532, pinned deployment/linkage, token decimals/domain, public identities,
   balances, canonical historical reads and measured RPC latency. Report what was
   actually observed. A missing configuration is not a successful preflight.
4. Inspect the documented multi-read preflight/120-second lease issue and the
   crash-between-persisted-submission-and-broadcast recovery limitation. Provide
   reproducible offline evidence or measured read-only latency as available. Specify
   what to inspect/reconcile and when to stop; never fix ambiguity by resetting a
   journal, payment ID, salt or nonce. Shared implementation changes require a
   coordinated follow-up, not an unowned refactor.
5. Produce exact commands and an evidence checklist for two later independent
   testnet fixtures, each 100000 atomic test USDC: A fund → restart → full capture;
   B fund → full void. A third expiry/reclaim case is separate. This is a payment
   lab amount, not funding for the migration's $120 dataset order. Prepare live
   terms only immediately before execution so the funding window has not expired.
6. The live checklist must distinguish submission from matching canonical confirmed
   events/state, record public transaction hashes only when observed, verify exact
   amount/parties/provider receipt or buyer return, demonstrate provider cannot
   capture, and preserve identity across restart/retries. Keep signed bytes,
   signatures, credentials and private journal contents out of the public report.

## Finish

Write docs/workstreams/07-payment-readiness.md with the baseline SHA, commands and
tests actually run, configuration gaps, public preflight observations if any,
remaining shared fixes, and the concrete bounded testnet execution plan. Keep
offline/injected-chain/read-only/live evidence clearly identified. Run relevant
tests and Ruff for any changed code. Give prompt 6 the exact lab-only commit for
integration; do not merge its unfinished application branch into this active task.
Record which shared transport/executor/journal revision was tested. If prompt 6
changes those interfaces, name the specific lab checks to rerun on the final combined
tree; a pass on the earlier baseline does not certify changed shared code.
Commit only this task's files locally and return branch/SHA and handoff. Do not push
or merge.

This prompt authorizes offline preparation and explicitly configured read-only
checks. Actual transaction broadcasts, funding transfers, wallet creation, paid
services and deployment require a later explicit user instruction; do not perform
them as an implicit part of readiness. Do not enable broadcast flags during this
task. No existing secrets or private state are needed for the offline work.
