"""Reserved product-visible transfer inputs. No endpoint labels or grading metadata."""

import hashlib

from app.improvement.probes import base_answers, base_source, visible_case


def transfer_cases():
    cases = []
    settings = [
        ("North Harbour", "NH", "GBP_per_household", "2026-10-22T00:00:00Z", 7),
        ("East Lake", "EL", "USD_per_household", "2026-09-01T00:00:00Z", 14),
        ("South Ward", "SW", "EUR_per_household", "2026-10-20T00:00:00Z", 10),
        ("Coast County", "CC", "USD_per_household", "2026-10-19T00:00:00Z", 20),
        ("Inland Metro", "IM", "CAD_per_household", "2026-10-17T06:00:00Z", 7),
        ("River District", "RD", "GBP_per_household", "2026-10-21T00:00:00Z", 5),
    ]
    for index, (geography, code, unit, observed_at, limit) in enumerate(settings):
        source = base_source()
        source.update(
            source_id=f"aggregate-{code.casefold()}",
            geography=geography,
            boundary_version="2025-revision-2",
            reference_period="2026-09",
            metric_unit=unit,
        )
        source["rows"] = [
            dict(
                entity_id=f"{code}-district-{number}",
                region_id=f"{code}-{number}",
                value=float(55000 + index * 7000 + number * 2000),
                observed_at=observed_at,
            )
            for number in (1, 2)
        ]
        answers = {
            **base_answers(),
            "geography": geography,
            "boundary_version": source["boundary_version"],
            "reference_period": source["reference_period"],
            "metric_unit": unit,
            "coverage_ids": [row["entity_id"] for row in source["rows"]],
            "region_ids": [row["region_id"] for row in source["rows"]],
            "max_age_days": limit,
        }
        if index == 2:
            source["published_at"] = None
            answers["freshness_basis"] = "published_at"
        if index == 3:
            source["metric_name"] = "mean_individual_income"
        case = visible_case(
            100 + index,
            sources=[source],
            answers=answers,
            intent=f"Recent district-level median household income for {geography}.",
            customer_id="other" if index == 5 else "northwind",
        )
        cases.append(
            case.model_copy(
                update={
                    "case_id": "case-"
                    + hashlib.sha256(f"reserved-{index}".encode()).hexdigest()[:12]
                }
            )
        )
    return tuple(cases)
