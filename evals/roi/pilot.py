"""Unexecuted internal timing packets; never convert blank forms into measured savings."""

import csv
import html
import io
import json
import math
from collections import defaultdict
from statistics import median

from evals.roi.plan import KINDS, PROMPT, ROOT, save, source_input

TASKS = {
    "repeat": (
        "Use permitted prior source notes to prepare a new recurring aggregate order. "
        "Check applicability, units, suppression and coverage. "
        "Record any question you still need answered."
    ),
    "documented": (
        "Use the current authoritative source dictionaries to check and prepare "
        "this order. Do not request an answer that the current document already supplies."
    ),
    "defect": (
        "Review the supplied draft delivery against the agreement and sources. "
        "If correction is needed, describe and perform it with ordinary tools, then recheck. "
        "This is pre-publication output checking, not a customer dispute."
    ),
    "objection": (
        "A buyer asks: Does standalone yoga count? Inspect the accepted gym/app scope "
        "and source definitions; write a cited answer and state whether any price, "
        "remedy or collection permission changes."
    ),
    "scope": (
        "The buyer requests an Oakland extension to the completed San Francisco order. "
        "Prepare the separate 50-cent offer and identify the additional acceptance/funding "
        "needed. Do not treat the request as payment consent."
    ),
    "exception": (
        "Check whether this source can support a fresh order. Its authority record "
        "is the current one. Identify any human action or evidence gap, and whether "
        "work or collection must stop."
    ),
}


def export_pilot(destination):
    destination.mkdir(parents=True, exist_ok=False)
    owner = json.loads(
        (ROOT / "docs/examples/judge-owner-walkthroughs.json").read_text(encoding="utf-8")
    )
    assignments, form = [], []
    for pair in range(12):
        category = KINDS[pair % len(KINDS)]
        participant = f"P{(pair + pair // 6) % 3 + 1:02d}"
        first = "operator" if pair < 6 else "groundhog"
        for order, condition in enumerate(
            (first, "groundhog" if first == "operator" else "operator")
        ):
            identifier = f"pair-{pair + 1:02d}-{chr(65 + order)}"
            bundle = source_input(
                200 + pair * 2 + order,
                "documented"
                if category == "documented"
                else "revoked"
                if category == "exception"
                else "normal",
                seed=671901,
            )
            task_dir = destination / "participants" / participant / identifier
            save(task_dir / "source-input.json", bundle)
            save(task_dir / "permitted-prior-owner-notes.json", owner)
            # A draft artifact for active checking, not an already scored result.
            rows = []
            dictionary = {r["source_family"]: r["column"] for r in owner["walkthroughs"]}
            for part in bundle["partitions"]:
                for row in part["export"]["rows"]:
                    if category == "defect" and row["zip"] == "94110":
                        continue
                    rows.append(
                        dict(
                            zip=row["zip"],
                            area=row["area"],
                            count=row["values"][dictionary[part["export"]["source_family"]]],
                            status=row["status"],
                        )
                    )
            text = io.StringIO()
            writer = csv.DictWriter(text, fieldnames=("zip", "area", "count", "status"))
            writer.writeheader()
            writer.writerows(rows)
            with (task_dir / "draft-delivery.csv").open(
                "x", encoding="utf-8", newline=""
            ) as handle:
                handle.write(text.getvalue())
            packet = dict(
                task_id=identifier,
                pair_id=f"pair-{pair + 1:02d}",
                participant_id=participant,
                condition=condition,
                presentation_order=order + 1,
                category=category,
                intent=PROMPT,
                task=TASKS[category],
                status="not_performed",
                source="source-input.json",
                notes="permitted-prior-owner-notes.json",
                declared_terms=dict(
                    geography="San Francisco",
                    category="gym_or_fitness_app",
                    age_min=25,
                    age_max=34,
                    minimum_released_count=50,
                    price_minor=100,
                    atomic_amount="1000000",
                ),
                groundhog_instruction=(
                    "Use a NEW offline/mock isolated instance or task harness. "
                    "Ingest these exact artifacts with the ordinary source-learning commands; "
                    "retain your own chronological notes and charge setup/approval. "
                    "Do not open ROI results or evaluator files."
                ),
                operator_instruction=(
                    "Use CSV/SQL/spreadsheet tools, these current docs, the "
                    "ordinary artifact verifier, and your own persistent notes. Do not open "
                    "another condition's future packet or any evaluator output."
                ),
            )
            save(task_dir / "task.json", packet)
            assignments.append(packet)
            form.append(
                dict(
                    task_id=identifier,
                    pair_id=packet["pair_id"],
                    participant_id=participant,
                    condition=condition,
                    category=category,
                    active_seconds=None,
                    waiting_seconds=None,
                    started_at=None,
                    ended_at=None,
                    mistakes=None,
                    correction_seconds=None,
                    notes=None,
                    provenance="not_performed",
                )
            )
            page = (
                f"<!doctype html><meta charset='utf-8'><title>{identifier}</title>"
                "<style>body{font:18px/1.6 system-ui;max-width:850px;margin:50px auto;"
                "padding:20px}code{background:#eee;padding:4px}</style>"
                "<h1>Groundhog internal timing task</h1>"
                f"<p>{participant} · {identifier} · {condition} · order {order + 1}</p>"
                f"<p>{html.escape(TASKS[category])}</p><h2>Allowed inputs</h2>"
                "<p><a href='source-input.json'>Current sources and authority</a> · "
                "<a href='permitted-prior-owner-notes.json'>Prior owner notes</a> · "
                "<a href='draft-delivery.csv'>Draft delivery</a> · "
                "<a href='task.json'>Terms and tool instructions</a></p>"
                "<p>Time ACTIVE attention, pause for machine/network waits. Include checking, "
                "interpretation, approval, mistakes and correction. This packet has not been "
                "performed; no duration is supplied.</p>"
            )
            with (task_dir / "task.html").open("x", encoding="utf-8") as handle:
                handle.write(page)
    save(destination / "assignments.json", assignments)
    save(destination / "timing-form.json", form)
    save(destination / "observations.json", [])
    save(
        destination / "practice-excluded.json",
        dict(
            task=(
                "Practice checking a fresh two-partition source, clarifying units, authorizing "
                "a mock quote and pausing the attention timer. Do not include in analysis."
            ),
            source=source_input(990, "documented", seed=92111),
            measured=False,
        ),
    )
    instructions = """# Internal timing pilot — not yet performed

12 paired task packets, two pairs in each of six categories; 24 tasks total.
P01/P02/P03 are unassigned internal participant IDs, not recruited people.
Equivalent A/B tasks use fresh distinct values/hashes. Condition order is counterbalanced
across IDs; each person receives only their next task, not future packets or evaluator results.
Retain allowed prior notes within each condition; never transfer future answers across conditions.

1. Obtain two or three willing teammates yourself; record the actual IDs/assignment.
   No third-party outreach is performed by the agent. With two, redistribute whole pairs
   and counterbalance order before timing.
2. Complete practice-excluded.json first. Use ordinary tools for operator tasks and a separate
   offline/mock Groundhog instance for assisted tasks. Account for source setup, learning
   approval and task-specific review rather than assuming zero effort.
3. Open each task.html. Start/pause an attention timer for active reading, checking,
   interpretation, approvals, corrections and mistakes. Waiting is separate.
   Do not use end-to-end wall time as active work.
4. Copy only completed rows from timing-form.json to observations.json, using provenance
   internal_timed_pilot. Fill actual start/end, active and waiting seconds and mistakes.
   Correction seconds are a subset of active seconds, never an additional charge.
   Leave unperformed observations absent.
5. Preserve raw observations. Analyze only complete paired observations within matching category;
   report participant count, pairs, medians/ranges and errors. This is a small internal pilot,
   not employee validation. Do not apply one category's time to another.

The packets contain allowed current documentation and source notes, not evaluator verdicts.
ROI results and evaluator-only.json are not participant materials. No measured-minute savings
exist until people actually complete these tasks.
"""
    with (destination / "README.md").open("x", encoding="utf-8") as handle:
        handle.write(instructions)
    return {
        "pairs": 12,
        "tasks": 24,
        "categories": list(KINDS),
        "completed_observations": 0,
        "measured_minutes_saved": None,
    }


