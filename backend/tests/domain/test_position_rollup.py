"""Tests for `app.domain.position_rollup`."""

from decimal import Decimal

import pytest

from app.domain.allocation import InvalidPortfolioValueError, compute_allocation
from app.domain.pnl import compute_pnl
from app.domain.position_rollup import PositionRollup, roll_up_positions
from app.domain.types import Holding

_ELEVEN_POSITIONS = (
    ("AAPL", "7830", "9555"),
    ("MSFT", "6120", "8427.6"),
    ("NVDA", "4400", "8156.5"),
    ("AMZN", "6900", "6933"),
    ("GOOGL", "4250", "4910"),
    ("JPM", "4820", "5378"),
    ("BRK.B", "4550", "4687.5"),
    ("XOM", "4550", "4256"),
    ("VTI", "3450", "3748.8"),
    ("SCHD", "3120", "3368"),
    ("UNH", "3960", "2736.8"),
)


def _holding(symbol: str, cost_basis: str, market_value: str, quantity: str = "10") -> Holding:
    return Holding(
        symbol=symbol,
        quantity=Decimal(quantity),
        cost_basis=Decimal(cost_basis),
        current_price=Decimal(market_value) / Decimal(quantity),
        market_value=Decimal(market_value),
    )


def _eleven_positions() -> list[Holding]:
    return [_holding(symbol, cost, value) for symbol, cost, value in _ELEVEN_POSITIONS]


def _row(rows: list[PositionRollup], symbol: str) -> PositionRollup:
    return next(row for row in rows if row.symbol == symbol)


def _two_places(value: Decimal | None) -> Decimal:
    assert value is not None
    return value.quantize(Decimal("0.01"))


def test_shares_for_synthetic_portfolio_match_known_figures() -> None:
    rollup = roll_up_positions(_eleven_positions())
    nvda = _row(rollup.positions, "NVDA")

    assert _two_places(nvda.share_of_net_gain_pct) == Decimal("45.77")
    assert _two_places(nvda.share_of_cost_pct) == Decimal("8.16")
    assert _two_places(nvda.share_of_value_pct) == Decimal("13.12")


def test_totals_sum_across_positions() -> None:
    rollup = roll_up_positions(_eleven_positions())

    assert rollup.total_market_value == Decimal("62157.2")
    assert rollup.total_cost_basis == Decimal("53950")
    assert rollup.net_gain_dollars == Decimal("8207.2")


def test_shares_each_sum_to_one_hundred() -> None:
    rows = roll_up_positions(_eleven_positions()).positions

    for shares in (
        [row.share_of_value_pct for row in rows],
        [row.share_of_cost_pct for row in rows],
        [row.share_of_net_gain_pct for row in rows],
    ):
        total = sum((share for share in shares if share is not None), start=Decimal(0))
        assert total.quantize(Decimal("0.0001")) == Decimal("100.0000")


def test_losing_position_has_negative_share_of_net_gain() -> None:
    rollup = roll_up_positions(_eleven_positions())

    assert _two_places(_row(rollup.positions, "UNH").share_of_net_gain_pct) == Decimal("-14.90")


def test_rows_are_sorted_by_value_descending_then_symbol() -> None:
    rollup = roll_up_positions(
        [
            _holding("SMALL", "10", "10"),
            _holding("TIEB", "10", "50"),
            _holding("BIG", "10", "100"),
            _holding("TIEA", "10", "50"),
        ]
    )

    assert [row.symbol for row in rollup.positions] == ["BIG", "TIEA", "TIEB", "SMALL"]


def test_symbol_held_in_two_accounts_merges_into_one_row() -> None:
    rollup = roll_up_positions(
        [
            _holding("AAPL", "1000", "1500", quantity="10"),
            _holding("AAPL", "3000", "3000", quantity="20"),
            _holding("MSFT", "500", "500", quantity="5"),
        ]
    )

    assert [row.symbol for row in rollup.positions] == ["AAPL", "MSFT"]
    aapl = rollup.positions[0]
    assert aapl.quantity == Decimal(30)
    assert aapl.market_value == Decimal(4500)
    assert aapl.cost_basis == Decimal(4000)
    assert aapl.gain_dollars == Decimal(500)
    assert aapl.gain_percent == Decimal("12.5")


@pytest.mark.parametrize("market_value", ["1000", "900"])
def test_share_of_net_gain_is_none_when_net_gain_is_not_positive(market_value: str) -> None:
    rollup = roll_up_positions([_holding("AAPL", "1000", market_value)])

    assert rollup.net_gain_dollars <= 0
    assert rollup.positions[0].share_of_net_gain_pct is None


def test_zero_cost_position_has_no_percent_since_cost() -> None:
    rollup = roll_up_positions([_holding("AAPL", "0", "500"), _holding("MSFT", "100", "100")])

    aapl = _row(rollup.positions, "AAPL")
    assert aapl.gain_percent is None
    assert aapl.gain_dollars == Decimal(500)


def test_merge_with_a_zero_cost_lot_has_no_percent_since_cost() -> None:
    """A lot with no recorded basis would otherwise inflate the merged percent."""
    rollup = roll_up_positions([_holding("AAPL", "0", "500"), _holding("AAPL", "100", "100")])

    aapl = rollup.positions[0]
    assert aapl.cost_basis == Decimal(100)
    assert aapl.gain_percent is None


def test_all_zero_cost_has_no_share_of_cost() -> None:
    rollup = roll_up_positions([_holding("AAPL", "0", "500")])

    assert rollup.total_cost_basis == 0
    assert rollup.positions[0].share_of_cost_pct is None


def test_empty_positions_returns_empty_rollup_with_zero_totals() -> None:
    rollup = roll_up_positions([])

    assert rollup.positions == []
    assert rollup.total_market_value == 0
    assert rollup.total_cost_basis == 0
    assert rollup.net_gain_dollars == 0


def test_non_positive_total_value_raises_like_compute_allocation() -> None:
    with pytest.raises(InvalidPortfolioValueError):
        roll_up_positions([_holding("AAPL", "100", "0")])


def test_figures_match_per_holding_math_for_a_single_account() -> None:
    """The map and the holdings list must never disagree."""
    holdings = _eleven_positions()
    rows = roll_up_positions(holdings).positions
    allocations = {a.symbol: a.percent for a in compute_allocation(holdings)}

    for holding in holdings:
        row = _row(rows, holding.symbol)
        pnl = compute_pnl(holding)
        assert row.gain_dollars == pnl.dollars
        assert row.gain_percent == pnl.percent
        assert row.share_of_value_pct == allocations[holding.symbol]
