"""Tests for `app.domain.allocation`."""

from decimal import Decimal

import pytest

from app.domain.allocation import Allocation, InvalidPortfolioValueError, compute_allocation
from app.domain.types import Holding


def _holding(symbol: str, market_value: str) -> Holding:
    """Build a `Holding` where only `market_value` matters for these tests."""
    return Holding(
        symbol=symbol,
        quantity=Decimal("1"),
        cost_basis=Decimal("1"),
        current_price=Decimal(market_value),
        market_value=Decimal(market_value),
    )


def test_three_holdings_allocation_percentages_sum_to_100() -> None:
    holdings = [
        _holding("AAPL", "5000"),
        _holding("MSFT", "3000"),
        _holding("GOOG", "2000"),
    ]

    allocations = compute_allocation(holdings)

    assert sum((a.percent for a in allocations), Decimal(0)) == Decimal(100)
    assert allocations == [
        Allocation(symbol="AAPL", percent=Decimal(50)),
        Allocation(symbol="MSFT", percent=Decimal(30)),
        Allocation(symbol="GOOG", percent=Decimal(20)),
    ]


def test_single_holding_is_100_percent_allocated() -> None:
    allocations = compute_allocation([_holding("AAPL", "1000")])

    assert allocations == [Allocation(symbol="AAPL", percent=Decimal(100))]


def test_empty_holdings_returns_empty_allocation_not_an_error() -> None:
    assert compute_allocation([]) == []


def test_duplicate_symbols_are_not_collapsed() -> None:
    """Same symbol across two accounts stays two entries, not one merged one."""
    holdings = [_holding("AAPL", "1000"), _holding("AAPL", "1000")]

    allocations = compute_allocation(holdings)

    assert len(allocations) == 2
    assert all(a.percent == Decimal(50) for a in allocations)


def test_zero_total_portfolio_value_raises_invalid_portfolio_value_error() -> None:
    holdings = [_holding("AAPL", "0"), _holding("MSFT", "0")]

    with pytest.raises(InvalidPortfolioValueError):
        compute_allocation(holdings)


def test_negative_total_portfolio_value_raises_invalid_portfolio_value_error() -> None:
    holdings = [_holding("AAPL", "-100")]

    with pytest.raises(InvalidPortfolioValueError):
        compute_allocation(holdings)
