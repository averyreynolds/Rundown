"""Response schema for `GET /fundamentals/{symbol}/price-history`."""

from datetime import date
from decimal import Decimal

from pydantic import BaseModel

from app.domain.price_windows import PriceWindow

__all__ = ["PriceHistoryWindow", "PricePoint", "PriceWindow"]


class PricePoint(BaseModel):
    """One EOD close for a symbol, chronologically ordered within `PriceHistoryWindow.points`."""

    date: date
    close: Decimal


class PriceHistoryWindow(BaseModel):
    """`symbol`'s closes sliced to one selectable window, plus that window's price
    change -- both computed server-side by `app.domain.price_windows` (see
    `FmpService.get_price_history`) so a client never re-derives money math itself.

    `price_change_*` is `None` when the window has fewer than two points to diff
    (e.g. a symbol newly held, sliced to a window wider than its cached history).
    """

    points: list[PricePoint]
    price_change_dollars: Decimal | None = None
    price_change_percent: Decimal | None = None
