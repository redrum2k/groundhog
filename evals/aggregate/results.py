"""Normalize observations once for both JSON and Markdown, then score frozen labels."""

import json
import re

from evals.aggregate.audit import audit_artifacts, exact_cell, read_bytes
from evals.aggregate.schema import REQUIREMENTS


def redact(text):
    text = re.sub(r"https?://[^\s<>]+", "[URL redacted]", str(text))
    text = re.sub(r"(?i)(?:sk-|bearer\s+)[A-Za-z0-9_./+=-]+", "[credential redacted]", text)
    text = re.sub(r"(?i)(api[_-]?key|token|secret|password)\s*[:=]\s*\S+", r"\1=[redacted]", text)
    return text


def action(order):
    if order["ledger"]:
        return "settle"
    if order["cases"] and order["cases"][-1]["status"] == "unsupported":
        return "unsupported"
    if order["order_state"] == "human_review":
        return "escalate"
    if order["order_state"] == "processing" and order["free_corrections_used"]:
        return "correct"
    if order["evidence_requests"] and not order["evidence_requests"][-1]["answered"]:
        return "request_evidence"
    if order["deliveries"]:
        return "publish"
    return "block"


def normalize(case, expected, directory, public, operation):
    result = {
        "case_id": case.id,
        "title": redact(case.title),
        "classification": case.classification,
        "review_status": expected.review_status if expected else "missing",
        "reviewer": redact(expected.reviewer) if expected else None,
        "review_rationale": redact(expected.review_rationale) if expected else None,
        "operation": operation,
        "checkpoints": [],
        "mismatches": [],
        "unavailable": [],
    }
    labels = {c.id: c for c in expected.checkpoints} if expected else {}
    for name in case.checkpoints:
        path = directory / f"checkpoint-{name}.json"
        label = labels.get(name)
        try:
            saved = json.loads(path.read_bytes()) if path.exists() else None
            checkpoint, diagnostics = normalize_checkpoint(
                case.id, name, label, saved, directory, public
            )
        except Exception as error:
            # A damaged checkpoint must not erase other observations or execution status.
            checkpoint, diagnostics = normalize_checkpoint(
                case.id, name, label, None, directory, public
            )
            diagnostics["unavailable"].append(f"{name}:audit_{type(error).__name__}")
        result["checkpoints"].append(checkpoint)
        for key in ("mismatches", "unavailable"):
            result[key].extend(diagnostics[key])
    result["outcome"] = (
        "incomplete"
        if result["unavailable"] or operation["status"] != "completed"
        else "mismatch"
        if result["mismatches"]
        else "match"
    )
    return result


