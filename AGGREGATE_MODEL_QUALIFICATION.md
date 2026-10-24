# Real aggregate intake and dispute qualification — October 24, 2026

## Result

Actual **Claude Opus 5.5 (`claude-opus-5-5`)** calls completed through the existing
guarded client and primary aggregate HTTP/service workflow. The reported
`fitness -> gym membership` conversation progresses to a precise broader-product
offer; only a separate buyer `yes` produces ready draft terms. No repeated-question
loop, contract acceptance or payment is manufactured.

The six pilot intake cases passed. Two pilot dispute limitations were found and
preserved, then addressed: taxonomy must not be inferred from contract exclusion,
and a bounded scope-first paraphrase needed an independently checked predicate.
Five fresh dispute follow-ups passed both raw-model and effective-outcome checks.
A further regression exposed bare `yes` failing to confirm a cohort; after fixing
that binding, four fresh real intake cases passed, including confirmation/refusal.

This is **bounded scenario qualification**, not independently reviewed, blind
held-out accuracy or unrestricted dispute competence. All model-dependent features
remain OFF by default. No main merge, deployment, live-server restart, real payment
broadcast, automatic rule activation or new purchase occurred.

PR: https://github.com/redrum2k/order-to-cash/pull/12
Branch: `feature/aggregate-intake-integration-20261024`.

## Authorization and execution boundary

The user's new 90-minute authorization is recorded as the conservative window
**12:52:00–14:22:00 Pacific, October 24**. Start was rounded down from the first
observed receipt-time clock, 12:52:17; this does not extend the authorization.
Receipt SHA-256: `40edb68196577d22c7684870c86a7c1de9d9620f660af5739c8742be50f34a78`.
Old V6 and follow-up cutoffs, prior charges and uncertain reservations remain intact.

`aggregate_qualification_access.py` registers a new immutable window in the same
existing ledger. It verifies the configured ledger path and `CLAUDE_MODEL`; only
the isolated process receives the new window and paid-call settings. No private
`.env`, shared main configuration or production flags were edited. The API key was
loaded privately, never printed or copied into evidence. Anthropic's model lookup
confirmed `claude-opus-5-5` for this account in each cohort.

The existing guard reserves cost before requests and reconciles actual usage.
Maximum aggregate expenditure remains **$45**; the existing **$10 final reserve**
was retained. There is no aggregate request-count ceiling. Concurrency cap is two;
observed peak was **one**. Requests had 4,096 maximum output tokens, 20-second
timeouts and zero SDK retries. All 30 requests completed within the new window,
below their reservations, with no outstanding requests or provider transport errors.
Each cohort had an independent hidden-window parent/child timeout; all exited zero.
The 30-call count is message inference; three model-availability lookups are separate
metadata requests, recorded in the bundle.

## Evidence and audit

- [Full generated evidence bundle](docs/evidence/aggregate-qualification-20261024.json):
  frozen plans, authorization receipt, provider model availability, actual request/
  response traces, typed proposals, transcripts, events, accepted synthetic terms,
  raw/effective findings and actual synthetic CSV/JSON source/output bytes.
- [Ledger audit sidecar](docs/evidence/aggregate-qualification-ledger-20261024.json):
  exact call IDs, timestamps, request hashes, usage/cost reservations and window checks.
- Bundle SHA-256:
  `1e41182345897d69743b1ae622b48bb24573cdbce60d2c1a40849beb4728e123`.

The publication uses canonical LF line endings, including on Windows checkouts.
The original CRLF draft was archived before normalization; parsed JSON and embedded
artifact bytes are unchanged. The generator now forces LF, and the hash above was
checked against the actual Git blob rather than only the local working file.

`aggregate_qualification_audit.py` reuses the existing independent exact-cell auditor.
It reopens and hashes actual saved bytes, checks **37 candidate/effective citation
references** without using the runtime resolver, and reconciles every response's
usage/cost to the shared ledger. Valid citations alone are not treated as entailment:
the pilot's model error and false-negative gate remain explicit below.

Expected outcomes and their rationales were frozen in evaluator-side plans before
each cohort. Runtime receives only customer text, accepted terms and allowed actual
evidence—not those labels or mutation metadata. These are author-defined development/
acceptance cases, not a claim of Rehan's independent review. Old P1–P7 and legacy
dispute cohorts were not rerun, relabeled or overwritten.

## Versions and incidents

| Cohort | Implementation / treatment |
| --- | --- |
| Pilot I1–I6, D1–D5 | Harness `82bc5ba`; application inherited from `706f41e`/published `849e98a`. Six intake passes; raw and effective dispute outcomes each 4/5, with different failing cases. |
| Follow-up F1–F5 | `1b7ed755a870a04d78320ba2fd7a54bf6e3e831d`: explicit taxonomy-authority instruction and whole-clause scope-first predicate. Five new orders/paraphrases; all raw/effective outcomes correct. |
| Confirmation C1–C4 | `b9476d930b413f03a6d86582d9596c1e3a052a2f`: cohort-offer confirmation binding. Four new intake requests; all acceptance checks pass. Dispute implementation is unchanged from `1b7ed75`. |

