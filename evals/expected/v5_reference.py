"""Offline reference endpoints. Never imported by backend/app or sent to a model."""


def reference_endpoints(development, transfer):
    # Reference worlds intentionally vary source facts, accepted semantics and customer choice.
    # These endpoints are defined independently of the runtime validator's returned result.
    development_endpoints = (
        "PASS",
        "FAIL",
        "UNKNOWN",
        "PASS",
        "UNKNOWN",
        "PASS",
        "FAIL",
        "FAIL",
        "FAIL",
        "FAIL",
        "UNKNOWN",
        "DECLINED",
    )
    transfer_endpoints = ("PASS", "FAIL", "UNKNOWN", "FAIL", "PASS", "PASS")
    if len(development) != len(development_endpoints) or len(transfer) != len(transfer_endpoints):
        raise ValueError("Reference manifest changed without independent endpoint review")
    return {
        case.case_id: {
            "outcome": endpoint,
            "base_bookings": int(endpoint == "PASS"),
            "accepted": endpoint != "DECLINED",
        }
        for cases, endpoints in (
            (development, development_endpoints),
            (transfer, transfer_endpoints),
        )
        for case, endpoint in zip(cases, endpoints, strict=True)
    }


def score(outcomes, reference):
    mismatches = []
    totals = {
        arm: {
            "cases": 0,
            "correct_endpoint": 0,
            "correct_financial_effect": 0,
            "accepted": 0,
            "closed_without_staff_resolution": 0,
        }
        for arm in ("static", "memory_only", "evolving_process")
    }
    for comparison in outcomes:
        truth = reference[comparison["case_id"]]
        for arm, run in comparison["arms"].items():
            totals[arm]["cases"] += 1
            totals[arm]["correct_endpoint"] += run["outcome"] == truth["outcome"]
            totals[arm]["correct_financial_effect"] += (
                run["financial_effects"] == truth["base_bookings"]
            )
            totals[arm]["accepted"] += run["accepted"]
            totals[arm]["closed_without_staff_resolution"] += run.get("order_state") == "closed"
            if (
                run["outcome"] != truth["outcome"]
                or run["financial_effects"] != truth["base_bookings"]
                or run["accepted"] != truth["accepted"]
            ):
                mismatches.append(
                    {
                        "case_id": comparison["case_id"],
                        "arm": arm,
                        "observed": run["outcome"],
                        "reference": truth,
                        "financial_effects": run["financial_effects"],
                        "accepted": run["accepted"],
                    }
                )
    return {"totals": totals, "mismatches": mismatches}