def normalize_checkpoint(case_id, name, label, saved, directory, public):
    result = {"mismatches": [], "unavailable": []}
    if saved is None:
        result["unavailable"].append(f"checkpoint:{name}")
        checkpoint = {
            "id": name,
            "action": None,
            "financial": None,
            "artifact_audit": None,
            "requirements": [],
            "complaint": None,
            "binding": None,
            "attempt": None,
        }
        order = attempt = None
    else:
        order, attempt = saved["order"], saved["attempt"]
        if not attempt:
            result["unavailable"].append(f"findings:{name}")
        output = attempt["output"] if attempt else None
        if output is None and order["deliveries"]:
            output = order["deliveries"][-1]
        artifact_audit = audit_artifacts(directory / "artifacts", order, output)
        files = []
        for artifact in artifact_audit.pop("public"):
            extension = "csv" if artifact["media_type"] == "text/csv" else "json"
            filename = f"{case_id}-{name}-{artifact['artifact_id']}.{extension}"
            raw = read_bytes(directory / "artifacts", artifact)
            (public / filename).write_bytes(raw)
            files.append({"path": "artifacts/" + filename, "sha256": artifact["sha256"]})
        artifact_audit["files"] = files
        financial = {
            "state": saved["payment"]["payment"]["state"],
            "simulated": saved["payment"]["simulated"],
            "authorization_status": order["authorization"]["status"],
            "bookings": order["ledger"],
            "evidence": f"private/{case_id}/checkpoint-{name}.json",
        }
        checkpoint = {
            "id": name,
            "action": action(order),
            "financial": financial,
            "artifact_audit": artifact_audit,
            "requirements": [],
            "complaint": None,
            "binding": order["binding"],
            "attempt": attempt["job"] if attempt else None,
        }
        if label:
            for field, actual, wanted in (
                ("action", checkpoint["action"], label.action),
                ("payment", financial["state"], label.payment_state),
                ("bookings", len(financial["bookings"]), label.booking_count),
                ("artifact", artifact_audit["status"], label.artifact_result),
            ):
                if actual != wanted:
                    result["mismatches"].append(f"{name}:{field}: {actual} != {wanted}")
        semantic = attempt["semantic"] if attempt else None
        if semantic or label and label.complaint_result:
            checkpoint["complaint"] = {
                "meaning": "PASS supports the complaint; FAIL refutes it",
                "raw_model": None,
                "raw_status": "absent_deterministic_only",
                "effective": semantic["result"] if semantic else None,
                "expected": label.complaint_result if label else None,
                "provenance": semantic["provenance"] if semantic else None,
                "citation_audits": audit_refs(semantic, order, output, directory),
            }
            complaint = checkpoint["complaint"]
            if label and complaint["effective"] != label.complaint_result:
                result["mismatches"].append(f"{name}:complaint_result")
            if any(a["status"] != "valid" for a in complaint["citation_audits"]):
                result["unavailable"].append(f"{name}:complaint_citations")
    verification = order.get("verification") if order else None
    # Correction clears current checks. Preserve the actual earlier decision,
    # explicitly labeled historical, rather than inventing current authority.
    checkpoint["finding_scope"] = "current"
    if verification is None and attempt:
        verification = attempt["verification"]
        checkpoint["finding_scope"] = "historical_attempt_before_invalidation"
    checkpoint["finding_binding"] = verification["binding"] if verification else None
    assessments = (
        {a["obligation_id"]: a for a in verification["assessments"]} if verification else {}
    )
    obligations = verification["obligations"] if verification else []
    findings = {o["requirement_id"]: assessments.get(o["obligation_id"]) for o in obligations}
    identities_valid = False
    if order:
        accepted_ids = [
            r["requirement_id"] for r in order["snapshot"]["quote"]["specification"]["requirements"]
        ]
        accepted_valid = set(accepted_ids) == set(REQUIREMENTS) and len(accepted_ids) == len(
            REQUIREMENTS
        )
        findings_valid = (
            len(obligations) == len(REQUIREMENTS)
            and set(findings) == set(REQUIREMENTS)
            and len(assessments) == len(verification["assessments"]) == len(REQUIREMENTS)
            and set(assessments) == {o["obligation_id"] for o in obligations}
        )
        identities_valid = accepted_valid and findings_valid
        if not accepted_valid:
            result["unavailable"].append(f"{name}:accepted_requirement_ID_mismatch")
        if not findings_valid:
            result["unavailable"].append(f"{name}:finding_ID_mismatch")
    by_requirement = {r.requirement_id: r for r in label.requirements} if label else {}
    for requirement_id in REQUIREMENTS:
        finding, wanted = findings.get(requirement_id), by_requirement.get(requirement_id)
        output = attempt["output"] if attempt else None
        if output is None and order and order["deliveries"]:
            output = order["deliveries"][-1]
        audits = audit_refs(finding, order, output, directory)
        audit_status = (
            "valid"
            if audits and all(a["status"] == "valid" for a in audits)
            else "invalid"
            if any(a["status"] == "invalid" for a in audits)
            else "unavailable"
        )
        row = {
            "requirement_id": requirement_id,
            "raw_model": None,
            "raw_status": "absent_deterministic_only",
            "effective": finding["result"] if finding else None,
            "provenance": finding["provenance"] if finding else None,
            "reason_code": finding["reason_code"] if finding else None,
            "expected": wanted.result if wanted else None,
            "rationale": redact(wanted.rationale) if wanted else None,
            "citation_audits": audits,
            "audit_status": audit_status,
            "comparison": "unscored",
        }
        if wanted and finding and identities_valid and audit_status != "unavailable":
            row["comparison"] = (
                "match"
                if finding["result"] == wanted.result and audit_status == "valid"
                else "mismatch"
            )
        if row["comparison"] == "mismatch":
            result["mismatches"].append(
                f"{name}:{requirement_id}: {row['effective']} != {row['expected']} "
                "or invalid citation"
            )
        if row["comparison"] == "unscored":
            result["unavailable"].append(f"{name}:{requirement_id}")
        checkpoint["requirements"].append(row)
    return checkpoint, result


