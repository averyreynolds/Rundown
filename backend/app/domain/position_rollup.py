"""Per-symbol portfolio rollup: merged positions and their shares of the whole.

The one source for "how much of my value, cost, or gain is this symbol?", so
the portfolio map and the advisor can't disagree. Row math goes through
`compute_pnl` and `compute_allocation` for the same reason: a symbol held in
one account gets exactly the figures `/portfolio/positions` reports.
"""

from collections.abc import Sequence
from dataclasses import dataclass, replace
from decimal import Decimal

from app.domain.allocation import compute_allocation
from app.domain.pnl import compute_pnl
from app.domain.types import Holding


@dataclass(frozen=True, slots=True)
class PositionRollup:
    """One symbol's totals across every account holding it.

    `gain_percent` is `None` when any merged lot has zero cost basis: its
    gain is unknown rather than 100%, so a percent over the remaining lots
    would be overstated.

    `share_of_net_gain_pct` is negative for a losing position, and `None`
    when the portfolio's net gain isn't positive, where a share of it has no
    meaningful reading. `share_of_cost_pct` is `None` when total cost is zero.
    """

    symbol: str
    quantity: Decimal
    market_value: Decimal
    cost_basis: Decimal
    gain_dollars: Decimal
    gain_percent: Decimal | None
    share_of_value_pct: Decimal
    share_of_cost_pct: Decimal | None
    share_of_net_gain_pct: Decimal | None


@dataclass(frozen=True, slots=True)
class PortfolioRollup:
    """Every symbol's rollup, largest value first, plus portfolio totals."""

    positions: list[PositionRollup]
    total_market_value: Decimal
    total_cost_basis: Decimal
    net_gain_dollars: Decimal


def _merge_lots(lots: Sequence[Holding]) -> Holding:
    """Sum one symbol's lots. `current_price` stays the first lot's, since it isn't summable."""
    return replace(
        lots[0],
        quantity=sum((lot.quantity for lot in lots), start=Decimal(0)),
        cost_basis=sum((lot.cost_basis for lot in lots), start=Decimal(0)),
        market_value=sum((lot.market_value for lot in lots), start=Decimal(0)),
    )


def _percent_of(part: Decimal, whole: Decimal) -> Decimal | None:
    return (part / whole) * Decimal(100) if whole > 0 else None


def roll_up_positions(holdings: Sequence[Holding]) -> PortfolioRollup:
    """Merge `holdings` by symbol and compute each symbol's shares of the portfolio.

    Args:
        holdings: The portfolio's holdings, possibly several per symbol. An
            empty sequence is a legitimate "no positions yet" case.

    Returns:
        One row per symbol, sorted by market value descending, then symbol.

    Raises:
        InvalidPortfolioValueError: if `holdings` is non-empty but the total
            market value is zero or negative (see `compute_allocation`).
    """
    lots_by_symbol: dict[str, list[Holding]] = {}
    for holding in holdings:
        lots_by_symbol.setdefault(holding.symbol, []).append(holding)

    merged = sorted(
        (_merge_lots(lots) for lots in lots_by_symbol.values()),
        key=lambda holding: (-holding.market_value, holding.symbol),
    )
    allocations = compute_allocation(merged)

    total_value = sum((h.market_value for h in merged), start=Decimal(0))
    total_cost = sum((h.cost_basis for h in merged), start=Decimal(0))
    net_gain = total_value - total_cost

    positions = []
    for holding, allocation in zip(merged, allocations, strict=True):
        pnl = compute_pnl(holding)
        has_unknown_basis = any(lot.cost_basis == 0 for lot in lots_by_symbol[holding.symbol])
        positions.append(
            PositionRollup(
                symbol=holding.symbol,
                quantity=holding.quantity,
                market_value=holding.market_value,
                cost_basis=holding.cost_basis,
                gain_dollars=pnl.dollars,
                gain_percent=None if has_unknown_basis else pnl.percent,
                share_of_value_pct=allocation.percent,
                share_of_cost_pct=_percent_of(holding.cost_basis, total_cost),
                share_of_net_gain_pct=_percent_of(pnl.dollars, net_gain),
            )
        )

    return PortfolioRollup(
        positions=positions,
        total_market_value=total_value,
        total_cost_basis=total_cost,
        net_gain_dollars=net_gain,
    )
