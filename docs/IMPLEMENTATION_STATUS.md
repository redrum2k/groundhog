# Implementation status — integrated catalog v0.3 / payments v1

Updated October 24, 2026. Runtime, Base transport and catalog settlement are integrated on
`codex/backend-integration`. [Exact commits, tests and limitations](workstreams/04-integration.md).
The catalog API remains 0.4.0 / `catalog-api-v1`; payment policy remains `catalog-payments-v1`.
The invoice workbench retains its own policy and API at `/api/jobflow`.

## Demonstrated behavior

| Area | Integrated result |
| --- | --- |
| Request and agreement | Automatic persisted compilation/clarification, immutable server quote and schema-4 accepted payment terms. Stable checks, price/amount/parties/deadlines cannot be replaced by model output. |
| Runtime | CatalogWorker selects eligible drafts/jobs; independent catalog/invoice deadline, catalog work, invoice work and payment lanes. Bounded calls, durable leases, restart recovery, fenced stale results and draining shutdown. |
| Funding and fulfillment | Explicit simulated mock funding or confirmed Base funding enables the one reserved job. Actual source/PDF verification, source-derived sidecar and citations. No work on acceptance/signature/submission alone. |
| Repair and unresolved evidence | Registered same-edition repair produces a verified PDF. Unregistered readable repair reaches useful human review with no capture. Consent and substantive changes retain separate authority gates. |
| Settlement | Mock terminal booking is atomic. Base capture/void stays pending until matching canonical payment evidence and catalog booking commit once, in the same SQLite transaction. |
| Safety and recovery | Current binding/checks/evidence/amount/review/expiry gates before submission; late disputes cannot cancel submitted capture; uncertainty/reorg holds, exact replay, nonce serialization and one terminal operation. Replacement waits for confirmed parent void and its own funding. |
| Base transport | Pinned ABI, verified USDC domain, read-only deployment probes, dedicated operator signing, exact-byte outbox, event/state/receipt reconciliation. Fully exercised with synthetic RPC; no actual chain proof. |
| Configuration | Mock default; Base selected only during lifespan, with startup preflight. Missing signer/preflight failure disables submission without mock fallback. Import and OpenAPI export do not initialize RPC/signers or load .env. |
| Frontend contract | Same 26 catalog paths / 66 schemas, generated TypeScript and 12 simulated payment fixtures. Only health's existing live_adapter default changed from planned to disabled. Invoice's 10 paths/schema remain separate. |
| Ownership | Lucas's existing Next/React invoice UI is preserved; no catalog screens/server bridge were implemented. Jeff's semantics/documents remain intact. |

## Validation

Final backend suite: **442 passed in 57.00s**, one upstream websockets deprecation warning.
Ruff lint/format pass (107 Python files). Exact checks and commands are recorded in
[workstream 04](workstreams/04-integration.md).
The integrated HTTP/lifespan tests use temporary SQLite stores, synthetic PDFs, injected clocks,
offline compiler results and the actual Base transport with an RPC double. Independent synthetic
fund/capture and fund/void runs cross restart and only book after released confirmation evidence.
Tests also cover auth boundaries, signature redaction, stale 409s, exact response replay, model/RPC
lane isolation, shutdown, all payment states, legacy snapshots and invoice compatibility.

README repaired journey: closed, one mock capture, verified PDF. Unresolved journey: human_review,
nine evidence rows, zero bookings. The lab executes all 27 offline subprocess commands, including
separate expiry/reclaim. Local Uvicorn OpenAPI equals the export; the fixture server serves all
12 simulated states. Catalog generation/freshness and strict TypeScript compilation pass.
Frontend invoice generation check, typecheck, 29 tests and production build pass with Node 24.14.1.

## Evidence levels and remaining work

- **Mock:** simulated funding/booking, no chain transaction IDs or explorer links. Historical
  mock snapshots/responses stay mock and unchanged even when read by a Base-configured service.
- **Fake chain:** actual transport encoding/signing/reconciliation against injected RPC and public
  synthetic scalars. This is not EVM execution, deployed bytecode attestation or an actual receipt.
- **Implemented, not live verified:** RPC preflight, operator submission and lab payer reclaim.
  No real testnet transactions or live balances have been observed. No broadcasts are authorized.
- **Outstanding live milestone:** separately authorize fresh disposable setup; verify deployment,
  domain, historical RPC support, latency, test ETH/USDC, provider non-authority and independent
  100000-atomic-USDC fund/restart/capture and fund/void receipts. USD 15 catalog work still requires
  15000000 atomic USDC. [Runbook](PAYMENT_RUNBOOK.md) and [spike](PAYMENT_SPIKE.md).
- **Recovery limits:** no automatic rebroadcast, fee bump/replacement, orphaned-operation recovery,
  catalog payer-reclaim endpoint or refunds. Crash around durable submission may need manual
  recovery. Individual RPC calls are bounded; long multi-read preflight may exceed the payment
  lease and is fenced. Shutdown drains calls rather than killing Python threads.
- **Product limits:** local customer audit labels are not authentication; tenant isolation,
  production settlement, public deployment, arbitrary scanned PDF/OCR and live supplier authority
  remain outside the demonstrated demo. Offline model/semantic quality needs independent evaluation.
- **Team next steps:** Lucas owns catalog screens/wallet/server bridge; Jeff owns semantic/document
  quality; Rehan owns independent outcomes and actual sponsor requirements. Nikita owns the separate
  live preflight/proof and payment recovery. [Lucas recipe](handoffs/lucas.md).

No paid models, existing secrets/private databases, deployment, push or main-branch mutation were
used. The earlier 130-test catalog baseline, 180-test payment handoff and 296-test invoice merge
are historical milestones; final combined validation supersedes their completion claims.
