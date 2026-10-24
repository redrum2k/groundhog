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

Validation details, exact base/reused SHAs, commands and evidence paths are in
[workstream 10](../workstreams/10-aggregate-evaluation.md). Final verification results
are recorded there before handoff. This draft is local; no publication or merge.
