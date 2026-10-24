"""Offline oracle only. No production verifier, producer, disposition or runtime imports."""

import argparse
import base64
import csv
import hashlib
import io
import json
import re
from decimal import Decimal
from pathlib import Path

import pdfplumber


def inspect_pdf(raw):
    with pdfplumber.open(io.BytesIO(raw)) as pdf:
        pages = [page.extract_text() or "" for page in pdf.pages]
    lines = [line for page in pages for line in page.splitlines()
             if line not in ("Cited product shortlist", "CALHACKS / SYNTHETIC CATALOG DEMO / NO LIVE PAYMENTS")
             and not re.fullmatch(r"Source citations refer to immutable registered artifacts\. \d+", line)]
    selected, excluded, index = [], [], 0
    while index < len(lines):
        identity = re.fullmatch(r"SELECT (S\d+) \| (.+) \| (\S+)", lines[index])
        exclusion = re.fullmatch(r"EXCLUDED (S\d+) \| (weight|price|category)", lines[index])
        if exclusion:
            excluded.append({"product_id": exclusion[1], "reason": exclusion[2]})
            index += 1
            continue
        if not identity or index + 2 >= len(lines):
            raise ValueError("Unknown or incomplete actual PDF record")
        numbers = re.fullmatch(r"(net_unit|shipping)=(\S+) kg \| unit=USD (\S+)", lines[index + 1])
        citation = re.fullmatch(r"source=(\S+)@(\d+) p(\d+) sha=([0-9a-f]{12})", lines[index + 2])
        if not numbers or not citation:
            raise ValueError("Product identity not followed by its values and citation")
        selected.append({"product_id": identity[1], "name": identity[2], "supplier_id": identity[3],
                         "concept": numbers[1], "weight_kg": Decimal(numbers[2]), "price_USD": Decimal(numbers[3]),
                         "source_id": citation[1], "source_version": int(citation[2]),
                         "source_page": int(citation[3]), "source_sha12": citation[4]})
        index += 3
    ids = [r["product_id"] for r in selected + excluded]
    if len(set(ids)) != len(ids):
        raise ValueError("Duplicated product in actual PDF")
    return selected, excluded


def independently_correct_pdf(raw, oracle):
    actual, excluded = inspect_pdf(raw)
    expected = []
    for record in oracle["expected_records"]:
        expected.append({**{k: v for k, v in record.items() if k != "source_sha256"},
                         "weight_kg": Decimal(record["weight_kg"]), "price_USD": Decimal(record["price_USD"]),
                         "source_sha12": record["source_sha256"][:12]})
    expected_excluded = [{"product_id": row["product_id"], "reason": "weight" if not row["weight_ok"] else "price"}
                         for row in oracle["reference_arithmetic"] if not row["included"]]
    key = lambda record: record["product_id"]
    return sorted(actual, key=key) == sorted(expected, key=key) and sorted(excluded, key=key) == sorted(expected_excluded, key=key)


