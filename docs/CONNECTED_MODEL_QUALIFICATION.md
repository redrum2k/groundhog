# Real Claude plus learned source procedures: integration test, October 24

## Verdict: connected execution works; full semantic qualification fails

Eight actual Claude Opus 5.5 calls used the primary application, ordinary running
worker, persisted source-owner procedures, accepted synthetic datasets and mock
payment adapter. Estimated additional usage cost was **$0.207804**, reconciled to
the existing cumulative ledger. No live financial broadcast or production change.

The three investigator responses were correct against the frozen author-defined
case expectations. Only **two of three** retained correct, model-provenanced
effective outcomes. The third exposed a genuine application limitation, not an
LLM failure: a correct semantic explanation was demoted by the proof grammar.
This does **not** qualify an unrestricted AI order-to-cash employee.

| Fresh case | Actual Claude result | Effective result | Finding |
| --- | --- | --- | --- |
| Alleged omitted ZIP 94110 | FAIL, cites actual delivered ZIP row | FAIL, model-provenanced | Correct contradiction, no automatic complaint fee |
| Accepted scope excludes yoga-only people; absence is not a defect | PASS, explains accepted exclusion and authority | UNKNOWN, deterministic guard | **Combined-product failure**: valid semantic paraphrase outside current proof grammar |
| Demand for person-level cross-ZIP deduplication proof | UNKNOWN, distinguishes contract assumptions from empirical evidence | UNKNOWN, model-provenanced | Correct actual model abstention, not an offline fallback |

PASS means evidence supports a complaint statement, not that the provider owes a
repair or that payment is authorized. No expected label was supplied to runtime.
These are development cases, not Rehan's independent evaluation or a reliability
percentage. The source-owner testimony and source data are explicitly synthetic.

## Integration with Nikita and Lucas

The isolated branch `feature/llm-learning-qualified-20261024` merges main
`8d47015b9263f5ab5fa48214eda1525a13e6642f`, including Nikita's
`a66c3cfdb452424a884aced148bc03370d7b1240` unified checkout/complaint changes.
There were no textual merge conflicts. Gateway wording repair, plain-text
complaint routing, financial contracts, payment code, $1 pricing, and frontend
checkout code were retained unchanged from main. The subsequent main update
`de1725008118171206628020751697381e2e657a` adds documentation only.

The live-model trial explicitly used Nikita's new `/orders/{id}/complaints`
plain-text command and asserted the actual accepted price object:
`{"amount_minor":100,"currency":"USD","decimals":2}`. Both `/` and `/live`
are now aggregate routes; the retained broker rehearsal is `/demo`.

The only new runtime integration change is an explicit Python test-process opt-in,
`source_learning_model_qualification=True`, on `create_app`. Startup otherwise
still rejects the combination of source learning and paid calls. The opt-in also
requires an open registered ModelBudget window, enabled model investigator, mock
payments and the existing distinct local role credentials. There is no environment
variable that silently activates this path in the normal deployed application.

## Observed connected behavior

- A genuine Claude intake clarification led to explicit buyer agreement and mock
  funding. Two source-owner resolutions were qualified, approved and activated
  through application commands, not by writing final answers into the runtime.
- Three new orders with different source bytes reused the approved version,
  avoiding both repeated source-owner reviews (same-byte stateless baseline: two).
- All 27 rows of each of four deliveries matched independently recomputed vendor
  values, the **accepted frozen derived source**, CSV bytes, and downloaded JSON.
- Training and the contradicted missing-ZIP order each had one terminal capture.
  Both unresolved orders had no terminal operation or ledger booking.
- Application shutdown/reopen retained learning, accepted snapshots, deliveries,
  decisions and financial records. Twelve commands replayed identically. This was
  an ASGI application lifecycle restart, not a new OS-process/browser demonstration.
- Seven candidate/effective citation references were independently reopened and
  checked by hash and exact cell. All eight raw provider responses reconciled to
  actual usage rows in the existing ledger; none was a simulated model response.

## Preserved evidence and technical recovery

Worktree: `C:\Users\sajee\order-to-cash-llm-learning-20261024`.
Evidence: `.local/connected-model-qualification/pilot/`.

`frozen-plan.json` and `capsule.json` name the LOCAL execution lane, original
commit `1c50134`, runtime source hash, frozen cases and authorization digest.
`http-trace.jsonl` contains application commands and saved responses without secret
headers. `call-*.json`, `recovery-calls/`, and `*-attempt.json` contain actual
requests/responses, raw/effective model findings and usage. Database/artifact bytes
remain private and local. `independent-model-audit.json` explicitly records
`combined_qualification_passed: false`.

The first driver stopped **after** the first successful real investigation because
it compared the structured Money object with the string `"1.00"`. The failure and
original supervisor logs are preserved. Recovery commit `5614708` fixed the harness
only, reopened the same database, reused that completed model assessment, and ran
the two not-yet-executed cases. It did not change application/model code, replay the
completed paid call, alter labels, or reset the budget. `technical-recovery.json`
and `recovery-supervisor.json` distinguish recovery from a scientific retry.

The paid window is **18:15–19:15 Pacific**, authorized for at most **$5 additional**.
The existing $10 reserve and all prior usage remain intact. A cumulative cap of
$17.129304 includes $2.129304 prior conservative commitments, the unchanged $10
reserve and the $5 allowance. Concurrency is one; SDK retries are zero; a hidden
parent process enforces a timeout no later than the authorization cutoff.
The test exited successfully; no paid worker/server is left running.

Audit without any model calls:

```powershell
uv run --locked --directory backend python connected_model_audit.py C:/Users/sajee/order-to-cash-llm-learning-20261024/.local/connected-model-qualification/pilot
```

Do not rerun this frozen cohort. A later quality change requires new cases and a
separately named output, within a valid authorization. The earlier 30-call
[aggregate qualification](../AGGREGATE_MODEL_QUALIFICATION.md) and the earlier
model-disabled connected safety trial remain unchanged historical evidence.

## Remaining product gap

`guarded_dataset_assessment` obtains the real model's answer but permits definitive
PASS/FAIL only when `independent_claim` recognizes a bounded language predicate and
the citations support it. The compound scope statement was correctly understood
by Claude, with valid authority/category citations, but `interpret_claim` returned
no certificate. Consequently the application retained an ADVISORY candidate and
produced deterministic UNKNOWN. The model did not lack the answer; the integration
could not use it.

Do not fix this by special-casing the tested sentence, by counting a safety hold
as success, or by letting any cited model claim authorize money. The next design
step is a general, evidence-grounded semantic disposition representation that can
cover multi-clause claims while keeping frozen scope, source authority, financial
gates and explicit abstention intact. That broader change was not silently made
as part of this test request.
