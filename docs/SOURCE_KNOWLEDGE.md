# Sandbox institutional source knowledge

Draft review only. Do not merge or enable in production until integration testing
and a team decision about presentation and deployment.

This feature preserves the first **simulated** operational-learning cycle that
reduced repeated internal intervention. It has no production endpoint, live
activation, real source-owner authentication, or payment implementation changes.
The full repository test suite has not been rerun.

## Mechanism

An ambiguous provider export triggers an internal review. An explicitly simulated,
authorized source-owner resolution establishes which column counts unique adults
for a specific source-family schema edition. The system derives an immutable
procedure from that evidence. A later order reuses it against fresh batch bytes
only while publisher, schema version/hash, edition, scope, unit and current authority
still match. Order-only resolutions cannot become cross-order procedures.

The candidate and stateless baseline execute the same code and receive identical
current-case information and tools. Only the candidate retains the prior resolution.
A current-definition control confirms that the baseline resolves the mapping without
review when current authoritative documentation already supplies it.

Changing the authorized resolution changes future behavior; renaming columns and
reversing their apparent meaning does not hardcode a successful answer. New batch
values are read afresh, not copied from previous results. Current conflicting,
revoked, expired or changed authority blocks inappropriate reuse.

## Sanitized evidence summary

Historical local execution of source commit `8e2ddd74ce7c197b517af4618eff820574b3948d`:

| Future-case metric | Stateless | Retained experience |
| --- | ---: | ---: |
| Correct outcomes, including required holds | 9/9 | 9/9 |
| Internal reviews | 8 | 6 |
| Logical tool operations | 59 | 65 |
| Verified citations | 4 | 13 |
| Mandatory customer consent preserved | Yes | Yes |
| Forbidden commercial-action attempts | 0 | 0 |

Two repeated reviews were avoided. One initial simulated source-owner review acquired
the knowledge; that cost is separate. Reuse required six extra tool operations.
Human minutes, real customer labor savings and production benefit were not measured.
These are engineered functional cases, not independent real-world evaluation data.

Two distinct sandbox orders completed normal explicit customer acceptance, explicit
mock funding and verified CSV delivery. No capture occurred. Source/evidence pins,
suppression and accepted snapshots were preserved. All 18 paired predictions were
re-audited against saved bytes, and the earlier negative-run files remained unchanged.

Historical evidence identifiers (raw artifacts remain local and are not in this PR):

- Run capsule SHA256: `859e4eab514bada8bf3c7e8e991dd0dcde89722cab30082c83e3cb571bb3e7a1`.
- Trace SHA256: `f98b2bc9e05ce6382140344d2d261e02d72b9c9ede899f8259d3101be18719d9`.
- Original verification: 28 focused tests and Ruff check/format passed.

Review packaging was also verified against main `3445e19`: all 28 focused tests,
Ruff check/format, and the portable standalone comparison passed. The comparison
reproduced 8 -> 6 internal reviews and 9/9 correct cases for each arm (capsule
`423978b61b2ab4ebc34c0d56b9c7dddb2d2ef52c202636fdcd11eacdf85eab37`).
Its optional historical-file audit was not requested and is reported as such;
the frozen original audit result above is not replaced. These focused checks do
not substitute for the full repository suite or team integration review.

The earlier CoSQL/DIR experiment remains unqualified. Its eight reviews were two
requests for absent income data and six refusal/interpretation/interface gaps; none
established an exception avoidable by remembered source-owner authority. No earlier
experimental code, datasets, labels, database, or generated delivery is included here.

## Review scope and safety

- `backend/app/agents/source_knowledge.py`: typed authority checks, immutable
  experience records, procedure derivation and guarded reuse.
- `backend/app/agents/source_preparation.py`: sandbox source preparation into the
  ordinary compiler/quote flow. Acceptance and funding remain separate.
- `evals/source_learning/`: explicitly simulated fixtures, comparison and 28 tests.

Both engine and memory constructors require sandbox opt-in. Production active-version
pointers remain empty. Source reasoning is checked against commercial-action tripwires
and protected-state comparisons. No startup hook, route, UI, shared payment module,
existing runtime module, or global policy is changed.

The review branch is rebuilt from main `3445e19` with only the source-learning change.
The original experiment history and frozen outputs are preserved locally, not pushed.
The two runtime modules and scenario/test definitions are unchanged from the source
commit. The runner packaging removes a machine-specific path: the prior negative
audit is optional and explicitly reports when its private inputs were not supplied.
This does not change the learning logic or comparison scenarios.

## Local verification

From the repository root:

```sh
uv sync --locked --project backend
uv run --locked --directory backend pytest ../evals/source_learning/test_source_knowledge.py
uv run --locked --directory backend ruff check app/agents/source_knowledge.py app/agents/source_preparation.py ../evals/source_learning
uv run --locked --directory backend ruff format --check app/agents/source_knowledge.py app/agents/source_preparation.py ../evals/source_learning
uv run --locked --directory backend python ../evals/source_learning/run.py --output ../evals/source_learning/build/reproduction-new
```

Use a new output directory; generated evidence and SQLite databases stay ignored.
No corpus download, paid model or network call is needed. If preserved negative
artifacts are available locally, supply `--prior-negative-dir PATH` pointing to the
parent of `comparison-001` and `comparison-002`; otherwise that audit is explicitly
not run. The original negative artifacts are never training inputs.

## Before any merge or activation

- Run the full repository suite and resolve integration failures against current main.
- Review the source-family authority boundary, stale/conflicting evidence behavior
  and simulated authorization assumptions.
- Agree with the team how to present the result without implying real-world labor
  savings or production readiness.
- Keep this PR draft and production activation disabled until those decisions pass.

This PR is for preservation and review, not permission to merge, deploy or expose a
live learning endpoint.
