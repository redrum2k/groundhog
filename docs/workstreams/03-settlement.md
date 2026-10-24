# Workstream 03: asynchronous catalog settlement

Branch: `codex/catalog-settlement`. Starting commit: `ac385a1`.
Implemented and tested offline with synthetic accepted terms, temporary SQLite databases,
injected business clocks and a fake transport. No RPC, live adapter, paid model, testnet
broadcast or deployment was used. No observed testnet success is claimed.

## Configuration and injection contract

`CatalogService(repository, artifact_root, clock=utc_now, *, compiler=None, assessor=None,
auto_mock_funding=False, payment_mode="mock", payment_config=None, payment_transport=None)`
retains existing constructor behavior. Base mode requires explicit configuration and rejects
`auto_mock_funding=True`. It never reads environment variables or constructs a live adapter.

The injected configuration uses the existing `BasePaymentConfig` attributes: `chain_id`,
`usdc_address`, `escrow_address`, `collector_address`, `operator_address`, `provider_address`,
`confirmations`, and `enable_testnet_broadcast`. Base quotes require an explicit payer. Missing
payer is 422; unavailable operator/provider is 503. Accepted terms freeze all parties,
integer amounts, deployment, salt, hashes, conversion and absolute deadlines. Initial work
remains 15000000 atomic test USDC; additional/replacement work is 5000000.

The transport implements the unchanged `PaymentTransport` interface and additionally exposes
`verified_usdc_domain() -> dict`. Preparation calls that method **outside SQLite transactions**,
validates its chain/token/domain shape and rejects the mock domain. Conversation 2 owns actual
DOMAIN_SEPARATOR verification and deployment preflight. The resulting domain and exact typed
data are persisted in the existing `funding_preparation` record. Authorization checks the
signature against those frozen terms/domain; it never guesses the USDC name. Exact preparation
replay returns the persisted response without another RPC/domain lookup.

`SignedTransaction` and `ChainObservation` are unchanged. `payments.work(limit=20)` remains the
entry point, with limits 0–20. It uses the existing `PaymentExecutor` and its guard, changed and
complete hooks. Real signing/submission requires the injected configuration's explicit
`enable_testnet_broadcast` flag; the transport still enforces its own opt-in/preflight. Tests
use `is_fake=True` on a network-free transport. Reconciliation continues without broadcast
permission. The catalog journal always uses **the catalog repository's SQLite file**; it does
not open `payment_config.journal_path` or create another ledger.

## Transaction boundaries and policy

- Quote acceptance atomically persists the immutable snapshot, payment account and one queued
  fulfillment job. Preparation, signature authorization and submission do not claim or run it.
- Signature acceptance atomically reserves the funding intent and saves the exact command
  response. Signatures/raw transactions remain in private journal storage, not public responses.
- Executor nonce reservation and signed-byte/hash persistence use the existing journal. Transport
  calls/signing occur outside the SQLite lock. The final guard and durable `submitted` transition
  share a transaction, before broadcast. Crashes reconcile that exact hash/nonce; no automatic
  replacement or rebroadcast is introduced.
- Funding confirmation, journal evidence/effect, account state and catalog authorization commit
  together. The existing reserved job becomes eligible; confirmation never appends another job.
- Capture reservation and catalog acceptance/timeout decisions commit together. Before signing
  and submission, the guard checks current snapshot/evidence/delivery binding, accepted amount
  and authorization deadline, confirmed funding, mandatory checks, material blockers, authority,
  pending approvals, disputes, acceptance/review expiry and terminal exclusivity. An agent report
  alone cannot reserve capture. Malformed/missing assessment dependencies fail closed.
- Capture/void remain pending without bookings or closure. The confirmation callback atomically
  appends the existing catalog booking and journal effect. Callback failure rolls both back.
  Journal uniqueness prevents repeated funding effects or terminal bookings across restart.
- An unsubmitted stale capture is invalidated and releases its unused nonce. A later eligible
  decision can reserve a new operation key against the **same** accepted payment/salt; old keys
  and saved responses remain unchanged. Failed operations require explicit resolution; there is
  no automatic new transaction after a definitive failure.
- Submitted capture is never invalidated by later input. A complaint received while capture is
  submitted/uncertain enters human review, including after the original delivery review ends.
  It preserves the transaction and binding being reconciled. Confirmed capture still books once;
  the late case remains in human review, without an implied refund or cancellation.
- Matching event name/payment hash/full amount and matching escrow state at the receipt's exact
  block are required. Missing/mismatched evidence is uncertain; subthreshold evidence is pending.
  Noncanonical/changed blocks become `reorg_hold` and require explicit recovery. Existing financial
  history and deliveries remain intact. Temporary receipt loss never erases a booking.
- Audits of confirmed funding cannot overwrite a concurrently reserved terminal action's pending
  account state. Confirmed receipt audits do not invoke the effect callback again.
- A substantive child starts as `blocked_parent`. Only confirmed full parent void unblocks signing;
  child work still needs its own confirmed funding. Pending, failed and uncertain returns leave it
  blocked. Waiting never extends accepted deadlines: a late return leaves expired child funding
  failed. A parent reorg also blocks child preparation/submission/work and settlement gates.
  Additional work has its own accepted price/payment/job and does not void its parent.

