"""Portfolio allocation: each holding's share of total portfolio value."""

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal

from app.domain.types import Holding


class InvalidPortfolioValueError(ValueError):
    """Raised when total portfolio market value is zero or negative.

    A non-empty `holdings` list with a zero/negative total is a
    data-quality anomaly (e.g. a malformed broker response), not a
    legitimate empty portfolio -- an empty `holdings` list is a separate,
    valid case handled without raising.
    """


@dataclass(frozen=True, slots=True)
class Allocation:
    """One holding's share of total portfolio market value.

    Returned as a list rather than a `dict[str, Decimal]` keyed by symbol
    so that holdings sharing a symbol (e.g. the same stock held across
    multiple brokerage accounts) are never silently collapsed into one
    entry -- callers that need per-symbol aggregation are expected to
    aggregate `Holding`s before calling `compute_allocation`, not have this
    function do it implicitly.
    """

    symbol: str
    percent: Decimal


def compute_allocation(holdings: Sequence[Holding]) -> list[Allocation]:
    """Return each holding's percent (0-100) of total portfolio market value.

    Args:
        holdings: The portfolio's current holdings. An empty sequence is a
            legitimate "no positions yet" case.

    Returns:
        One `Allocation` per input holding, in input order. Percentages
        sum to 100 (within `Decimal` rounding) across all holdings. Empty
        if `holdings` is empty.

    Raises:
        InvalidPortfolioValueError: if `holdings` is non-empty but the
            total market value is zero or negative.
    """
    if not holdings:
        return []

    total_value = sum((h.market_value for h in holdings), start=Decimal(0))
    if total_value <= 0:
        raise InvalidPortfolioValueError(
            f"Total portfolio market value must be positive to compute "
            f"allocation, got {total_value}."
        )

    return [
        Allocation(symbol=h.symbol, percent=(h.market_value / total_value) * Decimal(100))
        for h in holdings
    ]
