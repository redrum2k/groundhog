"""Independent review of the holdout: agreement with the design labels and rescoring.

  uv run --locked --directory backend python ../evals/disputes/review.py --review <reviewer csv>

The reviewer labels the holdout views and artifacts blind (no access to evals/expected or
the generator). Their CSV is copied into evals/expected/disputes/holdout_review.csv, agreement
with the design labels is measured, every disagreement is listed for adjudication, and the
already-frozen predictions are rescored against the reviewer's labels. Predictions are not
recomputed; their hash must match the last scored run.
"""

import argparse
import csv
import json
import shutil
from collections import Counter

from common import (
    ACTIONS,
    CASES,
    EXPECTED,
    ROOT,
    SETTLEMENT,
    VERDICTS,
    read_jsonl,
    sha256_file,
    write_json,
)
from run_disputes import score

REPORTS = ROOT / "reports"


def split(value):
    return [v.strip() for v in (value or "").replace(",", ";").split(";") if v.strip()]


def kappa(pairs):
    n = len(pairs)
    observed = sum(a == b for a, b in pairs) / n
    left, right = Counter(a for a, _ in pairs), Counter(b for _, b in pairs)
    expected = sum(left[k] * right[k] for k in set(left) | set(right)) / (n * n)
    return round((observed - expected) / (1 - expected), 4) if expected < 1 else 1.0


def reviewer_labels(path):
    labels = {}
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            action = row["action"].strip()
            if action not in ACTIONS or row["verdict"].strip() not in VERDICTS:
                raise SystemExit(f"{row['case_id']}: invalid action or verdict")
            alternatives = [a for a in split(row.get("acceptable_alternatives")) if a in ACTIONS]
            labels[row["case_id"].strip()] = {
                "verdict": row["verdict"].strip(),
                "acceptable_primary": [action, *[a for a in alternatives if a != action]],
                "required_secondary": [
                    a for a in split(row.get("secondary_action")) if a in ACTIONS
                ],
                "required_citations": split(row.get("citations")),
                "settlement": SETTLEMENT[action],
                "forbidden_actions": [],
                "financial_flags": [],
                "notes": row.get("notes", ""),
            }
    return labels


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--review", required=True)
    parser.add_argument("--reviewer", default="independent-model-reviewer")
    parser.add_argument("--subset", action="store_true", help="score the frozen 40-case subset")
    parser.add_argument("--human", action="store_true", help="the reviewer is a person")
    args = parser.parse_args()

    manifest = json.loads((CASES / "holdout" / "MANIFEST.json").read_text(encoding="utf-8"))
    usage = json.loads((EXPECTED / "holdout_usage.json").read_text(encoding="utf-8"))
    predictions_path = REPORTS / "predictions_holdout.jsonl"
    if sha256_file(predictions_path) != usage[-1]["predictions_sha256"]:
        raise SystemExit("holdout predictions changed since the scored run")

    model_review = EXPECTED / "holdout_review.csv"
    human = args.reviewer != "independent-model-reviewer"
    target = EXPECTED / (f"holdout_review_{args.reviewer}.csv" if human else "holdout_review.csv")
    shutil.copyfile(args.review, target)
    review = reviewer_labels(target)
    design = json.loads((EXPECTED / "holdout_labels.json").read_text(encoding="utf-8"))
    ids = sorted(design)
    if args.subset:
        ids = json.loads((EXPECTED / "human_subset.json").read_text(encoding="utf-8"))["subset"]
    if set(review) != set(ids):
        raise SystemExit(f"review covers {len(review)} of {len(ids)} cases")
    action_pairs = [
        (design[i]["acceptable_primary"][0], review[i]["acceptable_primary"][0]) for i in ids
    ]
    verdict_pairs = [(design[i]["verdict"], review[i]["verdict"]) for i in ids]
    compatible = [
        i
        for i in ids
        if set(design[i]["acceptable_primary"]) & set(review[i]["acceptable_primary"])
    ]
    disagreements = [
        {
            "case_id": i,
            "mechanism": design[i]["mechanism"],
            "design": {"verdict": design[i]["verdict"], "actions": design[i]["acceptable_primary"]},
            "review": {"verdict": review[i]["verdict"], "actions": review[i]["acceptable_primary"]},
            "review_notes": review[i]["notes"],
        }
        for i in ids
        if i not in compatible or design[i]["verdict"] != review[i]["verdict"]
    ]

    views = [
        json.loads((CASES / "holdout" / i / "view.json").read_text(encoding="utf-8")) for i in ids
    ]
    preds = {}
    for row in read_jsonl(predictions_path):
        preds[row.pop("case_id")] = row
    arms = list(next(iter(preds.values())))
    rescored = {a: score(preds, views, review, a) for a in arms}
    vs_model = None
    if human and model_review.exists():
        # The question that decides whether the model review can stand in for humans.
        model = reviewer_labels(model_review)
        pairs = [
            (model[i]["acceptable_primary"][0], review[i]["acceptable_primary"][0]) for i in ids
        ]
        verdicts = [(model[i]["verdict"], review[i]["verdict"]) for i in ids]
        vs_model = {
            "primary_action_exact": round(sum(a == b for a, b in pairs) / len(ids), 4),
            "primary_action_kappa": kappa(pairs),
            "action_compatible": round(
                sum(
                    bool(set(model[i]["acceptable_primary"]) & set(review[i]["acceptable_primary"]))
                    for i in ids
                )
                / len(ids),
                4,
            ),
            "verdict_exact": round(sum(a == b for a, b in verdicts) / len(ids), 4),
            "verdict_kappa": kappa(verdicts),
        }
    both = {i: review[i] for i in compatible if design[i]["verdict"] == review[i]["verdict"]}
    agreed_scores = {a: score(preds, views, both, a) for a in arms}

    result = {
        "reviewer": args.reviewer,
        "reviewer_independence": "Human, blind to design labels, model review and predictions."
        if args.human
        else (
            "Blind to the design labels, generator and arms; a model, not a human. The repo "
            "policy says a second model agreeing with the producer is not independent truth, "
            "so treat this as a cross-check pending a human reviewer."
        ),
        "review_sha256": sha256_file(target),
        "labels_sha256": manifest["labels_sha256"],
        "cases": len(ids),
        "human_vs_model_review": vs_model,
        "agreement": {
            "primary_action_exact": round(sum(a == b for a, b in action_pairs) / len(ids), 4),
            "primary_action_kappa": kappa(action_pairs),
            "action_compatible": round(len(compatible) / len(ids), 4),
            "verdict_exact": round(sum(a == b for a, b in verdict_pairs) / len(ids), 4),
            "verdict_kappa": kappa(verdict_pairs),
            "cases_needing_adjudication": len(disagreements),
        },
        "scores_against_reviewer_labels": rescored,
        "scores_on_cases_both_labelers_agree": {"n": len(both), **agreed_scores},
        "disagreements": disagreements,
    }
    write_json(
        REPORTS / (f"holdout_review_{args.reviewer}.json" if human else "holdout_review.json"),
        result,
    )
    print(json.dumps({k: v for k, v in result.items() if k != "disagreements"}, indent=2))
    for d in disagreements:
        print(d["case_id"], d["mechanism"], d["design"], d["review"], "|", d["review_notes"])


if __name__ == "__main__":
    main()