The injected clock controls catalog deadlines. Existing executor lease/nonce bookkeeping still
uses the journal's wall clock. No persistence migration or shared repository/API extension was
needed; original tables, uniqueness constraints and atomic repository operations are reused.

## Existing public contract

No DTOs, route signatures, generated files, startup selection, frontend or invoice modules were
changed. Existing pending payment states express asynchronous settlement: an order can remain
`delivered` with `capture_pending`, or in human review/pending approval with `void_pending`.
Orders close only after confirmed terminal evidence, except late capture disputes that remain
in human review. `available_actions` suppresses acceptance/funding controls when payment or
parent-return gates fail and exposes the supported late-dispute path. Standard 409 binding,
revision and changed-idempotency behavior remains; invalid signatures are redacted 422 errors.

Historical schema-3 orders remain read-only. Stored schema-4 mock terms, operations and exact
command responses remain mock, including when loaded by a service configured for Base. Mock
capture/release keeps its synchronous atomic behavior and original intent fingerprints. No
mock receipt gains chain evidence or explorer links. Fake Base tests use synthetic transaction
hashes solely as offline fixtures and do not populate explorer links.

## Demonstrated transitions and tests

`backend/tests/payments/test_catalog_settlement.py` exercises actual SQLite persistence and the
catalog compiler, source verification, evidence repair and PDF delivery path with fake transport:

- accepted → awaiting signature → reserved/submitted funding → confirmed funding → one claimable job;
- delivered → capture pending → submitted → confirmed/one booking; injected callback failure
  proves the journal effect and catalog booking roll back together;
- dispute/evidence change before submission → invalidated capture → later valid capture;
- submitted capture → late dispute/human review → confirmed capture with the case retained;
- amount/verification/authority/consent/expiry changes → capture invalidation without transfer;
- pending/uncertain/reverted parent void → blocked child → confirmed return → separate child funding;
- parent return after child's fixed funding deadline → failed child, no deadline extension;
- additional-work child without parent void; competing capture/void has one durable winner;
- exact replay, concurrent job claims, restart, ambiguous submission, missing/wrong event/state/block,
  confirmation threshold, receipt loss and reorgs; no duplicate transfers, deliveries or bookings;
- verified-domain lookup outside database locks, mock-domain rejection, wrong-domain signature
  rejection, mock simulation rejection for Base, and exact replay without domain availability;
- byte-for-byte preservation of stored mock records, command responses and financial effects.

Validation commands actually run (uv cache override on run commands only avoids the local cache
sandbox restriction):

```sh
uv sync --locked --project backend
UV_CACHE_DIR=/tmp/catalog-settlement-uv-cache uv run --locked --directory backend pytest tests/payments tests/api tests/catalog tests/legacy tests/runtime tests/investigation
UV_CACHE_DIR=/tmp/catalog-settlement-uv-cache uv run --locked --directory backend pytest
UV_CACHE_DIR=/tmp/catalog-settlement-uv-cache uv run --locked --directory backend ruff check .
UV_CACHE_DIR=/tmp/catalog-settlement-uv-cache uv run --locked --directory backend ruff format --check .
git diff --check
```

Final verification: **332 passed** in the full backend suite (41.91 seconds), including the
preserved invoice/jobflow tests. The dedicated settlement file passes **36 cases** (8.01 seconds).
The requested combined catalog/API/payment/legacy/runtime/investigation run passed **246 tests**
before the final two regressions were added; both are included in the final full-suite result.
Ruff lint passes; format check reports all **96 Python files** formatted; `git diff --check` passes.

## Precise integration requests and limits

1. Conversation 4: pass the explicitly selected mode/config/transport into `CatalogService` and
   continue invoking bounded `payments.work()` independently of fulfillment dispatch. Keep
   `claim_job()` as the authoritative job eligibility gate; a queued job alone is insufficient.
   Bind the journal to the catalog database, even if the isolated runner uses another file.
2. Conversation 2: supply `BasePaymentTransport(config, *, rpc=None)` with verified domain lookup;
   reconcile payment-specific event/state at the receipt block. The generic executor now rejects
   event/state block mismatches, so returning latest-head state with an older receipt is insufficient.
   Preserve private authorization handling, zero-fee/full-amount semantics and broadcast opt-ins.
3. Conversation 4: update health/startup capability disclosure and the shared Lucas/runbook/status
   docs, which currently describe asynchronous settlement as planned and the worker as mock-only.
   `PaymentWorkResult.simulated` now reflects the configured service mode. No public schema fork
   is proposed; show payment state alongside order/case state and refetch after exact saved replay.
4. Human recovery remains necessary for orphaned receipts and an unresolved crash around broadcast.
   There is no automatic rebroadcast, replacement transaction, refund, payer-reclaim catalog route,
   production authentication/tenancy, or live finality claim. An unchanged confirmed receipt can
   clear transient payment uncertainty without rebooking; human-review cases are not auto-dismissed.
   A failed replacement return can be explicitly retried through the existing cited reviewer
   release decision, but never silently unblocks or closes its child/parent.
