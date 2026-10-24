"""Compare static, functional-memory and evolving-procedure arms on identical cases.

  uv run --locked --directory backend python ../evals/disputes/run_disputes.py --dataset <dir>

Order of operations (labels are never available while arms decide):
  1. fit arms on the 1,279 training cases only; hash the frozen memory and procedures
  2. decide every development, HF and holdout view; write and hash the predictions
  3. only then load labels: development (policy-mapped sim), reviewed HF rows, and the
     sealed holdout, whose label hash must match its MANIFEST
  4. score and write reports/results.json + reports/RESULTS.md

The 221 simulated test cases are development tests (wording generalization), not a holdout.
"""

import argparse
import csv
import json

from arms import Evolving, Memory, Static, train_set
from build_memory import build
from common import (
    ABSTAIN,
    ACTIONS,
    CASES,
    EXPECTED,
    ROOT,
    SETTLEMENT,
    Dataset,
    assert_safe_view,
    read_jsonl,
    sha256_file,
    sha256_json,
    sim_label,
    sim_view,
    write_json,
    write_jsonl,
)

REPORTS = ROOT / "reports"


def holdout_views():
    root = CASES / "holdout"
    manifest = json.loads((root / "MANIFEST.json").read_text(encoding="utf-8"))
    views = []
    for item in manifest["index"]:
        path = root / item["case_id"] / "view.json"
        if sha256_file(path) != item["view_sha256"]:
            raise SystemExit(f"holdout view {item['case_id']} changed after sealing")
        views.append(json.loads(path.read_text(encoding="utf-8")))
    return views, manifest


def predict(arms, views):
    out = {}
    for view in views:
        assert_safe_view(view)
        out[view["case_id"]] = {arm.name: arm.decide(view) for arm in arms}
    return out


def normalize(label):
    if "acceptable_primary" in label:
        return label
    return {
        **label,
        "acceptable_primary": [label["primary_action"]],
        "required_secondary": label["acceptable_actions"][1:],
        "forbidden_actions": [],
        "financial_flags": [],
    }


def unsupported(pred, view):
    statuses = [c["status"] for c in view["checks"]]
    actions = pred["actions"]
    if any(a not in ACTIONS for a in actions):
        return True
    if "free_correction" in actions and "FAIL" not in statuses:
        return True
    return "reject_unsupported" in actions and any(s != "PASS" for s in statuses)


def financial_violation(pred, label):
    # Rationale wording ("no credit is permitted") is not an action; only proposals count.
    if pred.get("financial_action") is not None:
        return True
    return (
        "no_charge_for_owed_scope" in label["financial_flags"]
        and "offer_separate_work" in pred["actions"]
    )


def score(preds, views, labels, arm):
    rows = []
    for view in views:
        cid = view["case_id"]
        if cid not in labels:
            continue
        label, pred = normalize(labels[cid]), preds[cid][arm]
        actions = pred["actions"]
        flagged = {c["requirement"] for c in view["checks"] if c["status"] != "PASS"}
        cited = set(pred["citations"])
        required = set(label["required_citations"])
        decidable = label["verdict"] != "undetermined"
        rows.append(
            {
                "action": actions[0] in label["acceptable_primary"]
                and set(label["required_secondary"]) <= set(actions),
                "verdict": pred["verdict"] == label["verdict"],
                "settlement": SETTLEMENT[actions[0]] == label["settlement"],
                "unsupported": unsupported(pred, view),
                "forbidden": bool(set(actions) & set(label["forbidden_actions"])),
                "undetermined": not decidable,
                "abstained": actions[0] in ABSTAIN,
                "cite_case": bool(required),
                "cite_recall": len(cited & required) / len(required) if required else None,
                "cite_grounded": all(
                    c in flagged or c == view.get("complaint_target") for c in cited
                ),
                "financial": financial_violation(pred, label),
                "human": "human_review" in actions,
                "calls": pred["model_calls"],
                "usd": pred["model_usd"],
            }
        )
    n = len(rows)
    if not n:
        return {"n": 0}
    und = [r for r in rows if r["undetermined"]]
    cite = [r for r in rows if r["cite_case"]]
    rate = lambda key, pool=rows: round(sum(r[key] for r in pool) / len(pool), 4) if pool else None  # noqa: E731
    return {
        "n": n,
        "action_accuracy": rate("action"),
        "verdict_accuracy": rate("verdict"),
        "settlement_correct": rate("settlement"),
        "unsupported_actions": sum(r["unsupported"] for r in rows),
        "forbidden_actions": sum(r["forbidden"] for r in rows),
        "correct_abstentions": f"{sum(r['abstained'] for r in und)}/{len(und)}",
        "over_abstentions": sum(r["abstained"] and not r["undetermined"] for r in rows),
        "citation_recall": round(sum(r["cite_recall"] for r in cite) / len(cite), 4)
        if cite
        else None,
        "ungrounded_citations": sum(not r["cite_grounded"] for r in rows),
        "financial_policy_violations": sum(r["financial"] for r in rows),
        "human_interventions": sum(r["human"] for r in rows),
        "model_calls": sum(r["calls"] for r in rows),
        "model_usd": round(sum(r["usd"] for r in rows), 4),
    }


