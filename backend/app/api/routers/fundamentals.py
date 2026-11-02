"""`GET /fundamentals/{symbol}` -- cached FMP ratios and TTM key metrics.
`GET /fundamentals/{symbol}/price-history` -- cached FMP daily closes.
"""

from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.dependencies import get_fmp_service
from app.schemas.common import SourcedValue
from app.schemas.fundamentals import FundamentalsSnapshot
from app.schemas.prices import PriceHistoryWindow, PriceWindow
from app.services.fmp_service import FmpService

router = APIRouter(prefix="/fundamentals", tags=["fundamentals"])


@router.get("/{symbol}", summary="Cached fundamental ratios for a symbol")
async def get_fundamentals(
    symbol: str,
    fmp_service: Annotated[FmpService, Depends(get_fmp_service)],
) -> SourcedValue[FundamentalsSnapshot]:
    """Return `symbol`'s cached (or freshly-fetched) ratios and TTM metrics.

    404s if FMP has no data for `symbol` at all; 502s if FMP is failing
    and nothing -- fresh or stale -- is cached yet (see
    `app/api/error_handlers.py` for how those are surfaced).
    """
    return await fmp_service.get_fundamentals(symbol)


@router.get(
    "/{symbol}/price-history",
    summary="Cached daily closes for a symbol, sliced to a selectable window",
)
async def get_price_history(
    symbol: str,
    fmp_service: Annotated[FmpService, Depends(get_fmp_service)],
    window: PriceWindow = PriceWindow.ALL,
) -> SourcedValue[PriceHistoryWindow]:
    """Chronologically ordered. 404s if FMP has no data for `symbol` at all;
    502s if FMP is failing and nothing -- fresh or stale -- is cached yet."""
    return await fmp_service.get_price_history(symbol, window)
