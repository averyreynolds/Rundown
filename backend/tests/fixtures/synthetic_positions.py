"""Synthetic SnapTrade fixture data.

Shaped to match the SDK response fields verified by introspecting the
installed `snaptrade-python-sdk` package (see
`app/services/snaptrade_service.py`'s module docstring) -- not real
account, credential, or holdings data (CLAUDE.md forbids committing any
of that, even in test fixtures).

The personal-key flow does not call `registerUser`, so there is no
`synthetic_register_response` here and `build_fake_snaptrade_client` does
not include an `aregister_snap_trade_user` mock.
"""

from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock


def synthetic_login_response(
    redirect_uri: str = "https://connect.snaptrade.com/portal/synthetic",
) -> dict[str, str]:
    return {"redirectURI": redirect_uri, "sessionId": "synthetic-session-id"}


def synthetic_account(account_id: str = "synthetic-account-1") -> dict[str, str]:
    return {
        "id": account_id,
        "name": "Synthetic Individual",
        "institution_name": "Synthetic Brokerage",
    }


def synthetic_balance() -> dict[str, Any]:
    return {"cash": 1000.0, "buying_power": 2000.0, "currency": "USD"}


def synthetic_stock_position(
    symbol: str = "AAPL", units: float = 10, price: float = 150.0, cost_basis: float = 1200.0
) -> dict[str, Any]:
    return {
        "units": units,
        "price": price,
        "cost_basis": cost_basis,
        "instrument": {"kind": "stock", "symbol": symbol, "raw_symbol": symbol},
    }


def synthetic_option_position() -> dict[str, Any]:
    """A non-equity position `SnapTradeService.list_positions` must filter out."""
    return {
        "units": 1,
        "price": 5.0,
        "cost_basis": 500.0,
        "instrument": {"kind": "option", "symbol": "AAPL 250101C00150000"},
    }


def build_fake_snaptrade_client(
    *,
    accounts: list[dict[str, Any]] | None = None,
    balance: dict[str, Any] | None = None,
    positions: list[dict[str, Any]] | None = None,
    login_error: Exception | None = None,
    positions_error: Exception | None = None,
) -> SimpleNamespace:
    """A `SimpleNamespace` shaped like the real `SnapTrade` SDK client.

    Matches the real client's `.authentication.a*` /
    `.account_information.a*` async-method shape closely enough for
    `SnapTradeService` to use it unmodified, without needing the real
    SDK's `aiohttp`-based transport or a live SnapTrade account.  Shared
    by both the service-level and route-level test suites so this shape is
    defined once.

    The personal-key flow calls only `alogin_snap_trade_user` (not
    `aregister_snap_trade_user`), so only that method is mocked here.
    """
    login_mock = AsyncMock(
        side_effect=login_error,
        return_value=None if login_error else SimpleNamespace(body=synthetic_login_response()),
    )
    accounts_mock = AsyncMock(
        return_value=SimpleNamespace(body=accounts if accounts is not None else [])
    )
    balance_mock = AsyncMock(
        return_value=SimpleNamespace(body=balance if balance is not None else {})
    )
    positions_mock = AsyncMock(
        side_effect=positions_error,
        return_value=None if positions_error else SimpleNamespace(body=positions or []),
    )
    return SimpleNamespace(
        authentication=SimpleNamespace(
            alogin_snap_trade_user=login_mock,
        ),
        account_information=SimpleNamespace(
            alist_user_accounts=accounts_mock,
            aget_user_account_balance=balance_mock,
            aget_all_account_positions=positions_mock,
        ),
    )
