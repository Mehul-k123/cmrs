"""Decimal helpers. Every monetary calculation in the codebase goes through these."""

from collections.abc import Iterable
from decimal import ROUND_HALF_UP, Decimal

PAISA = Decimal("0.01")
ZERO = Decimal("0.00")


def to_money(value) -> Decimal:
    """Convert int/str/Decimal to a 2-dp Decimal. Floats are rejected to avoid binary rounding errors."""
    if isinstance(value, float):
        raise TypeError("Floats are not allowed for monetary values; pass str or Decimal")
    if value is None:
        return ZERO
    return Decimal(value).quantize(PAISA, rounding=ROUND_HALF_UP)


def money_sum(values: Iterable) -> Decimal:
    return to_money(sum((to_money(v) for v in values), ZERO))
