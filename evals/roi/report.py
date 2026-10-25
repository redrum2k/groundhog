"""Export a zero-network, read-only report from preserved execution records."""

import argparse
import json
import re
from collections import Counter
from pathlib import Path

from evals.roi.economics import PROFILES, assumption_manifest, modeled_minutes, project
from evals.roi.plan import save
from evals.roi.scoring import load


def dashboard_data(directory):
    report, plan = load(directory / "results.json"), load(directory / "inputs.json")
    work = load(directory / "work-ledger.json")
    cases = []
    for original in report["cases"]:
        events = [
            e for e in work if e["case_id"] == original["case_id"] and e["arm"] == original["arm"]
        ]
        row = {
            k: original.get(k)
            for k in (
                "case_id",
                "stream_id",
                "category",
                "phase",
                "arm",
                "observed_disposition",
                "booking_count",
                "quality_pass",
                "provider_episodes",
                "trace",
                "process_id",
            )
        }
        row["order_count"] = len(original["orders"])
        row["provider_work"] = dict(
            Counter(e["work_type"] for e in events if e["actor_role"] in ("operator", "controller"))
        )
        row["other_work"] = {
            role: dict(Counter(e["work_type"] for e in events if e["actor_role"] == role))
            for role in ("source_owner", "buyer")
        }
        cases.append(row)
    restarted = True
    for arm in plan["arms"]:
        before = next(r for r in cases if r["arm"] == arm and r["case_id"] == "case-010")
        after = next(r for r in cases if r["arm"] == arm and r["case_id"] == "case-011")
        restarted &= bool(
            before["process_id"]
            and after["process_id"]
            and before["process_id"] != after["process_id"]
        )
    return dict(
        source_commit=report["source_commit"],
        capsule_sha256=report["capsule_sha256"],
        seed=plan["seed"],
        summary=report["summary"],
        counts=plan["counts"],
        cases=cases,
        quality_gate=report["quality_gate"],
        assumptions=assumption_manifest(),
        restart_verified=restarted,
    )


def render(directory, report_name="report.html", *, public_snapshot=False):
    if not re.fullmatch(r"[A-Za-z0-9][\w.-]*\.html", report_name):
        raise ValueError("Presentation name must be a local HTML filename")
    data = dashboard_data(directory)
    if public_snapshot:
        # Publish only the existing aggregate/per-case counts. Local paths and process
        # identities are useful for a private audit, not a standalone public download.
        for row in data["cases"]:
            row.pop("trace", None)
            row.pop("process_id", None)
    template = Path(__file__).with_name("dashboard.html").read_text(encoding="utf-8")
    if public_snapshot:
        template = re.sub(r'href="(?!#)[^"]+"', 'href="#publication-note"', template)
        template = template.replace(
            "Each link opens original records from the isolated execution.",
            "This public snapshot contains per-case counts, not private raw traces.",
        )
        template = template.replace(
            "<footer>",
            '<footer><p id="publication-note"><b>Public evidence snapshot.</b> '
            "Private traces, databases and pilot packets are intentionally not bundled. "
            "See docs/ROI_RESULTS.md and docs/evidence/roi-lab-20261025.json in the "
            "repository for the original revision, artifact hashes and reproduction "
            "commands. This is an export of the preserved run, not a new experiment.</p>",
        )
    script = Path(__file__).with_name("dashboard.js").read_text(encoding="utf-8")
    page = template.replace("__ROI_DATA__", json.dumps(data).replace("<", "\\u003c")).replace(
        "__ROI_SCRIPT__", script
    )
    with (directory / report_name).open("x", encoding="utf-8") as handle:
        handle.write(page)
    immutable_export(directory / "assumptions.json", data["assumptions"])
    work = load(directory / "work-ledger.json")
    observed = load(directory / "results.json")
    minutes = modeled_minutes(work, observed["cases"])
    parity = []
    for baseline in ("operator", "no_learning"):
        for profile, weights in PROFILES.items():
            for realization in (0, 0.5, 1):
                saved = {
                    k: minutes[f"{baseline}:{k}"] - minutes[f"approved_learning:{k}"]
                    for k in weights
                }
                parity.append(
                    dict(
                        baseline=baseline,
                        profile=profile,
                        realization=realization,
                        expected=project(saved, weights, realization_fraction=realization),
                    )
                )
    immutable_export(directory / "calculator-parity.json", parity)
    return data


def immutable_export(path, value):
    if path.exists():
        if load(path) != value:
            raise ValueError(
                "Existing evidence/assumptions differ; use a new explicit report bundle"
            )
    else:
        save(path, value)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    print(
        json.dumps(
            {
                "report": str(args.directory / "report.html"),
                "quality_gate": render(args.directory)["quality_gate"],
            }
        )
    )
