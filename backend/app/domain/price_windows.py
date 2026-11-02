"""Selectable-window price change for the holding-detail sidebar chart.

`PriceWindow.ONE_DAY` deliberately means "since the last close before this
one," not "the last 24 hours" -- `PricePoint.close` is EOD data (see
`services/fmp_service.py`), so there's no intraday tick to diff against.
Slicing to the trailing two points gives the right answer either way: on a
Monday that's Friday's close vs. today's, which is also what a broker's own
"day change" means after a weekend.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from enum import Enum

from app.domain.types import PricePoint


class PriceWindow(Enum):
    ONE_DAY = "1D"
    ONE_WEEK = "1W"
    ONE_MONTH = "1M"
    THREE_MONTHS = "3M"
    YTD = "YTD"
    ONE_YEAR = "1Y"
    ALL = "ALL"


@dataclass(frozen=True, slots=True)
class WindowChange:
    """Price (and, if a quantity was given, position-value) change from the
    first to the last point of a sliced window.

    `price_percent` is `None` when the window's starting close is zero --
    not expected for a real equity price, but the same divide-by-zero
    guard `domain.pnl.compute_pnl` applies to cost basis.
    """

    start: PricePoint
    end: PricePoint
    price_dollars: Decimal
    price_percent: Decimal | None
    position_dollars: Decimal | None


_WINDOW_LOOKBACK_DAYS: dict[PriceWindow, int] = {
    PriceWindow.ONE_WEEK: 7,
    PriceWindow.ONE_MONTH: 30,
    PriceWindow.THREE_MONTHS: 91,
    PriceWindow.ONE_YEAR: 365,
}


def slice_window(
    points: Sequence[PricePoint], window: PriceWindow, *, today: date
) -> list[PricePoint]:
    """Return the suffix of `points` (assumed chronologically ordered, oldest first)
    falling within `window`, relative to `today`.

    Never returns an empty list for a non-empty `points`: a window whose
    cutoff falls after every point still returns the single most recent
    point, since "no data old enough to fill the window" isn't the same
    as "no data."
    """
    if not points:
        return []

    if window is PriceWindow.ONE_DAY:
        return list(points[-2:])

    if window is PriceWindow.ALL:
        return list(points)

    if window is PriceWindow.YTD:
        cutoff = date(today.year, 1, 1)
    else:
        cutoff = today - timedelta(days=_WINDOW_LOOKBACK_DAYS[window])

    sliced = [p for p in points if p.date >= cutoff]
    return sliced or [points[-1]]


def compute_window_change(
    points: Sequence[PricePoint],
    window: PriceWindow,
    *,
    quantity: Decimal | None = None,
    today: date,
) -> WindowChange | None:
    """Return the change over `window`, or `None` if fewer than two points fall in it
    (e.g. a symbol newly held, or a window larger than the cached history)."""
    sliced = slice_window(points, window, today=today)
    if len(sliced) < 2:
        return None

    start, end = sliced[0], sliced[-1]
    price_dollars = end.close - start.close
    price_percent = (price_dollars / start.close * Decimal(100)) if start.close != 0 else None
    position_dollars = price_dollars * quantity if quantity is not None else None

    return WindowChange(
        start=start,
        end=end,
        price_dollars=price_dollars,
        price_percent=price_percent,
        position_dollars=position_dollars,
    )
