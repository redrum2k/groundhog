# Add isolated aggregate evaluation and auditable comparative reports

Aggregate evaluation previously had only a small acceptance smoke and one-off
semantic diagnostics. This adds a noninteractive offline runner with strict frozen
case/expectation inputs, one bounded process and database per case, requirement-level
scoring, independently audited CSV/JSON citations, and JSON/Markdown reports.
Initial rejected output and findings survive correction; missing results remain in
scheduled totals. Explicit fixture compilation leaves intake quality unscored.

The pure cell auditor is attributed to Jeff's `ef8c99a` published blob and extended
with tested null/absence/version handling. Its private ledger paths, model rates and
entry point are excluded. No runtime branch is merged; compiler, gateway, financial
gates, public contracts and frontend remain unchanged. The existing acceptance smoke
and legacy v5 evaluator are preserved. Ownership documentation records the agreed
Nikita tooling/Rehan independent labels/Jeff semantics split.

Six engineering fixtures cover conforming capture, detected defect/correction,
unsupported complaint, separately accepted additional scope, insufficient evidence
and contradictory evidence. All six complete; two intentionally reported development
mismatches expose source-stage `R-ARTIFACT=PASS` without output bytes. Funds remain
held and evidence is requested. Rehan-reviewed gold, held-out qualification, raw model
quality and provider cost remain unavailable. No accuracy or live payment claim.

Validation on implementation `ee8fd85`: **40 evaluator tests**, **233 combined
evaluator/dataset/API/broker tests**, and **760 full backend tests** pass. Both
regression runs retain the two unchanged strict R3/R4 expected failures. Ruff
lint/format (179 files), the unchanged brokerage acceptance smoke, Node 24 generated
contract freshness and `git diff --check` pass. The initial sandbox-denied localhost
test setup and uv-cache attempts are recorded separately; approved retries pass.

Exact base/reused SHAs, commands and evidence paths are in
[workstream 10](../workstreams/10-aggregate-evaluation.md). The clean-tree six-case
report is `/private/tmp/aggregate-evaluation-ee8fd85/aggregate-s7498cdm/report.md`,
with adjacent schema-versioned `results.json` and retained private evidence. Default
exit 1 preserves the two disclosed engineering mismatches; selected conforming/
corrected cases exit 0. No independent gold or qualification success is claimed.
This draft is local; no publication or merge.