def log_holdout_use(manifest, frozen):
    """Every label opening is recorded. A changed arm after any entry needs a new holdout."""
    path = EXPECTED / "holdout_usage.json"
    usage = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
    entry = {
        "labels_sha256": manifest["labels_sha256"],
        "seed": manifest["seed"],
        "procedures_sha256": frozen["procedures_sha256"],
        "memory_sha256": frozen["memory_sha256"],
        "static_sha256": sha256_file(ROOT / "arms.py"),
        "predictions_sha256": frozen["predictions_sha256"]["holdout"],
    }
    if entry not in usage:
        usage.append(entry)
        write_json(path, usage)
    frozen["holdout_scored_runs"] = len(usage)


def hf_reviewed_labels():
    path = EXPECTED / "hf_review_labels.csv"
    if not path.exists():
        return {}, str(path)
    labels = {}
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row.get("reviewer") and row.get("appropriate_action") in ACTIONS:
                action = row["appropriate_action"]
                labels[row["thread_id"]] = {
                    "verdict": row.get("verdict") or "undetermined",
                    "acceptable_primary": [action],
                    "required_secondary": [],
                    "required_citations": [],
                    "settlement": SETTLEMENT[action],
                    "forbidden_actions": [],
                    "financial_flags": [],
                }
    return labels, str(path)


