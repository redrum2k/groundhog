# Payment spike — unrun

Owner: Nikita. The empty checkout contained no previous spike notes. This file is a
plan and unresolved interface checklist, not evidence of working escrow or settlement.

## Purpose

Determine whether CDP and the existing Base escrow contracts can implement the
accepted order's authorization, capture, release and reconciliation requirements.
Do not assume a card-like hold API. No SDK/provider, deployed contract address,
network, asset, authorization lifetime, or finality threshold is selected here.

## Isolated work

Use `spikes/payments/`; do not couple the main runtime to an unverified experiment.
The current scaffold does not make paid calls, broadcast transactions, or deploy.
Any such experiment needs separate authorization. Keep credentials private and
ignored; the checked-in `.env.example` contains variable names only.

## Questions the spike must answer

1. Who authorizes which spender/contract, for what asset/network/amount and lifetime?
   How does that authorization bind an immutable order snapshot?
2. How do capture and release work, including escrow ownership and unsupported
   partial-operation semantics? Pre-delivery cancellation UI remains out of scope.
3. Can an open dispute reliably block capture? What authoritative state and atomic
   reservation protect acceptance/dispute/capture races?
4. What happens when the separate onchain authorization expires before the 60-second
   review window or during a human review? How is any renewal explicitly authorized?
5. Which receipt/provider/chain evidence establishes submission, uncertainty, failure
   and confirmed settlement? What finality/reorg rule is sufficient for the demo?
6. How are persisted idempotency keys mapped to transactions/nonces, and how are
   restart, response loss, replacement, retry and uncertain outcomes reconciled?
7. Which fees exist and who pays them? No additional debit for unsupported complaints
   is authorized, regardless of technical support for extra charges.

## Evidence required before choosing a live adapter

Record network/asset/contract/version, method semantics, authorization model, redacted
request/response examples, authoritative reconciliation evidence, failure/expiry
cases, exact reproducible commands, costs, and remaining limitations. Never record
credentials. Label simulated versus actual observations and distinguish submitted
transactions from confirmed settlements.

Current result: **not attempted**. The application supports only the explicitly
labeled mock adapter. Any future live executor must enforce deterministic policy,
persist requests before effects, and reconcile uncertain transactions before retrying.