**D4, retained model failure:** raw FAIL inferred taxonomy from the accepted exclusion
despite `yoga_is_gym=null`. The independent guard correctly retained UNKNOWN and
no financial effect. The revised dataset prompt distinguishes contractual inclusion
from taxonomic membership and requires the actual registered value for the latter.
It supplies policy, not a case-specific expected label.

**D5, retained false-negative gate:** raw PASS correctly understood a scope-first
exclusion, with resolving category/authority evidence. The old whole-clause grammar
did not recognize the wording, so effective UNKNOWN remained. The fix accepts a
bounded family of positive/negative scope-first assertions and still requires
matching frozen facts and complete citation support. Compound promises, extra
qualifiers and contradictory candidates remain unvalidated; financial gates did
not change.

**Cohort confirmation incident:** two no-network tests reproduced `yes` remaining
in clarification after a supported-cohort offer. New `:cohort_offer:` question IDs
bind the exact server-rendered cohort and persisted question history. The public
question field remains `cohort`, so no API schema change is needed. Bare affirmative
answers apply only to that offer; arbitrary legacy questions, conditional answers
and declines cannot silently change age/geography. The original prompt and deadline
remain unchanged. Six regressions cover these boundaries, then C1/C2 exercise them
with real Claude calls. Source files were frozen during each full regression run.

## Actual outcomes, tokens, latency and estimated cost

Tokens are input/output; output already includes thinking. Latency is the sum of
instrumented guarded-call/assessment elapsed time per case, not browser latency.
Raw/effective dispute columns are intentionally separate. PASS supports the complaint;
it is not provider-output fault or permission to move money.

| Case and purpose | Outcome | Calls | Input/output tokens | Seconds | Cost |
| --- | --- | ---: | ---: | ---: | ---: |
| I1 Exact reported conversation, then consent | ready | 3 | 5211 / 1364 | 19.703 | $0.048124 |
| I2 Gym-only request; broader product declined | human_review, no terms | 2 | 3342 / 540 | 8.750 | $0.024168 |
| I3 Explicit question-bound age correction | ready | 2 | 3308 / 700 | 10.938 | $0.027232 |
| I4 Explicit yoga exclusion | ready, yoga excluded | 1 | 1569 / 285 | 4.453 | $0.011976 |
| I5 Weight-room/not-software paraphrase, then consent | ready | 2 | 3322 / 714 | 10.609 | $0.027568 |
| I6 Contradictory yoga instructions, then correction | ready, yoga excluded | 2 | 3286 / 918 | 12.077 | $0.031504 |
| D1 Accepted yoga expansion | PASS / PASS | 1 | 5782 / 1461 | 15.406 | $0.052348 |
| D2 Alleged omitted ZIP, present in actual CSV | FAIL / FAIL | 1 | 5582 / 544 | 7.031 | $0.033208 |
| D3 Undefined investor-ready promise | UNKNOWN / UNKNOWN | 1 | 5774 / 765 | 7.938 | $0.038396 |
| D4 Null taxonomy, retained failure | **FAIL / UNKNOWN** | 1 | 5776 / 1097 | 11.640 | $0.045044 |
| D5 Scope-first paraphrase, retained failure | **PASS / UNKNOWN** | 1 | 5782 / 868 | 9.156 | $0.040488 |
| F1 Fresh null-taxonomy paraphrase after fix | UNKNOWN / UNKNOWN | 1 | 5973 / 708 | 7.688 | $0.038052 |
| F2 Fresh negative scope-first form | PASS / PASS | 1 | 5969 / 889 | 9.109 | $0.041656 |
| F3 Positive scope-first form, expanded contract | PASS / PASS | 1 | 5979 / 915 | 9.375 | $0.042216 |
| F4 Known-false taxonomy, negative control | FAIL / FAIL | 1 | 5956 / 549 | 7.282 | $0.034804 |
| F5 Undefined wellness-ready promise | UNKNOWN / UNKNOWN | 1 | 5966 / 863 | 9.219 | $0.041124 |
| C1 Bare yes to exact supported-cohort offer | ready | 2 | 3272 / 836 | 11.766 | $0.029808 |
| C2 Declined SF offer; no silent geography change | human_review, no terms | 2 | 3307 / 1170 | 15.687 | $0.036628 |
| C3 Fresh fitness/gym/consent conversation | ready | 3 | 5267 / 1330 | 16.984 | $0.047668 |
| C4 Exclusion after cohort-confirmation fix | ready, yoga excluded | 1 | 1569 / 269 | 4.016 | $0.011656 |