def summarize_observations(observations):
    pairs, ids = defaultdict(dict), set()
    for row in observations:
        if row.get("active_seconds") is None:
            continue
        if (
            row.get("provenance") != "internal_timed_pilot"
            or not row.get("started_at")
            or not row.get("ended_at")
        ):
            raise ValueError("Actual timing provenance and timestamps required")
        identifier = (row["participant_id"], row["task_id"])
        if (
            identifier in ids
            or not math.isfinite(row["active_seconds"])
            or row["active_seconds"] < 0
            or row["category"] not in KINDS
        ):
            raise ValueError("Duplicate or invalid timing observation")
        ids.add(identifier)
        if (row.get("correction_seconds") or 0) > row["active_seconds"]:
            raise ValueError("Correction attention must be included in active attention")
        key = (row["participant_id"], row["pair_id"], row["category"])
        if row["condition"] not in ("operator", "groundhog") or row["condition"] in pairs[key]:
            raise ValueError("Duplicate/unknown condition")
        pairs[key][row["condition"]] = row["active_seconds"]
    grouped = defaultdict(list)
    participants = set()
    for (participant, _, category), values in pairs.items():
        if set(values) == {"operator", "groundhog"}:
            grouped[category].append((values["operator"] - values["groundhog"]) / 60)
            participants.add(participant)
    return dict(
        evidence_class="timed_pilot" if grouped else "unavailable",
        participants=len(participants),
        completed_pairs=sum(map(len, grouped.values())),
        measured_minutes_saved_by_category={
            k: dict(median=median(v), minimum=min(v), maximum=max(v), pairs=len(v))
            for k, v in grouped.items()
        }
        or None,
    )