def markdown(results):
    lines = ["# Dispute arm comparison", "", results["summary"], ""]
    metrics = [
        "n",
        "action_accuracy",
        "verdict_accuracy",
        "settlement_correct",
        "unsupported_actions",
        "forbidden_actions",
        "correct_abstentions",
        "over_abstentions",
        "citation_recall",
        "ungrounded_citations",
        "financial_policy_violations",
        "human_interventions",
        "model_calls",
        "model_usd",
    ]
    for name, block in results["sets"].items():
        lines += [f"## {name}", "", block["description"], ""]
        if not block["scores"].get("static", {}).get("n"):
            lines += [block.get("unscored_reason", "No labels yet."), ""]
            continue
        lines.append("| metric | " + " | ".join(block["scores"]) + " |")
        lines.append("| --- |" + " --- |" * len(block["scores"]))
        for m in metrics:
            lines.append(
                f"| {m} | "
                + " | ".join(str(block["scores"][a].get(m)) for a in block["scores"])
                + " |"
            )
        lines.append("")
    lines += ["## Frozen inputs", "", "```json", json.dumps(results["frozen"], indent=2), "```", ""]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", required=True)
    args = parser.parse_args()
    ds = Dataset(args.dataset)

    # 1. Fit on train only, then freeze.
    contrastive, _, _ = build(ds)
    dev_ids = {c["case_id"] for c in ds.dev}
    if any(p["case_id"] in dev_ids for p in contrastive):
        raise SystemExit("memory contains development cases")
    views, labels = train_set(ds)
    memory_labels = [
        {"actions": p["chosen_actions"], "verdict": p["chosen_verdict"]} for p in contrastive
    ]
    arms = [
        Static().fit(views, labels),
        Memory().fit(views, memory_labels),
        Evolving().fit(views, labels),
    ]
    frozen = {
        "dataset_fingerprint": ds.fingerprint,
        "memory_sha256": sha256_json(contrastive),
        "procedures_sha256": sha256_json(arms[2].procedures()),
        "evolving_history": arms[2].history,
    }
    write_json(REPORTS / "procedures.json", arms[2].procedures())

    # 2. Decide everything before any label is read.
    dev_views = [sim_view(c) for c in ds.dev]
    hf_views = read_jsonl(CASES / "hf_views.jsonl") if (CASES / "hf_views.jsonl").exists() else []
    hold_views, manifest = holdout_views()
    predictions = {
        "development": predict(arms, dev_views),
        "hf_real": predict(arms, hf_views),
        "holdout": predict(arms, hold_views),
    }
    for name, preds in predictions.items():
        write_jsonl(
            REPORTS / f"predictions_{name}.jsonl", [{"case_id": k, **v} for k, v in preds.items()]
        )
    frozen["predictions_sha256"] = {
        name: sha256_file(REPORTS / f"predictions_{name}.jsonl") for name in predictions
    }

    # 3. Labels only now.
    labels_path = EXPECTED / "holdout_labels.json"
    if sha256_file(labels_path) != manifest["labels_sha256"]:
        raise SystemExit("holdout labels do not match the sealed manifest hash")
    hold_labels = json.loads(labels_path.read_text(encoding="utf-8"))
    log_holdout_use(manifest, frozen)
    dev_labels = {c["case_id"]: sim_label(c) for c in ds.dev}
    hf_labels, hf_path = hf_reviewed_labels()

    # 4. Score.
    names = [a.name for a in arms]
    sets = {
        "Sealed aggregate holdout": {
            "description": f"{len(hold_views)} cases across {manifest['mechanisms']} "
            "aggregate-brokerage mechanisms built from actual source and delivery bytes; "
            "checks are the real verify_dataset output. Labels sealed until predictions froze.",
            "scores": {a: score(predictions["holdout"], hold_views, hold_labels, a) for a in names},
        },
        "Development (221 simulated test cases)": {
            "description": "Wording generalization only: same 26 templates as train, remedies "
            "translated to aggregate-brokerage-v1. Development tests, not a holdout.",
            "scores": {
                a: score(predictions["development"], dev_views, dev_labels, a) for a in names
            },
        },
        "Real-language stress (Hugging Face)": {
            "description": f"{len(hf_views)} real threads, no accepted contract or verified "
            "checks. Scored only on independently reviewed rows; keyword-assigned remedies "
            "are not ground truth.",
            "scores": {a: score(predictions["hf_real"], hf_views, hf_labels, a) for a in names},
            "unscored_reason": f"No reviewed labels yet. Fill {hf_path} "
            "from hf_review_worksheet.csv.",
            "unreviewed_action_mix": {
                a: dict(
                    sorted(
                        {
                            act: sum(
                                p[a]["actions"][0] == act for p in predictions["hf_real"].values()
                            )
                            for act in ACTIONS
                        }.items()
                    )
                )
                for a in names
            },
        },
    }
    hold = sets["Sealed aggregate holdout"]["scores"]
    best = max(names, key=lambda a: (hold[a]["action_accuracy"], -hold[a]["unsupported_actions"]))
    summary = (
        "On the sealed holdout, action accuracy is "
        + ", ".join(f"{a} {hold[a]['action_accuracy']:.1%}" for a in names)
        + f"; best arm: {best}. A learning claim needs the evolving arm to beat the static "
        "checklist here without more unsupported or financial-policy violations."
    )
    results = {"summary": summary, "sets": sets, "frozen": frozen}
    write_json(REPORTS / "results.json", results)
    (REPORTS / "RESULTS.md").write_text(markdown(results), encoding="utf-8")
    print(markdown(results))


if __name__ == "__main__":
    main()
