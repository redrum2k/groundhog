"""Leakage audit and diagnostic baselines for the dispute bundle.

  uv run --directory backend python ../evals/disputes/audit.py --dataset <dispute-dataset dir>

Metadata lookups are leakage diagnostics, not agent evaluations.
"""

import argparse
import json
from collections import Counter, defaultdict

from common import ROOT, Dataset, TfIdf, read_jsonl, write_json


def knn_family(index, train, text, k=7):
    votes = Counter()
    for score, i in index.nearest(text, k):
        votes[train[i]["resolution"]["family"]] += score
    return votes.most_common(1)[0][0] if votes else None


def lookup_accuracy(train, test, key):
    table = defaultdict(Counter)
    for c in train:
        table[key(c)][c["resolution"]["family"]] += 1
    right = sum(
        table[key(c)] and table[key(c)].most_common(1)[0][0] == c["resolution"]["family"]
        for c in test
    )
    return right / len(test)


def message(c):
    return c["thread"][0]["text"]


def message_checks(c):
    return (
        message(c)
        + " "
        + " ".join(x.get("evidence", "") for x in c["checks"] if x["status"] == "fail")
    )


def audit(ds):
    sim = ds.root / "data" / "sim"
    test_ids = {c["case_id"] for c in ds.dev}
    contrastive = read_jsonl(sim / "contrastive.jsonl")
    convergent = read_jsonl(sim / "convergent.jsonl")
    lessons = json.loads((sim / "lessons.json").read_text(encoding="utf-8"))
    lesson_ids = {i for lesson in lessons for i in json.dumps(lesson).split('"') if i in test_ids}
    variants = {
        split: {c["dispute"]["variant"] for c in cases}
        for split, cases in (("train", ds.train), ("test", ds.dev))
    }
    train_msgs = {message(c) for c in ds.train}
    leakage = {
        "contrastive_test_pairs": sum(p["case_id"] in test_ids for p in contrastive),
        "convergent_test_ids": len({i for g in convergent for i in g["case_ids"] if i in test_ids}),
        "lessons_test_ids": len(lesson_ids),
        "variants_train": len(variants["train"]),
        "variants_test": len(variants["test"]),
        "variants_unseen_in_train": sorted(variants["test"] - variants["train"]),
        "test_messages_verbatim_in_train": sum(message(c) in train_msgs for c in ds.dev),
    }
    baselines = {}
    for name, text in (
        ("tfidf_message_only", message),
        ("tfidf_message_plus_failing_checks", message_checks),
    ):
        index = TfIdf([text(c) for c in ds.train])
        right = sum(
            knn_family(index, ds.train, text(c)) == c["resolution"]["family"] for c in ds.dev
        )
        baselines[name] = round(right / len(ds.dev), 4)
    baselines["DIAGNOSTIC_lookup_issue_type"] = round(
        lookup_accuracy(ds.train, ds.dev, lambda c: c["dispute"]["issue_type"]), 4
    )
    baselines["DIAGNOSTIC_lookup_variant"] = round(
        lookup_accuracy(ds.train, ds.dev, lambda c: c["dispute"]["variant"]), 4
    )
    baselines["DIAGNOSTIC_lookup_failing_requirements"] = round(
        lookup_accuracy(
            ds.train,
            ds.dev,
            lambda c: tuple(sorted(x["requirement"] for x in c["checks"] if x["status"] == "fail")),
        ),
        4,
    )
    mapped = [h for h in ds.hf if h.get("maps_to_family")]
    index = TfIdf([message(c) for c in ds.train])
    hf_right = sum(
        knn_family(index, ds.train, h["title"] + " " + h["comments"][0]["text"][:500])
        == h["maps_to_family"]
        for h in mapped
    )
    outcomes = Counter(c["outcome"]["buyer_accepted"] for c in ds.cases)
    return {
        "dataset_fingerprint": ds.fingerprint,
        "counts": {
            "simulated": len(ds.cases),
            "train": len(ds.train),
            "development_tests": len(ds.dev),
            "hf_threads": len(ds.hf),
            "hf_keyword_mapped": len(mapped),
        },
        "leakage": leakage,
        "baselines_on_221_development_tests": baselines,
        "hf_keyword_mapped_agreement": f"{hf_right}/{len(mapped)}",
        "notes": [
            "contrastive.jsonl, convergent.jsonl and lessons.json reference test cases; "
            "rebuild memory from train only (build_memory.py).",
            "All test variants also occur in train: the 221 cases measure wording "
            "generalization only, and are development tests after any debugging use.",
            "Lookup rows read scenario metadata a runtime agent never receives.",
            "HF targets are keyword-assigned, not adjudicated contractual decisions.",
            "Simulated acceptance/CSAT outcomes are random draws from fixed probabilities: "
            f"{dict(outcomes)} accepted; they cannot show operational improvement.",
        ],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--output", default=str(ROOT / "reports" / "audit.json"))
    args = parser.parse_args()
    report = audit(Dataset(args.dataset))
    write_json(args.output, report)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
