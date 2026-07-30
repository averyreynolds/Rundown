"""`GET /news` -- cached, holdings-filtered news via Finnhub.

No server-side watchlist entity for R4 (see the plan's Scope Boundaries):
the client supplies which symbols it wants news for on every call.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.dependencies import get_finnhub_service
from app.schemas.common import SourcedValue
from app.schemas.news import NewsItem
from app.services.finnhub_service import FinnhubService

router = APIRouter(prefix="/news", tags=["news"])


@router.get("", summary="Recent news for a set of holdings/watchlist symbols")
async def get_news(
    finnhub_service: Annotated[FinnhubService, Depends(get_finnhub_service)],
    symbols: Annotated[
        list[str], Query(description="Repeat for multiple, e.g. ?symbols=AAPL&symbols=MSFT")
    ],
) -> SourcedValue[list[NewsItem]]:
    return await finnhub_service.get_news_for_symbols(symbols)
