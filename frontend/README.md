# Frontend — Lucas

React/TypeScript is planned; no UI is scaffolded by this backend refactor. Lucas owns the
complete frontend lifecycle described in AGENTS.md and docs/responsibilities.md.

Use [API documentation](../docs/API.md), backend `/openapi.json`, and [contracts.ts](contracts.ts)
for the integration boundary. [Lucas handoff](../docs/handoffs/lucas.md) is the implementation
checklist. `/docs` remains authoritative for complete generated schemas. The generated API
types accompany the focused request/quote, funding and revision-bound helpers.

Phase 1 provides offline mock/fake payment contracts and [all payment-state fixtures](fixtures/README.md).
It does not claim a successful Base transaction. A local Python mock API makes fixtures
runnable now, without scaffolding Lucas's UI or waiting for wallet/RPC credentials.

First build prompt/clarification -> specification/quote approval -> work/evidence repair ->
cited output. Add buyer-wallet preparation/signature submission and payment polling, targeted
complaints, consent, explicit paid work and reviewer controls. Quote approval shows Base Sepolia,
USDC, exact settlement amount and conversion, payer/provider/operator and frozen deadlines.
The dedicated platform operator applies accepted settlement rules; escrow itself does not
verify document quality. This uses Base Commerce Payments, not x402.
Use server-based 60-second delivery/dispute timers, poll every two seconds, refetch on 409,
and retain historical PDFs. Evidence uncertainty, pending consent, human review, operational
failure (red) and mock money are distinct. Funding pending is not held; held is not paid;
capture/void pending is not completed; expired capture is not returned funds. Uncertain/reorg
states require recovery and must never trigger a fresh payment automatically. Rejected complaints
have no processing fee. New schema-4 snapshots add payment policy `catalog-payments-v1`;
historical v0.3 mock snapshots remain readable without live reinterpretation.

Only server-side trusted bridges may call provider/reviewer routes. Never place either token
in browser code. Customer authentication and production tenancy are not implemented yet.
Add package-manager/dev/test/deployment commands here when the UI exists. Validate highlight
alignment with Jeff and reconcile visual observations with Rehan's independent labels offline.
