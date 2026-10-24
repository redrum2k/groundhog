# Bounded prospective improvement

The application, not the coding session, runs this loop:

1. Persist a material uncertainty incident and later observed outcome.
2. Generate at most two typed patches from scoped incidents and tested experience.
3. Run baseline, memory-only control and candidate through actual application commands
   in separate temporary stores with simulated parties/providers/payment authority.
4. Retain a tested candidate or retain the baseline. Preserve negative results.
5. Require a controller's approval, then a separate prospective activation.
6. New drafts pin the version; customer/provider acceptance still freezes each order.
7. Revoke to the preceding version. Existing accepted orders never change.

The implemented edit surface is deliberately small: require a named intake field,
replace its clarification question, or bind an already implemented validator to its
exact confirmed parameters. Source bytes are retained by the fixed application.
New evidence-acquisition tools, new validator algorithms and arbitrary generated code
are outside this editable surface. Unsupported operations are rejected, not installed.

Accepted contracts, prices, roles, fees, payment guards, source truth, evaluator truth,
credentials and deployment are never editable. There is no eval/exec/generated SQL,
general filesystem tool or model payment tool. A one-case concession is not a template.

## Existing implementation reused

The broker adapter reuses the compatibility OrderService in `orders/invoice_compat.py`,
jobflow identities and SQLite transactions, immutable
artifacts/events/receipts, bounded document extraction, the existing Anthropic SDK and
its durable global call allocation. New tables contain profile/improvement records,
not another financial ledger. Lucas's UI is not redesigned; generated types, a typed
client and event fixtures are the integration seam.

Current main's catalog remains the default product. Its compiler, 60-second review,
payment journal and frozen root OpenAPI are unchanged. This improvement mechanism is
scoped to the separate regional-data broker profile; catalog intake is not silently
subscribed to its templates. All profiles use the same app/DB with separate schemas
and accepted financial policies.

## Harness2 source audit

Reference: Google Research `harness2` at
[`1cfe254e8d25b15f37048c3730134686abe60335`](https://github.com/google-research/harness2/tree/1cfe254e8d25b15f37048c3730134686abe60335).
This is a Harness2-inspired adapter, not the upstream executor or benchmark suite.
No upstream source was copied. The inspected project declares Apache-2.0 and no
mandatory Python dependencies, but its package is oriented to POSIX execution.
Its optional bridge dependencies are not needed here.
[Package definition](https://github.com/google-research/harness2/blob/1cfe254e8d25b15f37048c3730134686abe60335/pyproject.toml).

| Inspected seam | Adopted method | Local implementation |
| --- | --- | --- |
| `core/spec.py` | Keep domain inputs/adapter separate from method | `ScenarioAdapter`, neutral visible cases, separate offline reference endpoints |
| `core/recursion.py` | Bounded contrasts, preserve failure/base fallback | Two proposals; isolated probes; retain candidate/base; no untested composition |
| `core/library.py` | Experience needs evidence and applicability | Immutable tested questions, contrasts, rejection reasons and probe IDs, scoped by customer/product |
| `core/context.py`, `core/prompts.py` | Evidence is data; no grader context | Typed incident/experience envelope; protected loader; no arbitrary context-directory access |

Sources: [spec](https://github.com/google-research/harness2/blob/1cfe254e8d25b15f37048c3730134686abe60335/harness2/core/spec.py),
[recursion](https://github.com/google-research/harness2/blob/1cfe254e8d25b15f37048c3730134686abe60335/harness2/core/recursion.py),
[library](https://github.com/google-research/harness2/blob/1cfe254e8d25b15f37048c3730134686abe60335/harness2/core/library.py),
[context](https://github.com/google-research/harness2/blob/1cfe254e8d25b15f37048c3730134686abe60335/harness2/core/context.py),
[prompts](https://github.com/google-research/harness2/blob/1cfe254e8d25b15f37048c3730134686abe60335/harness2/core/prompts.py).
The paper describes task-level adaptation and reuse of improvement experience;
its benchmark gains are not results of this application.
[Harness2 paper](https://arxiv.org/abs/2610.14224).

The dependency spike ended with a local typed adapter: importing filesystem harness
mutation and external executor/credential defaults would add authority and integration
cost without solving a missing domain capability. No full framework install occurred.

## Runtime and evidence controls

- `im_records` is immutable; `im_state`, `im_active` and durable job status are separate.
- Approval/activation bind candidate, probe, baseline and the backend/lockfile hash.
- A completed negative probe cannot be rerun to erase its evidence.
- Maximum two proposal cycles before checkpoint; no automatic retry after uncertain
  external work. The shared durable dollar ledger includes all earlier V6 spend and
  uncertain reservations, with no aggregate request-count ceiling and at most two
  concurrent application calls. Separately authorized windows retain their old cutoffs.
- The real proposer uses the existing configured Anthropic adapter. Missing approved
  access produces BLOCKED with zero model calls. Injected transports are labeled
  ANTHROPIC_TEST_DOUBLE; fixture proposals are DETERMINISTIC_INFRASTRUCTURE.
- Later deterministic proposals select wording from actual successful question traces
  while avoiding recorded rejected wording. This tests experience reuse, not model
  weight training or a measured second-cycle effectiveness gain.

## Evaluation boundary

The application receives neutral IDs, ordinary contracts/source bytes, the actual
answer to the actual question, and allowed timeline facts. `evals/expected` is loaded
only by the offline runner after candidate selection; the backend Docker image copies
only `app`, never evaluation files. No product/model tool can read the repository.

Historical fixed contracts test preservation of UNKNOWN. Future-intake comparisons
use matched customer intent and answers; they measure a process/information change,
not same-input reasoning accuracy. Memory-only is a deterministic control with no
template authority; a live-model memory comparison is not qualified here.

Every incoming case remains in the denominator, including declined, blocked,
unsupported, timed-out and reviewed work. Candidate promotion fails on authority,
financial, endpoint, completion or answer-fidelity regressions. Company intervention
events, customer answers and rework are separate; active human seconds and dollar
savings are not inferred from automated test duration. See EVALUATION_RESULTS.md.
