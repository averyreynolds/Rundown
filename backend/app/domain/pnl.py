"""Unrealized profit-and-loss for a single holding."""

from dataclasses import dataclass
from decimal import Decimal

from app.domain.types import Holding


@dataclass(frozen=True, slots=True)
class UnrealizedPnl:
    """Unrealized gain/loss for one holding, in both dollars and percent.

    `percent` is `None` when `cost_basis` is zero -- a real brokerage
    data-quality case (e.g. a position transferred in without a recorded
    cost basis) where percent P&L is genuinely undefined, not a
    divide-by-zero crash.
    """

    dollars: Decimal
    percent: Decimal | None


def compute_pnl(holding: Holding) -> UnrealizedPnl:
    """Return unrealized gain/loss in dollars and percent for `holding`."""
    dollars = holding.market_value - holding.cost_basis
    if holding.cost_basis == 0:
        return UnrealizedPnl(dollars=dollars, percent=None)

    percent = (dollars / holding.cost_basis) * Decimal(100)
    return UnrealizedPnl(dollars=dollars, percent=percent)
