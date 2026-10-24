# Evaluation boundary — Rehan, with Lucas's visual review

Follow root AGENTS.md. Rehan owns independently reviewed expected answers and acceptance
checks. Lucas classifies the generated PDFs visually; reconcile disagreements offline.

Runtime-safe inputs belong in cases. Gold verdicts, grading labels and mutation metadata
belong in expected or private evaluator storage, never prompts or runtime mounts. Only
an offline evaluator may compare returned verdicts with expected answers. Do not give
an investigator repository-wide filesystem access. Follow docs/INTEGRATION_CHECKPOINT.md.
