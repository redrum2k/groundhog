# DataPact canvas — Lucas

The demo route is `/`: the run canvas (`components/run/`) fed by Jeff's broker through
`/api/broker-run` (driver, translate, store under `lib/run/broker/`), with the recorded
scenario (`lib/run/scenario.ts`, `lib/run/source.ts`) as the fallback feed.
Nikita's aggregate intake (`components/run/live-run.tsx`, `lib/run/live.ts`) is mounted at
`/live`. Both read the generated Pydantic DTOs; `lib/run/contract.ts` re-exports them and adds
the canvas-only `caption` event. Preserve the canvas's visual design.
Read HACK.md and docs/workstreams/06-data-broker.md for current prices and timing.
The bridge permits only loopback local-demo mode with distinct server-only credentials.
Generate catalog, runs, jobflow, broker and improvement clients together; never hand-edit them.

The remaining catalog/PDF guidance applies to retained compatibility behavior:

# Complete frontend — Lucas

Follow root AGENTS.md, HACK.md and docs/API.md (catalog v0.3, payment policy v1). Own prompt intake/clarification,
specification and quote approval, progress, delivery/payment status, PDF/highlights, targeted
complaints, evidence responses, amendment upload/status/approval, paid-work acceptance,
human-review table/controls, buyer-wallet typed-data signing, polling/stale handling/timers
and frontend deployment. Phase 1 is the mock/fake contract handoff; a live testnet outcome
must never be inferred from fixtures or API capability fields.

Use React/TypeScript; the full UI is outside this backend refactor. See contracts.ts and API
examples. Poll runs every one second (legacy orders every two seconds), stop on unmount, and use server_time plus persisted deadlines.
Delivery and dispute windows are 60 seconds. Refetch on 409; never silently reapprove stale work.
Red means operational failure. Show evidence gaps, pending consent, human review, synthetic
fixtures and mock payments distinctly. Quote approval displays network, token, exact amount,
receiver, operator, conversion and funding deadlines. Acceptance, buyer signature, submission,
held funds and payment completion are separate states. Expiry is not a returned payment.
Unsupported complaints have no fee. Additional work
requires an explicit offered job/price/terms and separate quote acceptance.

Jeff supplies normalized citation rectangles; validate crop/rotation against actual PDF pages.
Historical source/output versions remain inspectable. Worker/reviewer routes need a server-side
bridge. INTERNAL_API_TOKEN and REVIEWER_API_TOKEN must never enter browser/NEXT_PUBLIC code.
Operator keys, signed authorization capabilities and raw signed transactions never belong in
fixtures, logs, analytics or model context. Sign exactly the prepared typed data; rejected wallet
signatures are not accepted orders or payment success. There is no general customer capture/void
endpoint. Show a provider/operator trust disclosure. Use fixtures/ for every payment state.
Rehan owns independent evaluation labels; keep them offline. Document run/test commands when
scaffolding the UI. First deliverable: request/approve work, inspect citations, answer a repair request.
