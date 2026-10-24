# Frozen fresh follow-up suite

Defined by the independent reviewer before inspecting candidate implementation.
Do not change labels or reroll failed actual calls. V6's 48/48 is not evidence here.
Run each public command sequence in a new isolated DB. Keep expected outcomes out
of runtime/model inputs. Preserve both rules-only and candidate results and raw attempts.

Common accepted source: harbor-statistics v1; Harbor District; boundary 2026-H2;
period 2026-Q3; median_household_income, USD_per_household, entity unit region.
One row: harbor-017 / H017 / value 84250 / observed 2026-10-15T00:00:00Z.
Published Oct20, exported Oct24. Accepted observation age <=21 days as of
2026-10-24T06:00:00Z. Exact versions; coverage harbor-017; no missing rows;
market-v1 JSON. Normal artifact generation is unchanged.

| Case | Complaint / independent expected outcome |
| --- | --- |
| J1 | Delivered JSON value mutated to 48250, other artifacts 84250. "The delivered JSON reports 48,250 for Harbor even though the accepted source reports 84,250." Justified; reserve eligible correction once, no capture. |
| J2 | Same independent corruption. "Your downloadable household-income figure has the digits transposed. Please reconcile it with the agreed source. I like the blue cover and our finance team meets on Tuesdays." Justified. |
| N1 | Pristine. "The observation is older than the twenty-one-day limit we agreed." Not justified; exact dates contradict complaint, NO_REMEDY, no fee/capture. |
| N2 | Pristine. "You sent stale observations: the measurement is outside our agreed age window. Our director strongly dislikes the report font." Not justified. |
| U1 | Pristine. "The chart does not satisfy the premium visual quality we agreed verbally." Unclear: absent accepted meaning is not refutation. |
| U2 | Pristine. "This presentation is not executive-ready as promised in our conversation. Your source revision and household-income number look accurate." Unclear. |

Eligibility is part of the result: J1/J2 may be BLOCKED because deterministic
production checks reserve correction before the dispute gate. Do not bypass that
gate, rewrite labels, or count them as model successes. Language paraphrases outside
an independently verified complaint predicate remain advisory even when model-correct.

Resource plan: four eligible semantic calls, no automatic retries; 4096 output tokens
each, conservative guard reservation before every call. Keep the shared $10 final
reserve (well above forecast under $4 for this suite) and cumulative $45 ceiling.
The $0.001072 connectivity pilot is separate, not a semantic trial. Thinking retains
the model default. Old allocation history and old mission cutoff remain auditable.

Acceptance also requires guard/adversarial/lifecycle tests and browser integration.
Frontend view/adapter implementation is Lucas-owned and untouched. Missing integration
or failed semantic cells requires feature OFF; report partial evidence honestly.
