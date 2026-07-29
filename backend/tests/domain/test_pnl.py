"""Tests for `app.domain.pnl`."""

from decimal import Decimal

from app.domain.pnl import UnrealizedPnl, compute_pnl
from app.domain.types import Holding


def _holding(cost_basis: str, market_value: str) -> Holding:
    return Holding(
        symbol="AAPL",
        quantity=Decimal("10"),
        cost_basis=Decimal(cost_basis),
        current_price=Decimal(market_value) / Decimal("10"),
        market_value=Decimal(market_value),
    )


def test_gaining_position_has_positive_signed_gain() -> None:
    pnl = compute_pnl(_holding(cost_basis="1000", market_value="1500"))

    assert pnl == UnrealizedPnl(dollars=Decimal(500), percent=Decimal(50))


def test_losing_position_has_negative_signed_loss() -> None:
    pnl = compute_pnl(_holding(cost_basis="1000", market_value="800"))

    assert pnl == UnrealizedPnl(dollars=Decimal(-200), percent=Decimal(-20))


def test_zero_cost_basis_yields_none_percent_not_a_crash() -> None:
    pnl = compute_pnl(_holding(cost_basis="0", market_value="500"))

    assert pnl.dollars == Decimal(500)
    assert pnl.percent is None


def test_break_even_position_has_zero_gain() -> None:
    pnl = compute_pnl(_holding(cost_basis="1000", market_value="1000"))

    assert pnl == UnrealizedPnl(dollars=Decimal(0), percent=Decimal(0))