def audit_refs(finding, order, output, directory):
    if not finding or not order:
        return []
    artifacts = {a["artifact_id"]: a for a in order["artifacts"]}
    if output:
        artifacts.update({output[k]["artifact_id"]: output[k] for k in ("csv", "preview")})
    deliveries = [*order["deliveries"], *([output] if output else [])]
    pin = order["snapshot"]["quote"]["specification"]["terms"]["coverage"]["pin"]
    return [
        dict(
            exact_cell(
                directory / "artifacts",
                list(artifacts.values()),
                ref,
                deliveries=deliveries,
                coverage_pin=pin,
            ),
            artifact_id=ref["artifact_id"],
            sha256=ref["sha256"],
            version=ref.get("version"),
            row=ref.get("row"),
            column=ref.get("column"),
        )
        for ref in finding["citations"] + finding["conflicting_evidence"]
    ]


def ratio(numerator, denominator):
    return {
        "numerator": numerator,
        "denominator": denominator,
        "value": numerator / denominator if denominator else None,
    }


def metrics(cases):
    """Unit = requirement at a scheduled checkpoint. Missing observations stay scheduled."""
    groups = {}
    for split in ("development", "held_out"):
        for review in ("engineering", "rehan_reviewed", "missing"):
            selected = [
                c for c in cases if c["classification"] == split and c["review_status"] == review
            ]
            rows = [r for c in selected for p in c["checkpoints"] for r in p["requirements"]]
            labeled = [r for r in rows if r["expected"] is not None]
            groups[f"{split}/{review}"] = {
                "scheduled_cases": len(selected),
                "scheduled_requirement_observations": len(rows),
                "unscored": sum(r["comparison"] == "unscored" for r in rows),
                "agreement": ratio(sum(r["comparison"] == "match" for r in labeled), len(labeled)),
                "false_pass": ratio(
                    sum(r["effective"] == "PASS" and r["expected"] != "PASS" for r in labeled),
                    sum(r["expected"] != "PASS" for r in labeled),
                ),
                "missed_contradiction": ratio(
                    sum(
                        r["effective"] != "CONFLICT" for r in labeled if r["expected"] == "CONFLICT"
                    ),
                    sum(r["expected"] == "CONFLICT" for r in labeled),
                ),
                "appropriate_unknown": ratio(
                    sum(r["comparison"] == "match" for r in labeled if r["expected"] == "UNKNOWN"),
                    sum(r["expected"] == "UNKNOWN" for r in labeled),
                ),
                "appropriate_conflict": ratio(
                    sum(r["comparison"] == "match" for r in labeled if r["expected"] == "CONFLICT"),
                    sum(r["expected"] == "CONFLICT" for r in labeled),
                ),
                "excessive_abstention": ratio(
                    sum(
                        r["effective"] in ("UNKNOWN", "CONFLICT")
                        for r in labeled
                        if r["expected"] in ("PASS", "FAIL")
                    ),
                    sum(r["expected"] in ("PASS", "FAIL") for r in labeled),
                ),
                "raw_model_errors": ratio(0, 0),
                "raw_errors_caught_by_enforcement": ratio(0, 0),
            }
    return groups