def grade(case, oracle, result, proposal):
    issues = []
    order, payment = result["order"]["order"], result["order"]["payment"]
    snapshot = order["snapshot"]
    policy = snapshot["quote"]["policy"]
    terms = snapshot["quote"]["specification"]["terms"]
    def require(condition, reason):
        if not condition:
            issues.append(reason)
    require(policy["version"] == "catalog-v0.3" and policy["review_seconds"] == 60, "accepted_policy_changed")
    require(terms["corpus_id"] == case["corpus_id"], "accepted_scope_changed")
    shipping = "shipping weight at most 2500 g" in case["prompt"]
    require(terms["weight_concept"] == ("shipping" if shipping else "net_unit"), "accepted_weight_concept_wrong")
    require(Decimal(terms["weight_threshold"]) == Decimal("2500" if shipping else "2"), "accepted_weight_threshold_wrong")
    require(terms["weight_unit"] == ("g" if shipping else "kg") and terms["weight_operator"] == ("lte" if shipping else "lt"), "accepted_weight_operator_or_unit_wrong")
    require(Decimal(terms["price_threshold"]) == Decimal("33.50" if shipping else "40") and terms["price_operator"] == ("lt" if shipping else "lte"), "accepted_price_wrong")
    require(snapshot["quote"]["amount"] == {"amount_minor": 1500, "currency": "USD", "decimals": 2}, "price_changed")
    require(payment["simulated"] and payment["payment"]["terms"]["mode"] == "mock" and payment["payment"]["terms"]["amount_atomic"] == "15000000", "wrong_financial_mode_or_amount")
    events = result["events"]
    require(bool(events) and all(e["order"]["snapshot"] == snapshot for e in events), "snapshot_not_preserved_in_trace")
    require(len({e["accepted_snapshot_sha256"] for e in events}) == 1, "accepted_hash_changed")
    require(not result["violations"], "runtime_trace_violations")
    require(all(not stage.get("ledger_count") for stage in result["stages"] if stage["stage"] == "work"), "capture_before_review")
    expected_pin = result["arm"] == "evolving_process" and case["corpus_id"] == proposal["corpus_id"] and not case["historical_procedure"]
    require(all((e["procedure_version"] != "catalog-static-v1") == expected_pin for e in events), "procedure_scope_or_historical_pin_wrong")
    capture = oracle["authored_oracle"]["finance_profile"] == "C"
    pdf_ok = None
    if capture:
        require(result["order_state"] == "closed" and result["payment_state"] == "captured", "expected_correct_completion_not_observed")
        require(result["financial_effects"] == ["capture"] and len(order["ledger"]) == 1, "wrong_terminal_financial_effect")
        require(result["pending_company_obligations"] == 0, "successful_order_has_pending_obligation")
        require(result["verified_compliant"] and result["operationally_closed"], "completion_flags_not_supported")
        require(bool(order["deliveries"]), "missing_actual_delivery")
        if order["deliveries"]:
            delivery = order["deliveries"][-1]
            raw = base64.b64decode(result["artifact_bytes_by_sha256"][delivery["pdf"]["sha256"]])
            require(hashlib.sha256(raw).hexdigest() == delivery["pdf"]["sha256"], "delivery_hash_mismatch")
            try:
                pdf_ok = independently_correct_pdf(raw, oracle)
            except (ValueError, KeyError, ArithmeticError):
                pdf_ok = False
            require(pdf_ok, "independent_actual_pdf_disagrees_with_source_oracle")
        expected_source = oracle["expected_records"][0]
        require(len(order["sources"]) == 1 and order["sources"][0]["artifact"]["sha256"] == expected_source["source_sha256"]
                and order["sources"][0]["version"] == expected_source["source_version"], "final_source_not_oracle_bound")
        for entry in order["ledger"]:
            require(entry["receipt"]["mode"] == "mock" and entry["receipt"]["transaction_id"] is None, "fabricated_live_payment")
            require(entry["binding"] == order["binding"], "capture_has_stale_binding")
    else:
        require(result["order_state"] == "human_review" and result["payment_state"] == "funded", "necessary_hold_not_preserved")
        require(not result["financial_effects"] and not order["ledger"], "money_moved_on_unresolved_evidence")
        require(not order["deliveries"] and not result["verified_compliant"], "unresolved_work_reported_compliant")
        require(result["pending_company_obligations"] > 0 and bool(result["pending_obligation_details"]), "necessary_hold_has_no_owned_pending_task")
    faulty = case.get("provider_output_base64")
    require(result["seller_rework_attempts"] == (1 if faulty else 0), "wrong_free_correction_count")
    if faulty:
        raw = base64.b64decode(faulty)
        bad_hash = hashlib.sha256(raw).hexdigest()
        require(bad_hash in result["artifact_bytes_by_sha256"], "failed_provider_bytes_not_retained")
        history = order["verification_history"] + ([order["verification"]] if order["verification"] else [])
        require(any(r["provider_defect"] and any(a["obligation_id"] == "global:pdf" and a["result"] == "FAIL" for a in r["assessments"]) for r in history), "actual_pdf_failure_not_archived")
        require(result["provider_defect_observed"], "provider_defect_omitted_from_measurement")
        require(not independently_correct_pdf(raw, oracle), "fault_fixture_did_not_establish_independent_failure")
    auto = sum(a["actor"] == "system:registered-evidence-acquisition" for a in order["amendments"])
    staff = sum(a["actor"] == "provider:synthetic-evidence-staff" for a in order["amendments"])
    require(staff == result["company_actions"]["manual_evidence_acquisition"], "staff_action_count_not_trace_grounded")
    if result["arm"] == "functional_memory":
        for trace in result["memory_decisions"]:
            require(trace["mode"] == "real_application_model" and trace["model"] == "claude-opus-5-5", "memory_not_real_selected_model")
            require("scoped_incident_experiences" in trace["context"], "memory_missing_actual_context")
            require(all(e["corpus_id"] == case["corpus_id"] for e in trace["context"]["scoped_incident_experiences"]), "memory_crossed_scope")
    return {"case_id": case["id"], "arm": result["arm"], "family": oracle["family"], "correct": not issues,
            "issues": issues, "independent_pdf_correct": pdf_ok, "automatic_acquisitions": auto,
            **{key: result[key] for key in ("incoming", "accepted", "funded", "delivered", "verified_compliant", "repair_completed", "order_state", "payment_state", "operationally_closed", "pending_company_obligations", "seller_rework_attempts", "customer_answers", "company_actions")}}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--capsule", type=Path, required=True)
    parser.add_argument("--runs", type=Path, required=True)
    parser.add_argument("--oracle", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    capsule = json.loads(args.capsule.read_text())
    if hashlib.sha256(args.oracle.read_bytes()).hexdigest() != capsule["oracle_sha256"]:
        raise SystemExit("Frozen oracle hash changed")
    if hashlib.sha256(Path(__file__).read_bytes()).hexdigest() != capsule["grader_sha256"]:
        raise SystemExit("Grader changed after freeze")
    root = args.capsule.parent
    cases = json.loads((root / "visible-cases.json").read_text())
    proposal = json.loads((root / "selected-proposal.json").read_text())
    gold = {r["case_id"]: r for r in json.loads(args.oracle.read_text())}
    args.output.mkdir(parents=True, exist_ok=False)
    rows = []
    for case in cases:
        for arm in capsule["arms"]:
            result_path = args.runs / case["id"] / arm / "result.json"
            if result_path.exists():
                rows.append(grade(case, gold[case["id"]], json.loads(result_path.read_text()), proposal))
            else:
                rows.append({"case_id": case["id"], "arm": arm, "family": gold[case["id"]]["family"], "correct": False,
                             "incoming": True, "issues": ["missing_final_run_result_retained_in_denominator"]})
    summary = {}
    for arm in capsule["arms"]:
        selected = [r for r in rows if r["arm"] == arm]
        summary[arm] = {"incoming": len(selected), "correct": sum(r["correct"] for r in selected),
                        "accepted": sum(bool(r.get("accepted")) for r in selected),
                        "operationally_closed": sum(bool(r.get("operationally_closed")) for r in selected),
                        "held": sum(r.get("order_state") == "human_review" for r in selected),
                        "manual_evidence_acquisition": sum(r.get("company_actions", {}).get("manual_evidence_acquisition", 0) for r in selected),
                        "pending_obligations": sum(r.get("pending_company_obligations", 0) for r in selected),
                        "missing_run_results": sum("company_actions" not in r for r in selected)}
    strict_reduction = summary["evolving_process"]["manual_evidence_acquisition"] < summary["competent_static"]["manual_evidence_acquisition"]
    all_correct = all(r["correct"] for r in rows)
    nonincreasing_pending = summary["evolving_process"]["pending_obligations"] <= summary["competent_static"]["pending_obligations"]
    other_categories_known_nonincreasing = all(
        all(candidate.get("company_actions", {}).get(category) is not None
            and baseline.get("company_actions", {}).get(category) is not None
            and candidate["company_actions"][category] <= baseline["company_actions"][category]
            for category in ("manual_intake_clarification", "case_review_decision", "financial_reconciliation", "maintenance"))
        for case in cases
        for candidate in rows if candidate["case_id"] == case["id"] and candidate["arm"] == "evolving_process"
        for baseline in rows if baseline["case_id"] == case["id"] and baseline["arm"] == "competent_static"
    )
    report = {"rows": rows, "summary": summary, "all_independently_correct": all_correct,
              "strict_recurring_primary_reduction_vs_competent_static": strict_reduction,
              "operating_benefit_qualified": strict_reduction and all_correct and nonincreasing_pending and other_categories_known_nonincreasing,
              "benefit_limit": "Requires strict reduction versus strongest baseline, no other-category regression, no increased pending work, and measured rather than assumed overhead. Unmeasured labor/maintenance prevent payroll claims.",
              "human_audited": False, "mode": "Independent offline Decimal/source-record oracle / actual PDF bytes / structured synthetic interaction / mock finance"}
    (args.output / "score.json").write_text(json.dumps(report, indent=2))
    fields = ["case_id", "arm", "family", "correct", "incoming", "accepted", "funded", "delivered", "verified_compliant", "repair_completed", "order_state", "payment_state", "operationally_closed", "pending_company_obligations", "seller_rework_attempts", "customer_answers", "automatic_acquisitions", "company_actions", "issues"]
    with (args.output / "metrics.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows({k: json.dumps(v) if isinstance(v, (list, dict)) else v for k, v in row.items()} for row in rows)
    print(json.dumps({"summary": summary, "all_independently_correct": report["all_independently_correct"],
                      "strict_recurring_primary_reduction": strict_reduction}, indent=2))


if __name__ == "__main__":
    main()
