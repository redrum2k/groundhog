# Primary `/runs` assessment — additive contract

This separate primary-workflow follow-up records a new authorization window from
2026-10-24T11:19:36-07:00 to 2026-10-24T12:25:38-07:00. It retains the previous
absolute cutoff, shared cumulative $45 ledger and feature branch. No V6 restart.
Current integrated main is 62fe035; the legacy implementation at db7aab8 is retained.

Reuse `investigate_dataset`, `SemanticAssessor`, `ClaudeGateway.assess_obligation`
and the existing durable worker, catalog records, bindings and run event stream.
No new decision engine, ledger, payment executor or frontend implementation.

The existing `verdict` event keeps its UI kind (agree/disagree/grey). Add optional
`verdict.finding`: `kind` (supported/contradicted/unclear), `reason`, `evidence_ids`,
`decided_by` (model/rules/unresolved), exact current `binding`, original
`assessed_binding`, accepted-specification hash, raw candidate, effective Assessment,
validation status and durable attempt ID. Candidate output is not applied authority.

`Assessment.PASS` SUPPORTS the complaint; FAIL CONTRADICTS it. UNKNOWN/CONFLICT
remain unresolved. A supported source-meaning claim still maps to grey/human review
until independently established output fault: no correction, capture or refund
authority follows. Existing deterministic provider-defect gates remain unchanged.

Source membership alone is not entailment. Definitive model findings require exact
resolved frozen cells plus a complaint-specific independently checkable predicate.
Other interpretations remain advisory/UNKNOWN. Tests must retain raw/effective
differences and distinguish model from rules fallback.

`ENABLE_DATASET_MODEL_ASSESSMENT` defaults false. Paid transport additionally needs
existing ENABLE_PAID_MODELS, CLAUDE_MODEL and shared budget/window configuration.
One durable dispatch per bound case snapshot; calls occur outside transactions;
recheck job lease, evidence, case and accepted binding at commit. Preserve stale,
failed and uncertain attempts. Polling/replay do not dispatch. No frontend source
or financial executor changes are authorized by this contract.
