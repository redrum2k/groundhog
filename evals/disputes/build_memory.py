"""Rebuild improvement memory from the 1,279 training cases only.

  uv run --directory backend python ../evals/disputes/build_memory.py --dataset <dir>

Writes contrastive.jsonl, convergent.jsonl and lessons.json under evals/disputes/build/memory
(git-ignored). Every remedy is translated to aggregate-brokerage-v1 actions first: credits,
refunds, SLA credits and agent settlements are not permitted procedures, so they are never
stored as something to do. Test (development) cases never enter memory.
"""

import argparse
import json
from collections import Counter, defaultdict

from common import (
    MONEY_WORDS,
    NOT_PERMITTED_FAMILIES,
    POLICY_MAP,
    ROOT,
    Dataset,
    failing_checks,
    sha256_file,
    sim_view,
    view_text,
    write_json,
    write_jsonl,
)

OUT = ROOT / "build" / "memory"
REROUTE = (
    "Route to human review with the failing evidence. The agent has no payment "
    "authority and aggregate-brokerage-v1 offers no credit for this case."
)


def first_correct_reply(case):
    thread = case["thread"]
    wrong = any(t["type"] == "wrong_first_action" for t in thread)
    agent = [t for t in thread if t["actor"] == "agent" and t["type"] != "wrong_first_action"]
    return (agent[0]["text"] if agent else ""), wrong


def scrub(text):
    """Keep the reasoning, drop the Northbeam money mechanics the aggregate policy forbids."""
    return MONEY_WORDS.sub("[not permitted: financial action]", text)


def build(ds):
    contrastive, by_action, by_family = [], defaultdict(list), defaultdict(list)
    for case in ds.train:
        family = case["resolution"]["family"]
        actions, verdict, note = POLICY_MAP[family]
        view = sim_view(case)
        reply, wrong_first = first_correct_reply(case)
        if family in NOT_PERMITTED_FAMILIES:
            # The original reply applies a credit; storing it would teach a forbidden action.
            reply = REROUTE
        contrastive.append(
            {
                "pair_id": "train-" + case["case_id"],
                "case_id": case["case_id"],
                "context": view_text(view),
                "failing_families": sorted(
                    {c["family"] for c in view["checks"] if c["status"] != "PASS"}
                ),
                "chosen_actions": list(actions),
                "chosen_verdict": verdict,
                "chosen_reasoning": scrub(reply),
                "rejected": scrub(case["rejected_alternative"]["action"]),
                "why_rejected_is_worse": scrub(case["rejected_alternative"]["why_worse"]),
                "first_response_was_wrong": wrong_first,
                "policy_note": note,
                "source_family": family,
            }
        )
        by_action[actions].append(case)
        by_family[family].append(case)
    convergent = [
        {
            "actions": list(actions),
            "n_cases": len(cases),
            "distinct_failing_signatures": sorted(
                {
                    ",".join(sorted({c["requirement"] for c in failing_checks(x["checks"])}))
                    or "none"
                    for x in cases
                }
            ),
            "source_families": dict(Counter(x["resolution"]["family"] for x in cases)),
            "example_buyer_messages": [x["thread"][0]["text"] for x in cases[:6]],
            "case_ids": [x["case_id"] for x in cases],
        }
        for actions, cases in sorted(by_action.items())
    ]
    original = {
        lesson["family"]: lesson
        for lesson in json.loads(
            (ds.root / "data" / "sim" / "lessons.json").read_text(encoding="utf-8")
        )
    }
    lessons = []
    for family, cases in sorted(by_family.items()):
        actions, verdict, note = POLICY_MAP[family]
        base = original[family]
        if family in NOT_PERMITTED_FAMILIES:
            do = REROUTE
        else:
            do = scrub(base["do"])
        lessons.append(
            {
                "id": f"L-{family}",
                "source_family": family,
                "actions": list(actions),
                "verdict": verdict,
                "when": base["when"],
                "do": do,
                "avoid": scrub(base["avoid"]),
                "policy_note": note,
                "evidence": {
                    "train_cases": len(cases),
                    "sample_case_ids": [c["case_id"] for c in cases[:8]],
                    "simulated_acceptance_rate": round(
                        sum(c["outcome"]["buyer_accepted"] for c in cases) / len(cases), 3
                    ),
                    "caveat": "Acceptance is a random simulated draw, not observed effectiveness.",
                },
            }
        )
    return contrastive, convergent, lessons


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--output", default=str(OUT))
    args = parser.parse_args()
    ds = Dataset(args.dataset)
    contrastive, convergent, lessons = build(ds)
    dev_ids = {c["case_id"] for c in ds.dev}
    stored = json.dumps([contrastive, convergent, lessons])
    leaked = sorted(i for i in dev_ids if f'"{i}"' in stored)
    if leaked:
        raise SystemExit(f"development cases leaked into memory: {leaked[:5]}")
    out = ROOT / args.output if not args.output.startswith("/") else args.output
    write_jsonl(f"{out}/contrastive.jsonl", contrastive)
    write_jsonl(f"{out}/convergent.jsonl", convergent)
    write_json(f"{out}/lessons.json", lessons)
    manifest = {
        "dataset_fingerprint": ds.fingerprint,
        "train_cases": len(ds.train),
        "development_ids_in_memory": 0,
        "files": {
            name: sha256_file(f"{out}/{name}")
            for name in ("contrastive.jsonl", "convergent.jsonl", "lessons.json")
        },
        "not_permitted_families_rerouted": sorted(NOT_PERMITTED_FAMILIES),
    }
    write_json(f"{out}/manifest.json", manifest)
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
