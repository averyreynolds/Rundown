"""Integration tests for `/portfolio/*`.

On top of the shared `api_client` fixture's `get_session` override (see
`conftest.py`), these tests use `set_fake_snaptrade_client` (see
`tests/api/conftest.py`) so the route never touches the real
lifespan-constructed SnapTrade SDK client, which would otherwise attempt
a live network call.
"""

from collections.abc import Callable
from typing import Any

from fastapi.testclient import TestClient
from snaptrade_client.exceptions_base import OpenApiException

from tests.fixtures.synthetic_positions import (
    synthetic_account,
    synthetic_balance,
    synthetic_stock_position,
)


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


def test_get_positions_without_connecting_first_returns_409(
    api_client: TestClient,
    auth_headers: dict[str, str],
    set_fake_snaptrade_client: Callable[..., Any],
) -> None:
    set_fake_snaptrade_client()

    response = api_client.get("/portfolio/positions", headers=auth_headers)

    assert response.status_code == 409


def test_get_positions_after_connecting_returns_mapped_holdings(
    api_client: TestClient,
    auth_headers: dict[str, str],
    set_fake_snaptrade_client: Callable[..., Any],
) -> None:
    set_fake_snaptrade_client(
        accounts=[synthetic_account()],
        balance=synthetic_balance(),
        positions=[synthetic_stock_position()],
    )

    connect_response = api_client.post("/portfolio/connect", headers=auth_headers)
    assert connect_response.status_code == 200

    response = api_client.get("/portfolio/positions", headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "SnapTrade"
    assert body["value"][0]["symbol"] == "AAPL"


def test_connect_when_snaptrade_registration_fails_returns_502(
    api_client: TestClient,
    auth_headers: dict[str, str],
    set_fake_snaptrade_client: Callable[..., Any],
) -> None:
    set_fake_snaptrade_client(register_error=OpenApiException("boom"))

    response = api_client.post("/portfolio/connect", headers=auth_headers)

    assert response.status_code == 502
