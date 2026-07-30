"""`POST /portfolio/connect`, `GET /portfolio/accounts`, `GET /portfolio/positions`.

SnapTrade is wired up read-only only -- see
`app/services/snaptrade_service.py`'s module docstring for the exact
guarantee this provides and its one open caveat.
"""

from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.dependencies import get_snaptrade_service
from app.schemas.common import SourcedValue
from app.schemas.portfolio import AccountSummary, ConnectResponse, PositionView
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
    """409s if no SnapTrade connection exists yet (call `/portfolio/connect` first)."""
    return await snaptrade_service.list_accounts()


@router.get("/positions", summary="Equity-like holdings with computed allocation and P&L")
async def get_positions(
    snaptrade_service: Annotated[SnapTradeService, Depends(get_snaptrade_service)],
) -> SourcedValue[list[PositionView]]:
    """409s if no SnapTrade connection exists yet (call `/portfolio/connect` first)."""
    return await snaptrade_service.list_positions()
