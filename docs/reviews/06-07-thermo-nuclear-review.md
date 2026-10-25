# Review of conversations 06 and 07

Reviewed October 24, 2026 using the local `thermo-nuclear-review` skill.
**Result: changes requested. The primary mock happy path passes, but prompt 06 is
not fully correct. Prompt 07 meets its offline preparation scope; it does not
establish live payment readiness.**

## Scope and evidence

- Original checkout: `main` at `ac385a1`; it does not contain the implementation.
- Reviewed combined worktree: `../order-to-cash-data-broker`, branch
  `codex/data-broker-migration`, HEAD `35194536da06481591291f2d486725ccb448e59d`.
- Migration implementation: `1956f18`, following integration merge `41ecf61`.
- Payment readiness: `f8a929a7fab2ac10ffee2a0aca112ca93a72fb2d`, merged by `6a714cf`.
- Verified ancestry of `39dd586`, `46f6c07`, `5c8dc72` and `f8a929a` in the combined
  HEAD. All prompt-07-owned files are byte-identical to its completed commit.
- Reviewed new/modified code and its interactions. Existing shared payment limits
  below are distinguished from regressions introduced by these sessions.
- After the independent audit, `gh pr list --state all --head <branch>` returned
  no PR for either task branch. There was no associated BugBot/PR discussion to incorporate.

Every finding below was reproduced against temporary synthetic state. Prior session
claims were not counted as fresh verification. No private environment, wallet or
existing application database was opened. No paid model, real RPC, broadcast or
deployment was performed.

## Findings

### R1 — P2: malformed dataset JSON can expose a suppressed exact count

Location: `backend/app/datasets.py:589`, reached through
`backend/app/api/catalog.py:230`.

`public_bytes` only validates JSON as a dataset if it contains `count_unit`, or as
a manifest if it contains `csv_sha256`. JSON missing both markers is returned
unchanged. Malformed provider data therefore bypasses the safe-count check that
correctly blocks well-formed but unsafe datasets.

Reproduction: create a synthetic run; register version 2 of the gym/app source
with `count_unit` omitted and ZIP 94129 set to `{count:42,status:"suppressed"}`;
compile, quote and accept the frozen source. Independent verification returns
`passed=false`, but the actual artifact route returns HTTP 200 and the exact 42.
No model verdict or payment is needed to reach the download.

Fix: select the allowed artifact schema using trusted registered artifact/source
kind, or validate a strict allowlist of source, manifest, coverage and authority
schemas. Unknown/malformed JSON must fail closed. Preserve original evidence
privately while preventing unsafe public downloads, resolutions and event payloads.
Add an HTTP regression for missing/renamed discriminators, not only unsafe CSV.

Owner: Nikita's artifact boundary, with Jeff on evidence/schema semantics. This is
a demo-contract violation on synthetic data, not evidence of an actual personal-data leak.

### R2 — P2: evidence-answer references are validated and then discarded

Location: `backend/app/orders/runs.py:310`; downstream
`backend/app/investigation/dataset.py:111`.

`Runs.answer` resolves each submitted reference, then saves only answer text or an
`answered` boolean. It advances evidence revision and enqueues re-verification,
but neither the order's evidence-answer history nor the investigator receives
the submitted references. The idempotency table retains a fingerprint, not the
reference payload. The investigator reconstructs only `definition` and
`yoga_is_gym`, so a cited answer cannot add its requested source passage.

Reproduction: an injected conservative assessor asks for evidence; submit a
resolving frozen `yoga_category="Wellness"` reference with text "See the cited
taxonomy cell." The next assessor call receives the text but its only evidence
columns are still `definition` and `yoga_is_gym`. The accepted reference is lost,
and the question budget is consumed without assessing it.

Fix: persist a typed answer with request/case, actor, text, references, original
binding and receipt time atomically; feed its allowlisted resolving passages into
the next assessment. Preserve deadlines and immutable accepted terms. Prove this
across restart, exact replay and stale-binding rejection. The frontend currently
always submits `references:[]` at `live-run.tsx:90`; Lucas also needs a way to
select a resolving reference, especially for source repair where it is mandatory.

Owner: Nikita for durable answer/context transport; Jeff for assessment use;
Lucas for evidence selection.

### R3 — P2: a negative yoga instruction becomes an inclusion term

Location: `backend/app/agents/dataset.py:26`.

The substring test for `include yoga` also matches `do not include yoga`.
Submitting "SF adults 25-34, gym membership or fitness app users. Do not include
yoga." produces a ready specification with `category="gym_app_or_yoga"`.
The server then quotes a different dataset from the requested scope.

Fix: use an explicit bounded category choice, or recognize affirmative/negative
answers and clarify ambiguous text conservatively. Test exclusion, inclusion,
negation and contradictory answers. Explicit quote acceptance remains a safeguard,
but it does not make an incorrectly compiled specification correct.

Owner: Jeff's compiler semantics.

### R4 — P2: a customer cannot correct an unsupported cohort during clarification

Location: `backend/app/agents/dataset.py:11` and `:20`.

The compiler concatenates the original prompt with every answer, then rejects if
any age range in that accumulated text is unsupported. The original rejected
range can never be superseded by an explicit answer.

