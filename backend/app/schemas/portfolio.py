"""Response schemas for `/portfolio/*` endpoints."""

from decimal import Decimal

from pydantic import BaseModel


class ConnectResponse(BaseModel):
    """Result of `POST /portfolio/connect`: a read-only connection portal URL."""

    portal_url: str


class AccountSummary(BaseModel):
    """One brokerage account known to SnapTrade, with its cash/buying-power balance."""

    account_id: str
    name: str
    institution_name: str
    cash: Decimal | None = None
    buying_power: Decimal | None = None
    currency: str | None = None


class PositionView(BaseModel):
    """One holding, with its computed allocation and P&L attached.

    Flattens U2's `Holding`/`Allocation`/`UnrealizedPnl` domain types into
    one response shape rather than exposing three separate arrays the
    frontend would need to zip together by symbol. Deliberately
    account-scoped, not merged across accounts by symbol -- see
    `SnapTradeService.list_positions`'s docstring for why.
    """

    symbol: str
    account_id: str
    quantity: Decimal
    cost_basis: Decimal
    current_price: Decimal
    market_value: Decimal
    allocation_pct: Decimal
    unrealized_pnl_dollars: Decimal
    unrealized_pnl_percent: Decimal | None
