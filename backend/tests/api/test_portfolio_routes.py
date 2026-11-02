"""Integration tests for `/portfolio/*`.

On top of the shared `api_client` fixture's `get_session` override (see
`conftest.py`), these tests use `set_fake_snaptrade_client` (see
`tests/api/conftest.py`) so the route never touches the real
lifespan-constructed SnapTrade SDK client, which would otherwise attempt
a live network call.
"""

from collections.abc import Callable
from typing import Any

import httpx
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
