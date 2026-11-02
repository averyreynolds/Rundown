"""`POST /portfolio/connect`, `GET /portfolio/accounts`, `GET /portfolio/positions`,
`GET /portfolio/company-names`.

SnapTrade is wired up read-only only, using Personal-tier auth -- see
`app/services/snaptrade_service.py`'s module docstring for the exact
guarantee this provides and its open caveats.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.dependencies import get_edgar_service, get_snaptrade_service
from app.schemas.common import SourcedValue
from app.schemas.portfolio import AccountSummary, ConnectResponse, PositionView
from app.services.edgar_service import EdgarService
from app.services.snaptrade_service import SnapTradeService

router = APIRouter(prefix="/portfolio", tags=["portfolio"])


@router.post("/connect", summary="Register (if needed), return a read-only connection portal URL")
async def connect(
    snaptrade_service: Annotated[SnapTradeService, Depends(get_snaptrade_service)],
) -> ConnectResponse:
    portal_url = await snaptrade_service.connect()
    return ConnectResponse(portal_url=portal_url)


@router.get("/accounts", summary="Brokerage accounts and balances known to SnapTrade")
async def get_accounts(
    snaptrade_service: Annotated[SnapTradeService, Depends(get_snaptrade_service)],
) -> SourcedValue[list[AccountSummary]]:
    """An empty list is a valid response: no brokerage linked yet (see `/portfolio/connect`)."""
    return await snaptrade_service.list_accounts()


@router.get("/positions", summary="Equity-like holdings with computed allocation and P&L")
async def get_positions(
    snaptrade_service: Annotated[SnapTradeService, Depends(get_snaptrade_service)],
) -> SourcedValue[list[PositionView]]:
    """An empty list is a valid response: no brokerage linked yet (see `/portfolio/connect`)."""
    return await snaptrade_service.list_positions()


@router.get(
    "/company-names",
    summary="Best-effort registered company names for a set of symbols, from SEC's ticker map",
)
async def get_company_names(
    edgar_service: Annotated[EdgarService, Depends(get_edgar_service)],
    symbols: Annotated[
        list[str], Query(description="Repeat for multiple, e.g. ?symbols=AAPL&symbols=MSFT")
    ],
) -> dict[str, str]:
    """`{symbol: name}`; a symbol absent from SEC's mapping (an ETF, a non-US listing) is
    omitted, not raised -- callers fall back to the ticker for those."""
    return await edgar_service.resolve_company_names(symbols)
