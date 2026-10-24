# Primary semantic foundation — compiler fixed, feature OFF

Separate follow-up to `db7aab832ad34b7d889ce6a07a5e855c2ee01107`, not a V6 or
legacy dispute rerun. Worktree: `D:\Downloads\order-to-cash-dispute-20261024`.
Branch: `feature/broker-dispute-assessment-20261024`.
Exact final code tested: **`ef8c99afb9cf5f3b6928f505242f2d622fce2c3e`**.
Later delivery commits contain reporting only; the archive receipt names its exact source commit.
Main `62fe03542f18d9f7514550bcff25968ae2557c08` was integrated INTO this branch.
No commit was pushed during this follow-up, no merge into main, deployment or real payment.

## Implemented and reused

- R3/R4 fixed in `agents/dataset.py`: explicit exclusion cannot become yoga-inclusive;
  question-bound cohort/geography corrections replace the proposed field, not original
  history. Contradictions clarify within existing question/deadline limits. Original
  strict xfail tests produced XPASS before their markers were removed; XML is retained.
- Kept the aggregate compiler active when built-in catalog model compilation is selected.
  Storage/PDF prompts cannot override the primary contract's R3/R4 protections.
- Reused current `investigation/dataset.py`, `orders/dataset.py`, `ClaudeGateway`,
  Assessment/evidence contracts, existing catalog records, worker leases, event log,
  source resolver and all financial gates. No duplicate order engine or payment ledger.
- Reused `db7aab8`'s bounded Anthropic client, cumulative SQLite budget, durable-attempt
  pattern, raw/effective separation and exact source references. Legacy broker code
  and its five DISPUTE documents remain intact; primary assessment is at `/runs`.
- Added full-clause category/taxonomy/coverage interpretation with independent proof
  checks, typed persisted primary findings, a default-OFF flag, guarded dispatch,
  stale-result rejection, explicit failure fallback and Lucas's event handoff.

PASS supports the complaint; FAIL contradicts it; UNKNOWN/CONFLICT are unresolved.
Supported source meaning is NOT established provider-output fault. Supported P1/P7
remain grey/human-review with zero corrections or payments. No model verdict can
authorize refunds, charges, consent, scope changes or financial execution.

## Fresh actual model evidence

The original six-case plan froze before calls on implementation `d2b6ba126f0c8fa0ba37b7b0be38eaa269a4645c`.
All cases used fresh, explicitly accepted, mock-funded primary orders and real HTTP
commands/events, actual production/verification, no corrupted-delivery bypass.

| Case | Complaint/fact | Raw | Effective | Input/output (thinking included) | Seconds | Estimated USD |
| --- | --- | --- | --- | --- | --- | --- |
| P1 | Yoga covered by explicitly expanded accepted scope | PASS | PASS, model; grey | 5786 / 1177 (521) | 19.532 | 0.046684 |
| P2 | Yoga belongs in explicitly excluding scope | FAIL | FAIL, model; disagree | 5776 / 770 (0) | 9.047 | 0.038504 |
| P3 | Negative yoga-scope paraphrase, genuinely true | PASS | **UNKNOWN, false-negative gate** | 5775 / 669 (91) | 8.156 | 0.036480 |
| P4 | ZIP 94110 allegedly omitted; actual CSV contains it | FAIL | FAIL, model; disagree | 5581 / 547 (0) | 7.282 | 0.033264 |
| P5 | Undefined executive-ready fitness promise | UNKNOWN | UNKNOWN; grey | 5768 / 819 (132) | 9.719 | 0.039452 |
| P6 | Yoga-as-gym claim with null taxonomy authority | **FAIL, wrong** | UNKNOWN, correctly held | 5770 / 1047 (394) | 11.657 | 0.044020 |

Six-case subtotal **$0.238404**. Raw and effective outcomes were each 5/6 correct,
with DIFFERENT failures. These diagnostic counts are not a general accuracy estimate.

P3 exposed a complete but alternative source proof that the gate did not accept.
Commit `5946378` adds that proof only for the exact excluding contract and both
resolving authority cells. Missing-cell, wrong-polarity and expanded-scope regressions
still abstain. Original P3 remains unchanged, not rerun or regraded.

A separately frozen **development** probe P7 used a new order and new negative
paraphrase: "Standalone yoga does not belong in the agreed fitness scope."
Raw/effective PASS, validated through exact `definition` plus `yoga_is_gym=false`,
grey/human-review and no financial effects. 5775 input / 564 output, 0 thinking,
8.657 seconds, **$0.034380**. This verifies the new proof path, not held-out accuracy.

