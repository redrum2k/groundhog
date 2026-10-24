# Reviewed catalog cases — Rehan

Runtime-safe scenario inputs only. The offline harness supplies a 48-product synthetic catalog
and repaired/unresolved journeys; these are engineering fixtures, not independently reviewed
gold answers. First independently label clean, defective, repaired, substantively amended and
unresolved cases from actual PDFs. Include net/shipping ambiguity, exact thresholds, missing
values, authority/date conflicts, irrelevant uncertainty, corrections and consent/expiry cases.

Keep expected outcomes, mutation labels and grading metadata in ../expected or private evaluator
storage. No evaluation field is accepted by runtime contracts. Runtime agents receive only
approved artifact IDs and bounded resolved passages, never repository-wide file access.

## Dispute holdout and stress inputs

`disputes/holdout/` holds 109 runtime-safe aggregate dispute cases (views plus actual CSV,
preview and source bytes, neutral IDs). `disputes/hf_views.jsonl` holds the 156 real Hugging
Face complaints as decision views. Labels live in `../expected/disputes`. See
`../disputes/README.md`.