Reproduction: request SF adults 18-24 with gym/app scope; answer the server's
clarification with "Yes, change to San Francisco adults 25-34 grouped by ZIP,
gym membership or fitness app use." The next result is the same cohort
clarification. Repetition exhausts the two-question budget despite agreement.

Fix: resolve current terms from question-bound answers with explicit precedence,
while preserving original testimony/history. Do not delete the original prompt
or extend the intake deadline. Test corrected age/geography and unresolved conflicts.

Owner: Jeff's compiler semantics.

### R5 — P2: the live canvas continues to show held funds after return

Location: `frontend/lib/run/fold.ts:88`, consuming the new
`backend/app/orders/run_events.py` payment/state effects.

The fold updates money only on `payment_authorized` and `payment_captured`.
`state_changed.paymentState` is ignored. An approved return produces a correct
backend `voided` state but leaves the canvas coin at `$120 held · mock`.

Reproduction: fund/deliver, enter human review and approve return through
`Runs.decide`. Replay those actual persisted events in the production UI.
The Funding heading reads `Funding · voided` while the canvas reads
`$120 held · mock`. Screenshot: `/private/tmp/datumco-thermo-browser/void-shown-held.png`.
This browser reproduction injected the generated backend event page into polling;
it did not execute a live chain return.

Fix: project current financial state consistently across the canvas and panels.
Cover void pending, returned, uncertain, expired-but-not-returned and reorg hold,
including recovery after an earlier capture event. Preserve historical events;
do not infer a return from expiry. Test transitions/replay, not just isolated state
headings. Keep mock disclosures and null hashes.

Owner: Nikita/Lucas shared event contract, Lucas's UI projection.

### R6 — P2: the live complaint form targets every complaint at category

Location: `frontend/components/run/live-run.tsx:82`.

The form always submits `R-CATEGORY`, `field="category"`,
`product_id="dataset"`, `intent="dispute_fact"`, regardless of the selected
row or complaint. Users cannot target a ZIP/coverage, cohort or provenance issue
through the live canvas, and scope requests are mislabeled factual disputes.

Reproduction: "ZIP 94110 is missing from the delivery" with the correct API
binding `R-COVERAGE/coverage/94110` resolves against the actual CSV as unsupported
(`FAIL`, no question). The same text with the form's hardcoded binding produces
`UNKNOWN` and asks which authority establishes yoga membership. This needlessly
blocks review and consumes the investigation budget for an unrelated question.

Fix: bind complaints to an explicit accepted requirement and, where applicable,
a dataset row/cell; distinguish scope requests. Generate the DTO mapping and
test the complete form-to-backend journey. Do not solve it with a hidden browser
scenario or a hardcoded verdict.

Owner: Lucas's complaint controls, with Nikita/Jeff on API validation and semantics.

## Prompt 07: completed scope and remaining shared work

No new medium/high defect was found in the small lab exit-status change. Its
regressions correctly distinguish reserved/signed/pending from success, and its
read-only probe recipes fail closed on generic RPC errors. Its four owned files
remain unchanged in the combined branch.

Two limits reproduced and disclosed by prompt 07 still exist in shared baseline
code; these are not newly introduced prompt-07 bugs:

1. Sequential RPC preparation can exceed the 120-second claim lease. The existing
   slow-RPC test advances 136 simulated seconds at four seconds/read; persistence
   and send are fenced, but there is no renewal. Total time must also fit frozen
   funding/capture deadlines.
2. A crash after durable `submitted` persistence and before broadcast can remain
   pending indefinitely. Ordinary reconciliation preserves identity and never
   rebroadcasts. A bounded, audited exact-byte recovery operation is still absent.

Nikita owns those shared executor/journal fixes. Use the exact reproduction and
constraints in `../order-to-cash-data-broker/docs/workstreams/07-payment-readiness.md`.
No live endpoint, deployment state, latency, balances, real buyer signature,
provider exclusion or testnet receipts were observed in this review.

## Fresh validation

| Check on the combined tree | Result |
| --- | --- |
| `uv sync --locked --project backend` | Passed |
| Full backend `pytest` | 615 passed, 84.94 s; one upstream websockets deprecation warning |
| Backend Ruff lint and format, including brokerage runner | Passed; 147 files formatted |
| Frontend under Node 24.14.1 | 88 tests passed, typecheck passed |
| `npm run generate:check` | Passed |
| Production frontend build | Passed |
| Isolated payment examples | All 27 offline CLI processes passed |
| Offline brokerage acceptance | Conforming capture, injected producer correction, separately funded Oakland, cited yoga resolution passed |
| Production browser smoke through real local backend | Passed; Chromium 156.0.8078.4, no page errors |
| Additional targeted probes | Reproduced R1–R6 above |

The production happy-path run was
`request-dda9af71468744d3bddb38eef95db028`. Its temporary DB/artifacts were created
under `/private/tmp/datumco-thermo.uOvnm4`. Browser evidence is under
`/private/tmp/datumco-thermo-browser`: CSV, delivery/capture screenshots,
events/payment page and trace. Offline acceptance evidence is under
`/private/tmp/datumco-review-acceptance/broker-qkp8mksp`. These are synthetic local
artifacts, not committed or live settlement evidence.

See [test the platform now](../TEST_PLATFORM_NOW.md) for repeatable commands and
[Nikita corrective prompt](../codex-prompts/08-review-remediation.md) for the next
runtime work. A new feature/deployment milestone should wait for the review fixes.
