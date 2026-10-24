# Bounded broker dispute follow-up — NOT qualified, feature OFF

Authorized start: **2026-10-24 10:25:38 Pacific**. Absolute cutoff: **12:25:38**.
Original V6 window 02:10–10:10, delivery `0b1127f` and frozen experiment `f388fe3`
were not reset or merged. Base for this separate feature branch: `c2f5619`.

The backend now makes a real, source-bound Claude assessment through the broker
investigation path, with immutable attempts, independently validated exact JSON cells,
server provenance and conservative effective decisions. It is **disabled by default**.
The full acceptance suite did not pass. Do not deploy or enable it in the live demo.

## Actual calls and failed attempts

Authenticated organization model lookup and one small smoke call succeeded using
`claude-opus-5-5`. Smoke: 223 input, 9 output, 0 thinking/cache tokens; lookup plus
request elapsed 2.625 s; estimated token cost **$0.001072**.

The first frozen cohort had four eligible semantic attempts, all rejected locally
before transport because their duplicated context exceeded 50,000 characters.
Those failures, original databases and rules fallbacks remain in the evidence.
No semantic API call occurred in that cohort. A runner exception-class error was
technically recovered without recreating its already blocked order. See
DISPUTE_TECHNICAL_RECOVERY.md; these are not successful first-attempt model results.

After lossless context deduplication, a separately declared fresh-order technical
cohort made four real calls, without retrying any failed model answer:

| Case | Raw model | Effective | Input / output (thinking included) | Latency | Estimated cost |
| --- | --- | --- | --- | --- | --- |
| N1 explicit age complaint | not_justified | not_justified, model | 17471 / 1123 (318) | 14.000 s | $0.092344 |
| N2 age paraphrase + irrelevant font remark | not_justified | unclear, unresolved | 17590 / 1317 (284) | 15.844 s | $0.096700 |
| U1 unaccepted visual-quality promise | not_justified **WRONG** | unclear, unresolved | 17705 / 1300 (548) | 15.485 s | $0.096820 |
| U2 undefined executive-ready promise | unclear | unclear, unresolved | 17576 / 1176 (264) | 13.484 s | $0.093824 |

All four actual responses reported `claude-opus-5-5`, end_turn, standard/global
service; no cache tokens. Total semantic use: 70,342 input, 4,916 output including
1,414 thinking; **$0.379688** estimated. Thinking was not double-counted.
Pricing reference: https://platform.claude.com/docs/en/about-claude/pricing
(Opus 5.5 $4/M input, $20/M output, verified 2026-10-24).

N1's accepted observation age was 21 days; actual age was 9.25 days. The independent
reviewer resolved and hash-checked all **16 live citations** against stored bytes.
U1 demonstrates why real citations do not prove reasoning: the model wrongly treated
absence of an accepted visual standard as contradictory evidence. The gate held it.
N2 demonstrates the cost of the deliberately narrow independent complaint recognizer:
correct model interpretation remains advisory when its support cannot be established.

Raw labels were 3/4 correct; effective labels were also 3/4, with different failures.
Rules-only baseline was 2/4. These small diagnostic counts do **not** establish an
attributable model accuracy gain. No economic-savings or general arbitration claim.

J1/J2 are **BLOCKED in both arms**: deterministic production already detects their
corrupt JSON and reserves correction before a public dispute is eligible. No bypass
was introduced to manufacture an assessment/remedy success. Include these two cases
in the six-case denominator. The inherited fixture's initial intent says Bay Metro,
while explicit later clarifications/accepted typed terms specify Harbor District;
that inconsistency was preserved and disclosed, not silently repaired after evaluation.

## Shared resource accounting

V6 began this follow-up with 17 reservations, $0.399756 known estimated use and
$0.772092 conservatively committed. Follow-up added five actual requests costing
**$0.380760**. Shared final snapshot: **22 reservations**, **$0.780516 known estimated
cost**, **$1.152852 conservatively committed**, **0 active**, **$45 maximum**.
Unknown prior costs remain reserved; these estimates are not an invoice or credit balance.
The $10 final-evaluation holdback remains; old allocation records are retained in history.

No aggregate request ceiling exists. Per-case/correction/question bounds remain.
Every real SDK dispatch uses the shared SQLite reservation ledger; concurrency <=2,
timeouts/output bounds/no SDK retries, rate-limit cooldown and repeated-failure guards
remain. New explicit window `broker-dispute-followup-20261024` was registered with
the authorization artifact hash; the original budget_policy cutoff remains 10:10.
No top-up, billing change, purchase, real payment, deployment or main merge occurred.

## Acceptance and verification

Early integrated checkpoint completed at 10:59 Pacific, before the hour-one checkpoint
and well before the two-hour cutoff. Final hardened backend: **452 tests passed**, no
failures/errors/skips; Ruff check and format check passed. This ends the bounded
follow-up early with the feature OFF; no background experimentation remains running.

Independent reviewer final recommendation:

| Condition | Outcome |
| --- | --- |
| 1 supported justified public flow | BLOCKED |
| 2 evidence-supported not justified | PASS |
| 3 unclear | PASS effective outcome; U1 raw model failed |
| 4 semantic variants | FAIL |
| 5 reference integrity | PASS within tested JSON-cell scope |
| 6 lifecycle/concurrency | PASS within tested scope |
| 7 provider failure handling | PASS within tested simulated-failure scope |
| 8 browser integration | FAIL / visual verification blocked |

Expanded lifecycle tests cover duplicate commands, restart/uncertain attempts,
same-information deduplication, actual source upload and mutually accepted version
amendment in flight, controller reassessment after new accepted source evidence,
unchanged clocks, and explicit failure provenance for timeout/refusal/budget/cutoff.
An attempted test amendment changing an already accepted age limit was correctly
rejected by the existing separate-quote gate; tests use permitted amendments instead.
No contractual gate was weakened. Unit mocks are not provider-performance evidence.

Frontend generated types, typecheck, production build and **61 tests** passed.
Only `frontend/lib/broker.generated.ts` changed; Lucas's components/adapters are intact.
Real local Next→broker HTTP round trip created a fresh accepted mock order, completed
one booking, and three repeated event GETs left order/event/model counts unchanged.
`/` and `/jobflow` returned 200; `/catalog` returned 404. No browser provider was
available, so there is **no visual-browser qualification claim**. Owned test servers
were stopped; ports 3108/8108 were verified released.

Actual model cohort backend/lock hash:
`4ea9a8032e219ba50041074c6cfb2e5983abe390f3698633b5d7941c83404571`.
Subsequent content-deduplication hardening hash:
`9d56ccad37dc731117eb513facccaa303cc9d23d2b08dc6dae2b6c2d43b26327`.
No fresh paid evaluation was performed after that hardening. Final test XML and
source commit receipt are included in the export; do not confuse these revisions.

## Integration blockers / limitations

The current frontend adapter treats `verification.completed=PASS` as a final
"disagree" and does not consume `dispute.assessed`. It can misrepresent an unresolved
complaint if this feature is enabled. The scripted driver also reads the immutable
acquisition command receipt instead of refetching the later assessment. These are
explicit frontend-owner handoff items, not fixed by generated types.

The independent recognizer only supports narrowly structured numeric/date complaints;
it is not general natural-language entailment. PDF/CSV exact-cell selection is not
implemented here. Uncertain in-flight process loss is held/deduplicated, not retried;
existing controller/case-deadline ownership remains. Existing broker GET may advance
legacy timers: the limited no-new-work HTTP observation is not a claim all GETs are
globally mutation-free. No source click/visual mapping acceptance is claimed.
