"""Exact presentation conversion. Financial authority stays in integer minor units."""

from decimal import Decimal


def major_units(amount_minor: int, decimals: int = 2) -> Decimal:
    if type(amount_minor) is not int or type(decimals) is not int or not 0 <= decimals <= 18:
        raise ValueError("integer minor units and a supported decimal scale are required")
    return Decimal(amount_minor).scaleb(-decimals)


def format_money(amount) -> str:
    return f"{major_units(amount.amount_minor, amount.decimals):.{amount.decimals}f}"
