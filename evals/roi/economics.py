"""Conditional provider economics. No transaction value or invented measured minutes."""

import math
from collections import defaultdict

from evals.roi.ledger import PROVIDER_ROLES, unique_episodes
from evals.roi.plan import KINDS

ASSUMED_SECONDS = {
    "glossary_lookup_apply": 45,
    "source_coordination": 30,
    "source_explanation": 120,
    "routine_oversight": 10,
    "final_review": 30,
    "finding_review": 30,
    "rework_review": 60,
    "scope_offer_review": 30,
    "exception_review": 120,
    "unnecessary_escalation": 180,
    "qualification_review": 180,
    "procedure_approval": 60,
    "activation_check": 30,
    "contract_consent": 30,
    "funding_consent": 20,
    "delivery_acceptance": 30,
    "objection_submission": 60,
}
PROFILES = {
    "low_repeat": dict(zip(KINDS, (0.10, 0.45, 0.10, 0.15, 0.10, 0.10), strict=True)),
    "medium_repeat": dict(zip(KINDS, (0.40, 0.20, 0.10, 0.10, 0.10, 0.10), strict=True)),
    "high_repeat": dict(zip(KINDS, (0.70, 0.10, 0.05, 0.05, 0.05, 0.05), strict=True)),
}
DEFAULTS = {
    "orders_per_month": 1000,
    "horizon_months": 12,
    "loaded_hourly_cost": 40,
    "incremental_variable_cost_per_order": 0.20,
    "fixed_cost_per_month": 150,
    "setup_cost": 1000,
    "realization_fraction": 0.5,
    "additional_governance_seconds": 0,
    "cost_components": {
        "incremental_inference_per_order": 0.15,
        "compute_per_order": 0.04,
        "storage_per_order": 0.01,
        "incremental_payment_fee_per_order": 0,
        "support_per_month": 120,
        "hosting_per_month": 30,
    },
}


def normalized(weights):
    if not weights or any(not math.isfinite(v) or v < 0 for v in weights.values()):
        raise ValueError("Weights must be finite and nonnegative")
    total = sum(weights.values())
    if total <= 0:
        raise ValueError("At least one positive workload weight is required")
    return {k: v / total for k, v in weights.items()}


def project(
    minutes_saved,
    weights,
    *,
    orders_per_month=1000,
    horizon_months=12,
    loaded_hourly_cost=40,
    incremental_variable_cost_per_order=0.20,
    fixed_cost_per_month=150,
    setup_cost=1000,
    realization_fraction=0.5,
):
    numbers = [
        orders_per_month,
        horizon_months,
        loaded_hourly_cost,
        incremental_variable_cost_per_order,
        fixed_cost_per_month,
        setup_cost,
        realization_fraction,
        *minutes_saved.values(),
    ]
    if any(not math.isfinite(v) for v in numbers) or min(numbers[:3]) <= 0:
        raise ValueError("Positive finite volume, horizon and wage required")
    if min(numbers[3:6]) < 0 or not 0 <= realization_fraction <= 1:
        raise ValueError("Costs must be nonnegative and realization must be within [0, 1]")
    weights = normalized(weights)
    if set(weights) != set(minutes_saved):
        raise ValueError("Every weighted category needs its own observed work/modeled time")
    n = orders_per_month * horizon_months
    mean = sum(weights[k] * minutes_saved[k] for k in weights)
    positive = (
        n * sum(weights[k] * max(0, minutes_saved[k]) for k in weights) / 60 * loaded_hourly_cost
    )
    negative = (
        n * sum(weights[k] * min(0, minutes_saved[k]) for k in weights) / 60 * loaded_hourly_cost
    )
    costs = (
        n * incremental_variable_cost_per_order + fixed_cost_per_month * horizon_months + setup_cost
    )
    recurring_benefit = mean / 60 * loaded_hourly_cost
    margin = (
        orders_per_month * (recurring_benefit - incremental_variable_cost_per_order)
        - fixed_cost_per_month
    )
    cash_margin = (
        (realization_fraction * positive + negative) / horizon_months
        - orders_per_month * incremental_variable_cost_per_order
        - fixed_cost_per_month
    )
    return dict(
        evidence_class="projected",
        weights=weights,
        orders=n,
        mean_net_minutes_saved=mean,
        capacity_hours=n * mean / 60,
        gross_capacity_value=positive + negative,
        positive_capacity_value=positive,
        negative_capacity_value=negative,
        incremental_cost=costs,
        net_capacity_value=positive + negative - costs,
        conditional_cash_impact=realization_fraction * positive + negative - costs,
        cash_at_0_percent=negative - costs,
        cash_at_50_percent=0.5 * positive + negative - costs,
        cash_at_100_percent=positive + negative - costs,
        break_even_seconds=3600 * costs / (n * loaded_hourly_cost),
        cash_break_even_positive_seconds=3600
        * (costs - negative)
        / (n * loaded_hourly_cost * realization_fraction)
        if realization_fraction
        else None,
        recurring_net_per_order=recurring_benefit - incremental_variable_cost_per_order,
        volume_break_even_orders_per_month=(fixed_cost_per_month + setup_cost / horizon_months)
        / (recurring_benefit - incremental_variable_cost_per_order)
        if recurring_benefit > incremental_variable_cost_per_order
        else None,
        months_to_capacity_break_even=math.ceil(setup_cost / margin) if margin > 0 else None,
        months_to_cash_break_even=math.ceil(setup_cost / cash_margin) if cash_margin > 0 else None,
    )


def modeled_minutes(events, cases, *, seconds=None, roles=PROVIDER_ROLES):
    seconds = seconds or ASSUMED_SECONDS
    totals = defaultdict(float)
    for event in unique_episodes(events):
        if event["actor_role"] in roles:
            value = seconds[event["work_type"]]
            if not math.isfinite(value) or value < 0:
                raise ValueError("Assumed attention must be finite and nonnegative")
            totals[(event["arm"], event["case_id"])] += value / 60
    categories = defaultdict(list)
    for case in cases:
        if case["phase"] == "recurring":
            categories[(case["arm"], case["category"])].append(
                totals[(case["arm"], case["case_id"])]
            )
    return {
        f"{arm}:{kind}": sum(values) / len(values) for (arm, kind), values in categories.items()
    }


def assumption_manifest():
    return dict(
        evidence_class="assumed",
        perspective="Provider operational capacity, not sales margin",
        commercial_unit=(
            "Scheduled commercial scenario; expanded scenarios contain "
            "separately counted parent/child orders"
        ),
        defaults=DEFAULTS,
        assumed_active_seconds_by_work_type=ASSUMED_SECONDS,
        workload_profiles=PROFILES,
        setup_accounting=(
            "The setup input is a total allowance including teaching/qualification/"
            "approval labor. Show that labor separately and never add it twice; "
            "reject allowances below the modeled incremental onboarding cost."
        ),
        missing=[
            "Actual active human times",
            "Production inference mix and failures",
            "Metered compute/storage costs",
            "Production payment fees",
            "Operating support load",
            "Empirical case prevalence",
            "Payroll/cash realization",
        ],
        warning=(
            "All defaults are illustrative scenarios, not external benchmarks. "
            "Zero payment-fee assumption is not a measured production fee. Source-owner "
            "and buyer attention are separate, not hidden provider savings."
        ),
    )