Total: **30 real calls, 91,992 input tokens, 16,785 output tokens including 4,494
thinking tokens; $0.703668 estimated new cost**. No cache reads/writes were charged.
Rates are the existing guard's registered standard/global $4/million input and
$20/million output estimates, reconciled to reported usage—not an invoice claim.
Individual measured latency: **3.890–15.406 seconds**, median **6.703 seconds**.

Cumulative ledger after qualification: **$1.756968 known cost**, **$2.129304
conservative committed cost**, **59 historical requests**, **0 active reservations**.
The $0.372336 difference retains earlier uncertain usage. Count is telemetry only.
Neither old reservations nor the original $45 ceiling were reset.

## Model versus deterministic behavior

Claude actually authored the first fitness clarifications in I1/C3 and interpreted
the meaningful `gym membership` and nonliteral weight-room answers. It did not
generate or authorize the final contract. Exact broader-product consent offers and
cohort-confirmation offers are rendered by deterministic code, then bound to the
actual buyer reply. I3's model-authored cohort wording is historical pilot evidence;
the final cohort-offer path deliberately uses an exact server-rendered offer.

All intake traces retained original prompts/deadlines, at most two questions,
no identical repeated question and no paid call on exact compile replay. Ready
drafts had no quote acceptance, funding or payment. All ten dispute orders retained
their accepted snapshots and deadlines, exact source references, zero settlement
bookings and zero free corrections; funding was explicitly simulated/mock only.
D4's UNKNOWN is a rules guard, not falsely labeled model-decided. F1/F5 are genuine
model abstentions with validated provenance. Supported source meaning stays grey
unless provider-output fault is independently established.

## Regression and integration status

108 focused intake/semantic tests pass, including preserved R3/R4, new proof guards
and cohort-confirmation cases. The full `1b7ed75` backend run had **794 pass / 11
pre-existing Windows failures** (805 tests). Final `b9476d9` full run:
**799 passed / 12 failed / 0 skipped / 0 errors**, 811 tests in 329.416 seconds
(`full-final-confirmation.xml`). All 108 focused cases also pass in that full run:
48 primary semantic, 19 unchanged R3/R4, 34 conversational intake, 6 cohort
confirmation and 1 harness boundary test.

The 12 failures are the same eleven Windows portability issues documented in the
integration handoff plus the previously reported
`test_http_automatic_repair_and_settlement_with_restart[unresolved-base_sepolia]`
observation race: the test sees persisted `submitted` before the fake broadcast
list is populated. The `repaired-base_sepolia` variant passed this time. There are
no new failure names versus the original 13-failure baseline, and no payment code
or tests were changed, skipped or weakened. This is not an entirely green suite.
Ruff lint/format pass across 177 files including the unchanged acceptance tool.
All original XML and incident evidence remains under
`backend/artifacts/aggregate-qualification-20261024/`; a portable
[test summary](docs/evidence/aggregate-qualification-tests-20261024.json) includes
the raw XML digests and exact failures.

Generated-contract checks pass. No DTO or frontend source changed in this follow-up;
the previous 109 frontend tests/typecheck/build remain evidence for that unchanged
frontend. Lucas's `/` broker canvas and `/live` aggregate intake are preserved.
Nikita's payments and `tools/brokerage_acceptance.py` are untouched. This one-off
qualification reuses the existing dispute harness and citation auditor; it does not
duplicate the proposed general aggregate evaluation runner/Rehan expectation lane.

## Handoff and remaining limits

- Defaults remain OFF: `ENABLE_PAID_MODELS`, `ENABLE_DATASET_MODEL_ASSESSMENT`,
  `ENABLE_BROKER_DISPUTE_ASSESSMENT`. These results do not silently enable shared main
  or production. The new paid window expires automatically at 14:22 Pacific.
- Evidence uses the primary `/runs` HTTP/service paths through isolated ASGI clients,
  real Anthropic traffic and synthetic datasets. This is not a browser deployment
  demonstration or real customer-payment validation.
- Supported products and proof grammar remain bounded. Unknown obligations and
  unsupported composite claims must remain unresolved; no broad natural-language
  reliability percentage is inferred from these cases.
- No new self-improving procedure was proposed/approved/activated by this task.
- Original integration/schema handoff: [AGGREGATE_INTEGRATION.md](AGGREGATE_INTEGRATION.md).
  The latest evidence bundle includes actual intake messages and primary verdict
  events, with raw candidates, effective findings, bindings and resolving citations.
- Do not rerun the frozen cohorts: the runner refuses existing evidence directories.
  Any future technical/quality recovery must preserve these results and the same
  ledger, obey its remaining authorization, and use separately declared new cases.
