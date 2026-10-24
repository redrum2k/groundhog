# Dispute dataset evaluation — Rehan

Evaluator-only. Nothing here is imported by `backend/app`, copied into the Docker image or
shown to a model. It applies the dataset review of `dispute-dataset.zip` (1,500 simulated
Northbeam cases, 156 real Hugging Face threads) to OBJECTION's aggregate-brokerage-v1 workflow.

## What the review asked for, and where it is

| Ask | Where |
| --- | --- |
| Confirm the leakage and baselines | `audit.py` → `reports/audit.json` (reproduces 47.5%, 87.8%, 95.9%, 100%, 13/136, 221/221/20 leaked IDs) |
| Rebuild lessons and contrastive examples from train only | `build_memory.py` → `build/memory/` (git-ignored); 0 development IDs |
| Expose only agreement, verified checks and received messages | `common.sim_view` + `assert_safe_view`; future turns, labels, variants and outcomes never reach an arm |
| Don't import Northbeam remedies the policy forbids | `common.POLICY_MAP`: credits, SLA credits and agent settlements become human review; no arm can move money |
| Real-language stress test with an independent reviewer | `hf_stress.py` → `evals/cases/disputes/hf_views.jsonl` + `evals/expected/disputes/hf_review_worksheet.csv` (48 threads, stratified) |
| New sealed holdout with actual artifacts | `holdout.py` → 109 cases, 20 aggregate mechanisms, `evals/cases/disputes/holdout/` (views, CSV, preview, sources); labels in `evals/expected/disputes/` |
| Static vs functional memory vs evolving procedures on the same cases | `arms.py`, `run_disputes.py` → `reports/RESULTS.md`, `reports/results.json` |
| Treat the 221 test cases as development tests | Scored and labeled as "Development", never as a holdout |

## Run (repository root)

```sh
uv sync --locked --project backend
DATA=<extracted dispute-dataset dir>
uv run --locked --directory backend python ../evals/disputes/audit.py --dataset $DATA
uv run --locked --directory backend python ../evals/disputes/build_memory.py --dataset $DATA
uv run --locked --directory backend python ../evals/disputes/hf_stress.py --dataset $DATA
uv run --locked --directory backend python ../evals/disputes/run_disputes.py --dataset $DATA
DISPUTE_DATASET=$DATA uv run --locked --directory backend pytest ../evals/disputes
```

`holdout.py` needs the backend environment because it drives the real application:
`cd backend && PYTHONPATH=../evals/disputes uv run --locked python ../evals/disputes/holdout.py --seed <new seed>`.
It refuses to overwrite a holdout that has already been scored with the same seed.

## The holdout

One real AcmeFitness order is accepted, mock-funded and delivered by `CatalogService` and
`CatalogWorker`. Each case starts from that order's actual frozen source, coverage, authority
and delivery bytes, applies one designed fault (or none), and records the real
`verify_dataset` output as the checks an arm sees. The mechanisms are aggregate-specific, so
none is one of the 26 simulated templates: missing, duplicate and changed ZIP rows, preview
disagreement, broken schema, suppressed rows reported as missing, buyer retraction,
contradictory buyer testimony, a complaint aimed at the wrong row while a different defect
exists, yoga excluded vs yoga already owed, Oakland scope, unverified authority, coverage
conflict, unknown source status, a second defect after the free correction, a refund demand
on a real defect, a privacy request, and an exhausted question budget.

Labels come from the design, not from the validator. The validator agreed with the design on
all 109 (`holdout_diagnostics.json`). The labels file hash is in `MANIFEST.json`;
`run_disputes.py` writes and hashes every prediction before it opens the labels, and logs
each opening in `holdout_usage.json`.

## Results (first scored run)

| Sealed holdout, 109 cases | static | memory | evolving |
| --- | --- | --- | --- |
| Action accuracy | 98.2% | 34.9% | 56.9% |
| Unsupported actions | 0 | 40 | 0 |
| Correct abstentions | 24/24 | 6/24 | 20/24 |
| Over-abstentions | 5 | 23 | 33 |
| Financial-policy violations | 2 | 0 | 0 |
| Citation recall | 100% | 53.1% | 17.2% |

On the 221 development cases the order flips: memory 86.9%, evolving 67.0%, static 63.4%.
Full metrics: `reports/RESULTS.md`.

