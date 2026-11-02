"""Tests for `app.domain.price_windows`."""

from datetime import date, timedelta
from decimal import Decimal

from app.domain.price_windows import PriceWindow, WindowChange, compute_window_change, slice_window
from app.domain.types import PricePoint

_TODAY = date(2024, 6, 15)


def _series(*closes_from_today: tuple[int, str]) -> list[PricePoint]:
    """Build a chronologically-ordered series from `(days_before_today, close)` pairs,
    given oldest-first (so callers list the most-in-the-past point first)."""
    return [
        PricePoint(date=_TODAY - timedelta(days=d), close=Decimal(c)) for d, c in closes_from_today
    ]


def test_slice_window_empty_series_returns_empty() -> None:
    assert slice_window([], PriceWindow.ONE_MONTH, today=_TODAY) == []


def test_slice_one_day_returns_last_two_points_regardless_of_gap() -> None:
    # A Friday close followed by a Monday close -- a 3-calendar-day gap.
    points = _series((3, "100"), (0, "110"))

    sliced = slice_window(points, PriceWindow.ONE_DAY, today=_TODAY)

    assert [p.close for p in sliced] == [Decimal("100"), Decimal("110")]


def test_slice_one_day_with_single_point_returns_that_point() -> None:
    points = _series((0, "100"))

    assert slice_window(points, PriceWindow.ONE_DAY, today=_TODAY) == points


def test_slice_one_week_excludes_points_older_than_seven_days() -> None:
    points = _series((10, "90"), (5, "95"), (1, "100"))

    sliced = slice_window(points, PriceWindow.ONE_WEEK, today=_TODAY)

    assert [p.close for p in sliced] == [Decimal("95"), Decimal("100")]


def test_slice_ytd_uses_january_first_of_todays_year() -> None:
    points = [
        PricePoint(date=date(2023, 12, 20), close=Decimal("80")),
        PricePoint(date=date(2024, 1, 1), close=Decimal("90")),
        PricePoint(date=date(2024, 3, 1), close=Decimal("100")),
    ]

    sliced = slice_window(points, PriceWindow.YTD, today=_TODAY)

    assert [p.close for p in sliced] == [Decimal("90"), Decimal("100")]


def test_slice_all_returns_every_point_unfiltered() -> None:
    points = _series((400, "70"), (10, "100"))

    assert slice_window(points, PriceWindow.ALL, today=_TODAY) == points


def test_slice_window_with_cutoff_before_all_data_falls_back_to_latest_point() -> None:
    """A symbol whose cached history is all older than the window (e.g. a stale
    cache entry queried with a short window) shouldn't return an empty slice --
    there's still a most-recent price to show."""
    points = _series((40, "100"), (35, "101"))

    sliced = slice_window(points, PriceWindow.ONE_WEEK, today=_TODAY)

    assert sliced == [points[-1]]


def test_compute_window_change_returns_none_for_fewer_than_two_points() -> None:
    points = _series((0, "100"))

    assert compute_window_change(points, PriceWindow.ONE_MONTH, today=_TODAY) is None


def test_compute_window_change_reports_price_and_position_delta() -> None:
    points = _series((5, "100"), (1, "110"))

    change = compute_window_change(
        points, PriceWindow.ONE_WEEK, quantity=Decimal("10"), today=_TODAY
    )

    assert change == WindowChange(
        start=points[0],
        end=points[1],
        price_dollars=Decimal("10"),
        price_percent=Decimal("10"),
        position_dollars=Decimal("100"),
    )


def test_compute_window_change_without_quantity_omits_position_dollars() -> None:
    points = _series((5, "100"), (1, "110"))

    change = compute_window_change(points, PriceWindow.ONE_WEEK, today=_TODAY)

    assert change is not None
    assert change.position_dollars is None


def test_compute_window_change_negative_move_is_signed_loss() -> None:
    points = _series((5, "100"), (1, "90"))

    change = compute_window_change(
        points, PriceWindow.ONE_WEEK, quantity=Decimal("2"), today=_TODAY
    )

    assert change is not None
    assert change.price_dollars == Decimal("-10")
    assert change.price_percent == Decimal("-10")
    assert change.position_dollars == Decimal("-20")


def test_compute_window_change_zero_start_price_yields_none_percent_not_a_crash() -> None:
    points = _series((5, "0"), (1, "10"))

    change = compute_window_change(points, PriceWindow.ONE_WEEK, today=_TODAY)

    assert change is not None
    assert change.price_dollars == Decimal("10")
    assert change.price_percent is None
