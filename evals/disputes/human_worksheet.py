"""Frozen, blind human-review subset of the holdout.

  python3 evals/disputes/human_worksheet.py

Selection: 2 cases per mechanism (20 mechanisms -> 40 cases), chosen with random.Random(5)
from each mechanism's case IDs. Mechanism names are used only to pick IDs and never appear
in the worksheet. The other 69 cases are reserved for later evaluation. The subset is frozen
in evals/expected/disputes/human_subset.json (IDs, seed, sha256 of the blank worksheet)
before the annotator sees anything; the script refuses to reselect once it exists.

The annotator sees only the same inputs an agent sees (buyer messages, targeted requirement,
check results, case folder). No design labels, model-review labels or arm predictions.
Fill the label columns, then:
  uv run --locked --directory backend python ../evals/disputes/review.py \
      --review <filled csv> --reviewer <name> --subset
"""

import csv
import json
import random
from collections import defaultdict

from common import ACTIONS, CASES, EXPECTED, VERDICTS, sha256_file, write_json

SEED = 5
PER_MECHANISM = 2
COLUMNS = (
    "case_id",
    "buyer_messages",
    "complaint_target",
    "non_pass_checks",
    "case_folder",
    "verdict",
    "action",
    "secondary_action",
    "citations",
    "acceptable_alternatives",
    "notes",
)


def main():
    freeze = EXPECTED / "human_subset.json"
    if freeze.exists():
        raise SystemExit(f"subset already frozen: {freeze}")
    labels = json.loads((EXPECTED / "holdout_labels.json").read_text(encoding="utf-8"))
    by = defaultdict(list)
    for cid, label in sorted(labels.items()):
        by[label["mechanism"]].append(cid)
    rng = random.Random(SEED)
    subset = sorted(cid for m in sorted(by) for cid in rng.sample(by[m], PER_MECHANISM))
    reserved = sorted(set(labels) - set(subset))
    path = CASES / "holdout_human_worksheet.csv"
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(COLUMNS)
        for cid in subset:
            view = json.loads((CASES / "holdout" / cid / "view.json").read_text(encoding="utf-8"))
            checks = "; ".join(
                f"{c['requirement']}={c['status']}" for c in view["checks"] if c["status"] != "PASS"
            )
            writer.writerow(
                (
                    cid,
                    " / ".join(m["text"] for m in view["messages"]),
                    view["complaint_target"],
                    checks or "all PASS",
                    f"evals/cases/disputes/holdout/{cid}",
                    *[""] * 6,
                )
            )
    write_json(
        freeze,
        {
            "selection": f"{PER_MECHANISM} per mechanism, random.Random({SEED}) over sorted IDs",
            "subset": subset,
            "reserved_for_later": reserved,
            "blank_worksheet_sha256": sha256_file(path),
            "annotator_sees": "buyer messages, complaint target, check results, case folder",
            "annotator_never_sees": "design labels, model-review labels, arm predictions",
        },
    )
    print(f"{len(subset)} cases -> {path}; {len(reserved)} reserved")
    print("verdict:", ", ".join(VERDICTS))
    print("action:", ", ".join(ACTIONS))


if __name__ == "__main__":
    main()
