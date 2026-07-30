"""Tests for `app.domain.concentration`."""

from decimal import Decimal

import pytest

from app.domain.allocation import Allocation
from app.domain.concentration import flag_concentrated, top_n_by_weight


def test_flags_holdings_above_threshold() -> None:
    allocations = [
        Allocation(symbol="AAPL", percent=Decimal(50)),
        Allocation(symbol="MSFT", percent=Decimal(30)),
        Allocation(symbol="GOOG", percent=Decimal(20)),
    ]

    flagged = flag_concentrated(allocations, threshold_pct=Decimal(25))

    assert flagged == [
        Allocation(symbol="AAPL", percent=Decimal(50)),
        Allocation(symbol="MSFT", percent=Decimal(30)),
    ]


def test_none_flagged_when_all_holdings_under_threshold() -> None:
    allocations = [Allocation(symbol="AAPL", percent=Decimal(10))]

    assert flag_concentrated(allocations, threshold_pct=Decimal(20)) == []


def test_flag_concentrated_on_empty_allocations_returns_empty() -> None:
    assert flag_concentrated([], threshold_pct=Decimal(20)) == []


def test_threshold_is_exclusive_not_inclusive() -> None:
    """A holding exactly at the threshold is not flagged as *above* it."""
    allocations = [Allocation(symbol="AAPL", percent=Decimal(20))]

    assert flag_concentrated(allocations, threshold_pct=Decimal(20)) == []


def test_top_n_by_weight_returns_descending_order() -> None:
    allocations = [
        Allocation(symbol="GOOG", percent=Decimal(20)),
        Allocation(symbol="AAPL", percent=Decimal(50)),
        Allocation(symbol="MSFT", percent=Decimal(30)),
    ]

    top_two = top_n_by_weight(allocations, n=2)

    assert top_two == [
        Allocation(symbol="AAPL", percent=Decimal(50)),
        Allocation(symbol="MSFT", percent=Decimal(30)),
    ]


def test_top_n_exceeding_length_returns_every_allocation() -> None:
    allocations = [Allocation(symbol="AAPL", percent=Decimal(100))]

    assert top_n_by_weight(allocations, n=5) == allocations


def test_top_n_negative_raises_value_error() -> None:
    with pytest.raises(ValueError, match="non-negative"):
        top_n_by_weight([Allocation(symbol="AAPL", percent=Decimal(100))], n=-1)