What this does and doesn't show:

- **No learning claim is supported yet.** Neither memory nor the evolving procedures beat
  the fixed checklist on unseen mechanisms. Memory's 86.9% on development cases is recognizing
  new wordings of the same 26 templates; on the holdout it drops to 34.9% and makes 40
  corrections or rejections the checks don't support.
- **The evolving arm fails to transfer.** Its procedures are keyed on which checks failed. Real
  aggregate defects fail two checks at once (coverage and artifact), a pattern the simulated
  cases never contain, so it falls back to asking a question. That is a real gap to fix, but
  fixing it now would be tuning on the holdout. Change the arm, then generate a new holdout
  with a new seed.
- **Blind second labeling of the holdout.** A separate reviewer with no access to the design
  labels, generator or arms labeled all 109 cases from the views, the actual bytes and the
  policy (`evals/expected/disputes/holdout_review.csv`; `review.py` → `reports/holdout_review.json`).
  Agreement: primary action 90.8% (kappa 0.88), verdict 96.3% (kappa 0.95), and every case
  shares at least one acceptable action. The only adjudication needed is 4 privacy requests
  (out_of_scope vs undetermined; both say human review). Against the reviewer's labels:
  static 98.2%, evolving 60.6%, memory 36.7%. The reviewer was a model, and HACK.md/AGENTS.md
  say a second model agreeing is not independent truth, so a human pass is still the bar for
  external claims. The static checklist's two real errors: "yoga add-on" matched its scope
  rule, offering to bill for yoga the buyer already owns.
- **Simulated outcomes are not evidence.** Acceptance and CSAT in the bundle are random draws,
  so they are never used as a success signal.
- **Hugging Face stress set (48 reviewed threads).** Labeled blind to the keyword remedies
  (`evals/expected/disputes/hf_review_labels.csv`, same model-reviewer caveat). No thread has
  an accepted contract; the reviewer chose human review 27 times and ask-for-evidence 11,
  never a free correction. All arms do poorly: memory 25.0%, static 22.9%, evolving 14.6%.
  Memory proposes 16 corrections or rejections no check supports; static always asks a
  question where the reviewer wanted a human. Real complaints without a contract are a gap
  for every arm.
- All arms are offline and deterministic: zero model calls, zero spend. A live-model arm
  would plug into `arms.py` with the same view and must report calls and cost.

## Still needed: a human reviewer

The review asked for independent labels. Both second passes so far came from a blind model
reviewer, which HACK.md/AGENTS.md do not accept as independent truth. To finish:

1. A teammate who hasn't seen `evals/expected/` fills `evals/cases/disputes/holdout_human_worksheet.csv`
   (`python3 evals/disputes/human_worksheet.py --sample 40` for a 40-case subset), using
   each case folder's view, CSV and preview plus HACK.md.
2. `uv run --locked --directory backend python ../evals/disputes/review.py --review <csv> --reviewer <name>`
   reports agreement with the design labels and rescores the frozen predictions.
3. For Hugging Face, a teammate re-fills `evals/expected/disputes/hf_review_worksheet.csv`
   and saves it as `hf_review_labels.csv` with their name in `reviewer`.

## 40-case subset check (October 24)

`human_worksheet.py` froze 40 holdout cases (2 per mechanism, seed 5) in
`evals/expected/disputes/human_subset.json`; the other 69 are reserved. A fresh blind
annotator (a model, no access to labels, reviews or predictions) filled
`evals/cases/disputes/holdout_human_worksheet_filled.csv`; `review.py --subset` →
`reports/holdout_review_subset-annotator.json`.

- vs the earlier blind model review: primary action 100% (kappa 1.0), verdict 95% (kappa 0.93)
- vs the design labels: action 90%, every case shares an acceptable action; 4 to adjudicate
  (H-023/H-046 wrong-row complaints: complaint unsupported but a real defect exists, both say
  free correction; H-060/H-070 privacy: out_of_scope vs undetermined, both say human review)
- arms on the subset: static 97.5%, evolving 60.0%, memory 32.5% (16 unsupported actions)

Both reviewers are models. A person filling the same worksheet with
`review.py --subset --human --reviewer <name>` is the remaining step for external claims.

