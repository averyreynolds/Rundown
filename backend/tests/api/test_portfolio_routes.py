"""Integration tests for `/portfolio/*`.

On top of the shared `api_client` fixture's `get_session` override (see
`conftest.py`), these tests use `set_fake_snaptrade_client` (see
`tests/api/conftest.py`) so the route never touches the real
lifespan-constructed SnapTrade SDK client, which would otherwise attempt
a live network call.
"""

from collections.abc import Callable
from decimal import Decimal
from typing import Any

import httpx
import pytest
import respx
from fastapi.testclient import TestClient
from snaptrade_client.exceptions_base import OpenApiException

from tests.fixtures.synthetic_filing import SYNTHETIC_TICKER_MAP
from tests.fixtures.synthetic_positions import (
    synthetic_account,
    synthetic_balance,
    synthetic_stock_position,
)

_TICKER_MAP_URL = "https://www.sec.gov/files/company_tickers.json"


def test_connect_with_valid_token_returns_portal_url(
    api_client: TestClient,
    auth_headers: dict[str, str],
    set_fake_snaptrade_client: Callable[..., Any],
) -> None:
    set_fake_snaptrade_client()

    response = api_client.post("/portfolio/connect", headers=auth_headers)

    assert response.status_code == 200
    assert response.json()["portal_url"]


def test_connect_without_bearer_token_returns_401(
    api_client: TestClient, set_fake_snaptrade_client: Callable[..., Any]
) -> None:
    set_fake_snaptrade_client()

    response = api_client.post("/portfolio/connect")

    assert response.status_code == 401


def test_get_positions_with_no_linked_brokerage_returns_empty_list(
    api_client: TestClient,
    auth_headers: dict[str, str],
    set_fake_snaptrade_client: Callable[..., Any],
) -> None:
    """No brokerage linked yet is a valid, successful (empty) response, not an error."""
    set_fake_snaptrade_client()

    response = api_client.get("/portfolio/positions", headers=auth_headers)

    assert response.status_code == 200
    assert response.json()["value"] == []


