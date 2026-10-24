# Flowchart to executable application

The separate broker profile supplies aggregate regional market intelligence as actual
JSON or CSV plus a source/methodology PDF. Catalog remains the default product on
current main, and the invoice compatibility profile remains operational. This mapping
describes broker commands, not a replacement for catalog's compiler or payment journal.
The V5 packet and both reference images were read; this mapping includes the
NO_REMEDY and human-resume branches that were implicit in the sketch.

| Flow | Application implementation | Persisted evidence |
| --- | --- | --- |
| Describe / clarify | `Broker.create_draft`, `draft_command` | Original intent, actual questions/answers, unresolved fields, template version |
| Provider can supply? | Explicit provider offer / capability result | Offered price, supported/unsupported reason; no authorization yet |
| Both parties accept | Exact acceptance digest, then existing `OrderService.create` | Immutable spec, source hashes, parties, price, v0.3 policy and mock authorization |
| Produce / check | `build_package`, independent byte reopening | Structured data, actual PDF, sidecar, source-linked PASS/FAIL/UNKNOWN checks |
| PASS | Customer review | `verification.completed`, `review.opened`; no early capture |
| Accepted / undisputed cutoff | Existing capture guard | Exactly one accepted-price booking if all current gates pass |
| Operational failure | Red, provider-owned or controller-owned after exhaustion | No invented delivery version; original failure and attempt outcome retained |
| Defect | Orange, one included correction | New bytes/version, new verification and review; second failure hands off |
| Unknown / disputed | Targeted issue-bound question, at most two rounds | Source references, testimony, exact resume, unchanged deadline |
| Still unresolved | Persistent controller task | Current binding, current evidence, missing facts and executable RESUME/RETAIN_HOLD decision |
| Refuted | NO_REMEDY | Evidence-backed resolution without a processing fee |
| Additional scope | New linked draft and separately accepted offer | Its own authorization/ledger; decline leaves the original order intact |

The typed requirements cover date basis/age/as-of, geography and boundary revision,
reference period, metric meaning/unit, entity unit, expected coverage and missingness,
exact source revisions/conflicts, and output schema. Unknown terms are not guessed.
Customer testimony is not source authentication or an accepted amendment.

Human RESUME revalidates actual current artifacts. It cannot assert PASS, renew
authority, waive a failed check, alter price, or reset an unanswered dispute clock.
An overdue case that resolves without replacement requires explicit customer
acceptance; a permitted corrected delivery gets a new review. Exhausted authority,
case time and uncertain payment operations remain explicitly owned handoffs.

The legacy investigator now delivers a validated model-authored question when it
fits the supported missing predicate. It records recipient, agreement/evidence
bindings and origin. Unsafe/unusable wording is explicitly FALLBACK. Answer replay
does not enqueue a second run, create another artifact, extend review or pay again.
