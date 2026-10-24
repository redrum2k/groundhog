# Independent expected outcomes — evaluator only

Owner: Rehan. No independently reviewed gold labels are supplied yet. Engineering fixture tests
are not independent outcome validation. Rehan's first deliverable is labeled clean, defective,
repaired, substantively amended and unresolved catalog cases.

Keep this directory unavailable to runtime workspaces, tools, prompts, frontend assets and
production packages. Only the offline evaluator may compare runtime outcomes with these labels.
Measure false passes, missed contradictions, useful abstention and failure analysis. Optional
semantic-provider comparisons also need latency and cost. No confidence cutoff is adopted.

## Dispute labels

`disputes/holdout_labels.json` seals the 109-case aggregate dispute holdout (hash in
`../cases/disputes/holdout/MANIFEST.json`); `holdout_usage.json` logs every scored opening.
`disputes/hf_review_worksheet.csv` is the 48-thread Hugging Face subset for an independent
reviewer; reviewed rows go in `disputes/hf_review_labels.csv`. See `../disputes/README.md`.