Every actual response identified **claude-opus-5-5**, `end_turn`, standard/global.
Seven calls total: **40,231 input**, **5,593 output including 1,138 thinking**, zero
cache tokens. Total **$0.272784**. No semantic retry or reroll. Independent audit
recomputed all costs and resolved **26 raw/effective citation occurrences** by
hashing/parsing saved JSON/CSV bytes without the runtime resolver.
Pricing: [Anthropic's official pricing](https://platform.claude.com/docs/en/about-claude/pricing),
checked 2026-10-24, $4/M input and $20/M output. These are estimates, not invoices.

Frozen first-cohort backend/lock hash:
`9146b16232aaae8bbaccad047dbc198b8ab9f1b19d1298291bd7950d1fc0423f`.
Proof-fix/P7 runtime hash:
`edd51f59d67d340be3b1112f0769e592db25676532796d4662965b7a5be9c112`.
Do not present the six-case cohort as having run on the later implementation.
A later no-call compiler hardening clears an earlier unbound field contradiction
only when a valid question-bound answer corrects that field. The final source differs
from the P7 fingerprint in that compiler fix; semantic proof code is unchanged.
Final tested runtime hash:
`bab24ab2a16f0b4319dba61ea4c29ba1559e60ecfda1a84973b58f55fdc30604`.

## Resource accounting and preservation

Separate recorded window: 2026-10-24 11:19:36–12:25:38 Pacific, authorization SHA-256
`d77d368644d3c4fc9e7d757ab5e7455819be84703cb24d6570bd35d31f2d9f68`.
Original V6 cutoff and prior window records were not reset. Shared ledger now has
29 historical reservations, **$1.053300 known estimated use**, **$1.425636 conservative
committed cost**, zero active calls, original **$45 ceiling** and **$10 final reserve**.
Unknown prior consumption stays conservatively charged. Counts are telemetry only.
Concurrency <=2, conservative pre-reservations, output/time bounds, no SDK retries,
rate-limit cooldown and repeated-failure controls remain. No account/billing change.

Original N2 (correct model/held interpretation), U1 (wrong model/correct hold) and
J1/J2 (production legitimately blocked dispute eligibility) are preserved exactly.
No old frozen suite, source, accepted contract or original result was edited.
Archive hashes rechecked unchanged:

- Original dispute ZIP: `c66f938e7959db0b2ab7da6be8d305988b148aac0ef3b117d3aa40783e02c159`.
- Original V6 ZIP: `06550571f57c77da42744d909f595f7e5e0dc6e0f72c92f4b3fb2628e2587b17`.

## Verification and unresolved risks

Focused compiler tests: 19 pass. Primary semantic tests: 38 pass, including full
offline HTTP rehearsal, actual evidence links, persistence/restart, concurrent
one-attempt dispatch, revision/binding/deadline rejection, invalid refs, wrong model
answers, provider timeout fallback, unknown authority and proof alternatives.
Frontend generated-contract check, TypeScript, **104 tests** and production build pass.
No Lucas UI/component/adapter was modified relative to main; only generated wire
types and hidden-window handling in the generator changed.

Final full backend run at `ef8c99a`: **747 passed / 13 failed / 0 skipped** (760 total),
`full-delivery-ef8c99a.xml`. All 19 compiler and 38 primary semantic tests pass in
that full run. Ruff lint/format passes (172 Python files including delivery tools).
Eleven failures are unchanged main Windows portability checks: nine stripped-SystemRoot
subprocesses, one POSIX mode assertion and one `.venv/bin/python` path. Two further
unchanged Base-transport tests intermittently observe durable `submitted` state before
the synthetic broadcast list is populated. The executor intentionally persists first.
All four mock/Base settlement scenarios passed in a separate diagnostic run, without
code/test changes; the two full-run failures remain failures, not reclassified passes.

Earlier full runs are also retained: 743/11 (754 total) before the proof fix and
748/11 (759 total) after it. No test was skipped, xfailed or weakened to hide these
failures. No clean full-suite claim; Windows payment-journal ACL equivalence and
the asynchronous test observation race remain owner follow-up items.

The feature stays **OFF / not generally qualified**. The interpreter is deliberately
bounded, does not resolve arbitrary compound claims/quality promises, and does not
establish provider fault. P6 remains a real model error. Browser/source-click/provenance
display acceptance belongs to Lucas and was not performed. No full semantic release,
production settlement, economic gain or general arbitration reliability is claimed.
See [PRIMARY_HANDOFF.md](PRIMARY_HANDOFF.md) and
[PRIMARY_REVIEW_INCIDENTS.md](PRIMARY_REVIEW_INCIDENTS.md) for exact next steps/evidence.
