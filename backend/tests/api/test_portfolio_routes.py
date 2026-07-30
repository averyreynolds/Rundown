"""Integration tests for `/portfolio/*`.

On top of the shared `api_client` fixture's `get_session` override (see
`conftest.py`), these tests also override `get_snaptrade_client` so the
route never touches the real lifespan-constructed SnapTrade SDK client,
which would otherwise attempt a live network call.
"""

from collections.abc import Callable, Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from snaptrade_client.exceptions_base import OpenApiException

from app.api.dependencies import get_snaptrade_client
from app.main import app
from tests.fixtures.synthetic_positions import (
    build_fake_snaptrade_client,
    synthetic_account,
    synthetic_balance,
    synthetic_stock_position,
)


@pytest.fixture
def set_fake_snaptrade_client() -> Iterator[Callable[..., Any]]:
    """Override `get_snaptrade_client` for this test only, cleaned up after."""

    def _set(**kwargs: Any) -> Any:  # noqa: ANN401
        client = build_fake_snaptrade_client(**kwargs)
        app.dependency_overrides[get_snaptrade_client] = lambda: client
        return client

    yield _set
    app.dependency_overrides.pop(get_snaptrade_client, None)


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
