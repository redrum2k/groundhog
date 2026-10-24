# Primary aggregate semantics — feature OFF

Worktree: `D:\Downloads\order-to-cash-dispute-20261024`.
Branch: `feature/broker-dispute-assessment-20261024`; integrated main `62fe035`.
Compiler fix `de53450`; primary integration `d2b6ba1`; equivalent-proof fix `5946378`.
Final tested code (including second-question recovery): `ef8c99afb9cf5f3b6928f505242f2d622fce2c3e`.
These follow-up commits are local, not pushed. Main was merged INTO this feature,
not the reverse. The earlier remote feature still contains `db7aab8`.

Read [PRIMARY_RESULTS.md](PRIMARY_RESULTS.md) for observed results, costs and limits.
The five DISPUTE documents and their exported cohort remain historical, unchanged.

## State and boundaries

R3 exclusion and R4 question-bound correction use the existing aggregate compiler.
History, intake deadline, question budget and immutable acceptance stay intact.
Built-in storage/PDF compilers no longer override aggregate compilation when paid
models are globally enabled; explicitly injected custom compilers remain supported.

Primary semantic work uses `investigation/dataset.py`, `orders/dataset.py`, the existing
Assessment/DatasetReference contracts and CatalogService/CatalogWorker transactions.
Durable attempts live in existing `catalog_records`, kind `dataset_assessment`;
they are an audit, not a second verdict store, ledger or payment authority.
Raw transport response, candidate, effective finding, binding, specification hash,
status and latency survive restarts. Replayed/uncertain attempts do not redispatch.

The independent gate recognizes bounded full-clause category-inclusion, gym-taxonomy
and ZIP-presence predicates, including supported negations/paraphrases. It checks
frozen contract terms and actual source/CSV cells. It rejects unsupported qualifiers,
undefined promises, missing authority and unsupported entailment. The equivalent
authority proof requires BOTH the exact gym/app definition and `yoga_is_gym=false`,
and only applies to the explicitly excluding accepted category. It does not use
model explanations as proof. It is not general natural-language arbitration.

`ENABLE_DATASET_MODEL_ASSESSMENT` defaults false and remains OFF. Global paid opt-in
does not enable it. The legacy `ENABLE_BROKER_DISPUTE_ASSESSMENT` stays OFF too.
No new server, deployment, real payment, correction or capture was enabled.

## Lucas: exact event mapping, no UI changes made here

Use the generated `DatasetFinding` and `VerdictEvent` in `frontend/lib/runs.generated.ts`.
Actual, unedited observed events with resolving evidence responses are committed in
[`docs/handoffs/primary-semantic-events.example.json`](docs/handoffs/primary-semantic-events.example.json).
Each entry has the case ID, actual run ID, full event (including seq/time/binding)
and exact evidence-resolution responses. These are synthetic mock-funded orders,
not made-up UI examples and not real settlement.

| Backend evidence | Meaning | Display / authority |
| --- | --- | --- |
| `check_passed` | One deterministic delivery check passed | Update that check only; never synthesize disagreement |
| `verdict.finding.effective.result=PASS` | Evidence supports the complaint | `finding.kind=supported`; observed root verdict is grey/human review, NOT automatic correction |
| `FAIL` | Evidence contradicts the complaint | Root verdict disagree; no complaint fee or immediate payment |
| `UNKNOWN` or `CONFLICT` | Unresolved interpretation | Grey/pending evidence or human review; never show final disagreement |
| `finding.candidate` | Raw proposed Assessment | Optional audit detail; never override effective result |
| `finding.decided_by=model` | Candidate passed independent validation | Model-assessed finding, not model-authorized money |
| `rules` | Independently established fallback | Explicitly rules-derived, not a successful model answer |
| `unresolved` / `ADVISORY`, `INVALID`, `STALE` | Candidate not applied | Keep held and preserve failure/provenance |

Consume the root `verdict.kind` as server disposition. Separately show semantic
support from `finding.kind`; do not map supported to an automatic "our fault" lane.
P1/P7 are supported yet grey; P4 is contradicted/disagree; P5/P6 are unresolved.
P3 remains the original raw PASS/effective UNKNOWN failure, despite the later fix.

Resolve `verdict.evidenceIds` through `GET /runs/{runId}/evidence/{evidenceId}`.
Use exact artifact hash, source/version/row/column/value from the response; don't
infer evidence revisions from card counts. `finding.assessed_binding` identifies
the model snapshot; `finding.binding` identifies the committing order revision.
For a new command, use the latest page's server binding and available actions,
not an old event binding. Preserve held/mock/expired/returned/captured distinctions.

Current primary `fold.ts` records backend verdicts and check events separately;
the old legacy adapter's verification-PASS shortcut is NOT the primary protocol.
The shared fold special-cases rules provenance for completed-step styling, and
the visual components do not yet expose this new finding provenance. Lucas should
review `frontend/lib/run/fold.ts` and the owned panels for model/unresolved styling,
then add replay/source-click/held-state browser acceptance. Do not replace
`frontend/components/run/run-app.tsx` with archived UI. No browser qualification
or UI implementation is claimed by this backend follow-up.

## Execution and evidence

The separate authorized window is `primary-semantic-followup-20261024`,
2026-10-24 11:19:36–12:25:38 Pacific. It retains the earlier absolute cutoff,
the original V6 window and the shared cumulative $45 ceiling/concurrency <=2.
No aggregate request-count ceiling exists. Never reset the ledger or reuse an
exported snapshot as a live ledger. No permission extends beyond the cutoff.

Live ledger: `D:/Downloads/order-to-cash-v6-20261024/backend/artifacts/v6-model-budget.sqlite3`.
The private ignored env remains in the original C: repository, never copied here.
Use CLAUDE_MODEL, not OBJECTION_MODEL. No billing/top-up/account-balance changes.

`backend/artifacts/primary-followup` contains additive authorization, original six-case
frozen plan/results/raw attempts/SQLite orders/HTTP events, the separate P7 development
probe, independent byte/cost audit and regression XML. `primary-amendment` retains
compiler XPASS-before-unxfail and all early test failures. Do not rerun either paid
runner to inspect it: both reject existing evidence. Both supervised children exited.

## Remaining work, not authorized activation

1. Lucas integrates and browser-tests the explicit mapping above; keep the flag off.
2. Run a separately preregistered independent semantic qualification if broader
   reliability is needed. Keep original P3/P6 and legacy N2/U1/J1/J2 in reporting;
   P7 was a development probe, not a held-out accuracy estimate.
3. Final full suite: 747 pass / 13 fail. Eleven are Windows payment-lab/platform
   checks and two are intermittent synthetic-broadcast observation races; the four
   settlement scenarios pass separately, without code changes. See PRIMARY_RESULTS.
   The owner can add Windows-aware test environment and permission checks and make
   the test await actual broadcast observation, not only pre-broadcast durable state.
   Don't weaken financial assertions, permission guarantees or network bans.
4. Any live activation, deployment, actual payment or merge into main needs separate
   authorization. New paid work after the cutoff also needs a new recorded window.