def test_get_positions_returns_mapped_holdings(
    api_client: TestClient,
    auth_headers: dict[str, str],
    set_fake_snaptrade_client: Callable[..., Any],
) -> None:
    set_fake_snaptrade_client(
        accounts=[synthetic_account()],
        balance=synthetic_balance(),
        positions=[synthetic_stock_position()],
    )

    response = api_client.get("/portfolio/positions", headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "SnapTrade"
    assert body["value"][0]["symbol"] == "AAPL"


def test_get_rollup_merges_symbols_across_accounts_with_provenance(
    api_client: TestClient,
    auth_headers: dict[str, str],
    set_fake_snaptrade_client: Callable[..., Any],
) -> None:
    set_fake_snaptrade_client(
        accounts=[
            synthetic_account("synthetic-account-1"),
            synthetic_account("synthetic-account-2"),
        ],
        balance=synthetic_balance(),
        positions=[synthetic_stock_position(units=10, price=150.0, cost_basis_per_share=120.0)],
    )

    response = api_client.get("/portfolio/rollup", headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "SnapTrade"
    assert body["as_of"]
    assert body["is_stale"] is False
    assert len(body["value"]["positions"]) == 1
    row = body["value"]["positions"][0]
    assert row["symbol"] == "AAPL"
    assert Decimal(row["quantity"]) == 20
    assert Decimal(row["market_value"]) == 3000
    assert Decimal(row["cost_basis"]) == 2400
    assert Decimal(row["gain_percent"]) == 25
    assert Decimal(row["share_of_value_pct"]) == 100
    assert Decimal(row["share_of_net_gain_pct"]) == 100
    assert Decimal(body["value"]["net_gain_dollars"]) == 600


def test_get_rollup_figures_match_positions_for_a_single_account(
    api_client: TestClient,
    auth_headers: dict[str, str],
    set_fake_snaptrade_client: Callable[..., Any],
) -> None:
    set_fake_snaptrade_client(
        accounts=[synthetic_account()],
        balance=synthetic_balance(),
        positions=[
            synthetic_stock_position("AAPL", units=10, price=150.0, cost_basis_per_share=120.0),
            synthetic_stock_position("MSFT", units=3, price=400.0, cost_basis_per_share=410.0),
        ],
    )

    positions = api_client.get("/portfolio/positions", headers=auth_headers).json()["value"]
    rollup = api_client.get("/portfolio/rollup", headers=auth_headers).json()["value"]["positions"]

    rows = {row["symbol"]: row for row in rollup}
    assert len(rows) == len(positions)
    for position in positions:
        row = rows[position["symbol"]]
        assert Decimal(row["market_value"]) == Decimal(position["market_value"])
        assert Decimal(row["cost_basis"]) == Decimal(position["cost_basis"])
        assert Decimal(row["gain_dollars"]) == Decimal(position["unrealized_pnl_dollars"])
        assert Decimal(row["gain_percent"]) == Decimal(position["unrealized_pnl_percent"])
        assert Decimal(row["share_of_value_pct"]) == Decimal(position["allocation_pct"])


def test_get_rollup_with_no_linked_brokerage_returns_empty_rollup(
    api_client: TestClient,
    auth_headers: dict[str, str],
    set_fake_snaptrade_client: Callable[..., Any],
) -> None:
    set_fake_snaptrade_client()

    response = api_client.get("/portfolio/rollup", headers=auth_headers)

    assert response.status_code == 200
    value = response.json()["value"]
    assert value["positions"] == []
    assert Decimal(value["total_market_value"]) == 0
    assert Decimal(value["net_gain_dollars"]) == 0


def test_get_rollup_without_bearer_token_returns_401(
    api_client: TestClient, set_fake_snaptrade_client: Callable[..., Any]
) -> None:
    set_fake_snaptrade_client()

    response = api_client.get("/portfolio/rollup")

    assert response.status_code == 401


def test_get_rollup_reads_cached_positions_without_a_new_provider_call(
    api_client: TestClient,
    auth_headers: dict[str, str],
    set_fake_snaptrade_client: Callable[..., Any],
) -> None:
    client = set_fake_snaptrade_client(
        accounts=[synthetic_account()],
        balance=synthetic_balance(),
        positions=[synthetic_stock_position()],
    )

    api_client.get("/portfolio/positions", headers=auth_headers)
    response = api_client.get("/portfolio/rollup", headers=auth_headers)

    assert response.status_code == 200
    assert client.account_information.aget_all_account_positions.await_count == 1


def test_get_rollup_when_snaptrade_fails_with_cached_positions_is_labeled_stale(
    api_client: TestClient,
    auth_headers: dict[str, str],
    set_fake_snaptrade_client: Callable[..., Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = set_fake_snaptrade_client(
        accounts=[synthetic_account()],
        balance=synthetic_balance(),
        positions=[synthetic_stock_position()],
    )
    # A zero TTL leaves the first response cached but already expired.
    monkeypatch.setattr("app.services.snaptrade_service.positions_ttl_seconds", lambda: 0)
    assert api_client.get("/portfolio/rollup", headers=auth_headers).json()["is_stale"] is False

    client.account_information.aget_all_account_positions.side_effect = OpenApiException("down")
    response = api_client.get("/portfolio/rollup", headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["is_stale"] is True
    assert body["value"]["positions"][0]["symbol"] == "AAPL"


def test_get_rollup_when_snaptrade_fails_with_no_cache_returns_502(
    api_client: TestClient,
    auth_headers: dict[str, str],
    set_fake_snaptrade_client: Callable[..., Any],
) -> None:
    set_fake_snaptrade_client(
        accounts=[synthetic_account()],
        balance=synthetic_balance(),
        positions_error=OpenApiException("down"),
    )

    response = api_client.get("/portfolio/rollup", headers=auth_headers)

    assert response.status_code == 502


def test_connect_when_snaptrade_login_fails_returns_502(
    api_client: TestClient,
    auth_headers: dict[str, str],
    set_fake_snaptrade_client: Callable[..., Any],
) -> None:
    set_fake_snaptrade_client(login_error=OpenApiException("boom"))

    response = api_client.post("/portfolio/connect", headers=auth_headers)

    assert response.status_code == 502


@respx.mock
def test_get_company_names_returns_names_for_known_symbols_only(
    api_client: TestClient, auth_headers: dict[str, str]
) -> None:
    respx.get(_TICKER_MAP_URL).mock(return_value=httpx.Response(200, json=SYNTHETIC_TICKER_MAP))

    response = api_client.get(
        "/portfolio/company-names?symbols=SYNT&symbols=NOTFOUND", headers=auth_headers
    )

    assert response.status_code == 200
    assert response.json() == {"SYNT": "Synthetic Test Co"}


def test_get_company_names_without_bearer_token_returns_401(api_client: TestClient) -> None:
    response = api_client.get("/portfolio/company-names?symbols=SYNT")

    assert response.status_code == 401