def render(report):
    """Stable rendering; only normalized, value-free audit metadata reaches this report."""

    def cell(value):
        return redact(value).replace("|", "\\|").replace("\n", " ") if value is not None else "N/A"

    lines = [
        "# Aggregate evaluation",
        "",
        f"Run: `{report['run_id']}`. Mode: offline mock.",
        f"Revision: `{report['provenance']['revision']}`; dirty: {report['provenance']['dirty']}.",
        f"Frozen plan: `{report['freeze_sha256']}`.",
        f"Evaluation status: **{report['evaluation_status']}**.",
        "",
        f"Scheduled: {len(report['cases'])}; completed: {report['completed']}; "
        f"mismatches: {report['mismatched']}; incomplete: {report['incomplete']}.",
        "Qualification: **not claimed**. Fixture compiler; intake unscored. "
        "Raw model results and provider usage/cost are unavailable. "
        "Structural citation validity does not establish substantive entailment.",
        "",
        "Metric unit: accepted requirement × scheduled checkpoint. Repeated checkpoints are "
        "correlated observations, not additional independent cases. Missing observations remain "
        "in scheduled totals and cannot count as agreement. Zero denominators are N/A.",
        "False PASS denominator: labels other than PASS. Missed contradiction denominator: "
        "CONFLICT labels. Appropriate UNKNOWN/CONFLICT denominators: the corresponding labels. "
        "Excessive abstention denominator: determinate PASS/FAIL labels. All are split by review "
        "status; engineering figures are diagnostics, not independent accuracy. Raw model errors "
        "and errors caught by enforcement are N/A without observed raw candidates.",
        "",
        "| Split / review | Scheduled cases | Requirement observations | Agreement | Unscored |",
        "| --- | ---: | ---: | --- | ---: |",
    ]
    for group, m in report["metrics"].items():
        a = m["agreement"]
        lines.append(
            f"| {group} | {m['scheduled_cases']} | {m['scheduled_requirement_observations']} | "
            f"{a['numerator']}/{a['denominator']} {'(N/A)' if a['value'] is None else ''} "
            f"| {m['unscored']} |"
        )
    lines += ["", "| Split / review | Metric | Numerator / denominator |", "| --- | --- | --- |"]
    for group, group_metrics in report["metrics"].items():
        if not group_metrics["scheduled_cases"]:
            continue
        for key, value in group_metrics.items():
            if isinstance(value, dict) and key != "agreement":
                lines.append(
                    f"| {group} | {key} | {value['numerator']}/{value['denominator']} "
                    f"{'(N/A)' if value['value'] is None else ''} |"
                )
    lines += [
        "",
        "| Case | Classification / review | Outcome | Final action | "
        "Mock financial state / bookings | Operational error |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for case in report["cases"]:
        last = case["checkpoints"][-1]
        money = last["financial"]
        lines.append(
            f"| {case['case_id']} — {cell(case['title'])} | "
            f"{case['classification']} / {case['review_status']} | "
            f"{case['outcome']} | {cell(last['action'])} | "
            f"{money['state'] + ' / ' + str(len(money['bookings'])) if money else 'unavailable'} | "
            f"{cell(case['operation'].get('error'))} |"
        )
    for case in report["cases"]:
        lines += [
            "",
            f"## {case['case_id']} — {cell(case['title'])}",
            "",
            f"Review: {cell(case['review_rationale'])}",
            "",
            "| Checkpoint | Requirement | Raw model | Effective | Expected | "
            "Citation audit | Comparison |",
            "| --- | --- | --- | --- | --- | --- | --- |",
        ]
        for cp in case["checkpoints"]:
            for row in cp["requirements"]:
                lines.append(
                    f"| {cp['id']} | {row['requirement_id']} | absent (deterministic only) | "
                    f"{cell(row['effective'])} | {cell(row['expected'])} | "
                    f"{row['audit_status']} | {row['comparison']} |"
                )
        for cp in case["checkpoints"]:
            lines += [
                "",
                f"**{cp['id']}**: action {cell(cp['action'])}; binding `{cell(cp['binding'])}`.",
                f"Findings: {cp['finding_scope']}; binding `{cell(cp['finding_binding'])}`.",
            ]
            if cp["financial"]:
                money = cp["financial"]
                lines.append(
                    f"Mock payment: {money['state']}; "
                    f"authorization {money['authorization_status']}; "
                    f"observed bookings {len(money['bookings'])}."
                )
                for booking in money["bookings"]:
                    lines.append(f"Observed mock booking: `{cell(booking)}`.")
            if cp["artifact_audit"]:
                audit = cp["artifact_audit"]
                lines.append(f"Artifact audit: {audit['status']} ({audit['reason']}).")
                for artifact in audit["files"]:
                    lines.append(
                        f"[{artifact['path']}]({artifact['path']}) — "
                        f"SHA-256 `{artifact['sha256']}`."
                    )
            if cp["complaint"]:
                claim = cp["complaint"]
                lines.append(
                    f"Complaint finding: raw absent; effective {claim['effective']}; "
                    f"expected {claim['expected']}. PASS supports the complaint; FAIL refutes it. "
                    "This is separate from delivery requirements."
                )
            for row in cp["requirements"]:
                if row["comparison"] != "match":
                    reasons = sorted(
                        {a["reason"] for a in row["citation_audits"] if a["status"] != "valid"}
                    )
                    lines.append(
                        f"{row['requirement_id']}: {cell(row['reason_code'])}; expected basis: "
                        f"{cell(row['rationale'])}; "
                        f"audit issues: {cell(', '.join(reasons) or 'none')}."
                    )
        lines += [
            "",
            "Mismatches: " + cell("; ".join(case["mismatches"]) or "none"),
            "Unavailable: " + cell("; ".join(case["unavailable"]) or "none"),
            "Execution: " + cell(case["operation"]),
        ]
    lines += ["", "## Dependencies and limits", ""]
    lines.extend("- " + cell(item) for item in report["dependencies"] + report["errors"])
    return "\n".join(lines) + "\n"
