"""Real-language stress set from the 156 Hugging Face dataset discussions.

  uv run --directory backend python ../evals/disputes/hf_stress.py --dataset <dir>

Writes
  evals/cases/disputes/hf_views.jsonl            decision views: title + reporter's opening text
  evals/expected/disputes/hf_review_worksheet.csv stratified subset for an independent reviewer

The bundle's `maps_to_family` is a keyword assignment, not an adjudicated decision, so it
is left out of both files to avoid anchoring the reviewer. No accepted purchase contract
exists for these threads: views carry no agreement and no verified checks, so "the
evidence is insufficient" is often the right answer. The reviewer fills the label columns;
run_disputes.py scores only rows with a reviewer and an action.
"""

import argparse
import csv
import random
from collections import defaultdict

from common import ACTIONS, CASES, EXPECTED, VERDICTS, Dataset, write_jsonl

SUBSET = 48
LABEL_COLUMNS = (
    "reviewer",
    "contract_obligation_established",  # yes / no
    "evidence_sufficient",  # yes / no / unclear
    "verdict",  # one of VERDICTS
    "appropriate_action",  # one of ACTIONS
    "notes",
)


def opening(thread):
    first = next((c for c in thread["comments"] if c["role"] == "reporter"), thread["comments"][0])
    return first["text"]


def view(thread):
    return {
        "case_id": thread["id"],
        "domain": "huggingface-real",
        "agreement": None,
        "checks": [],
        "source_ok": None,
        "messages": [{"actor": "buyer", "text": f"{thread['title']}\n\n{opening(thread)[:2000]}"}],
        "complaint_target": None,
        "correction_used": False,
        "questions_asked": 0,
        "max_questions": 2,
    }


def stratified(threads, n, seed=11):
    by = defaultdict(list)
    for t in threads:
        by[t.get("category") or "uncategorized"].append(t)
    rng = random.Random(seed)
    for group in by.values():
        rng.shuffle(group)
    picked = []
    while len(picked) < n and any(by.values()):
        for key in sorted(by):
            if by[key] and len(picked) < n:
                picked.append(by[key].pop())
    return picked


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--subset", type=int, default=SUBSET)
    args = parser.parse_args()
    ds = Dataset(args.dataset)
    write_jsonl(CASES / "hf_views.jsonl", [view(t) for t in ds.hf])
    EXPECTED.mkdir(parents=True, exist_ok=True)
    path = EXPECTED / "hf_review_worksheet.csv"
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            (
                "thread_id",
                "url",
                "dataset",
                "category",
                "title",
                "reporter_text",
                "maintainer_reply",
                *LABEL_COLUMNS,
            )
        )
        for t in stratified(ds.hf, args.subset):
            reply = next((c["text"] for c in t["comments"] if c["role"] == "maintainer"), "")
            writer.writerow(
                (
                    t["id"],
                    t["url"],
                    t["dataset"],
                    t.get("category"),
                    t["title"],
                    opening(t)[:1500],
                    reply[:1500],
                    *[""] * len(LABEL_COLUMNS),
                )
            )
    print(f"{len(ds.hf)} HF views; {args.subset}-thread worksheet at {path}")
    print("allowed verdicts:", ", ".join(VERDICTS))
    print("allowed actions:", ", ".join(ACTIONS))


if __name__ == "__main__":
    main()
