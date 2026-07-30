"""Integration tests for `GET /fundamentals/{symbol}`.

Uses the shared `api_client` fixture (see `conftest.py`) so the app's
lifespan actually runs (constructing `app.state.fmp_client`) and each
test's cache reads/writes land in an isolated temp DB rather than a file
shared across tests.
"""

import httpx
import respx
from fastapi.testclient import TestClient

_RATIOS_URL = "https://financialmodelingprep.com/stable/ratios"
_KEY_METRICS_URL = "https://financialmodelingprep.com/stable/key-metrics-ttm"


def _mock_fmp_success(symbol: str = "AAPL") -> None:
    respx.get(_RATIOS_URL).mock(
        return_value=httpx.Response(200, json=[{"symbol": symbol, "priceToEarningsRatio": 25.5}])
    )
    respx.get(_KEY_METRICS_URL).mock(
        return_value=httpx.Response(200, json=[{"symbol": symbol, "revenuePerShareTTM": 6.5}])
    )


@respx.mock
def test_get_fundamentals_with_valid_token_returns_200(
    api_client: TestClient, auth_headers: dict[str, str]
) -> None:
    _mock_fmp_success()

    response = api_client.get("/fundamentals/AAPL", headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "Financial Modeling Prep"
    assert body["value"]["symbol"] == "AAPL"
    assert "as_of" in body


def test_get_fundamentals_without_bearer_token_returns_401(api_client: TestClient) -> None:
    response = api_client.get("/fundamentals/AAPL")

    assert response.status_code == 401


@respx.mock
def test_get_fundamentals_for_unknown_symbol_returns_404(
    api_client: TestClient, auth_headers: dict[str, str]
) -> None:
    respx.get(_RATIOS_URL).mock(return_value=httpx.Response(200, json=[]))
    respx.get(_KEY_METRICS_URL).mock(return_value=httpx.Response(200, json=[]))

    response = api_client.get("/fundamentals/NOTREAL", headers=auth_headers)

    assert response.status_code == 404


@respx.mock
def test_get_fundamentals_when_fmp_down_with_no_cache_returns_502(
    api_client: TestClient, auth_headers: dict[str, str]
) -> None:
    respx.get(_RATIOS_URL).mock(return_value=httpx.Response(500))
    respx.get(_KEY_METRICS_URL).mock(return_value=httpx.Response(500))

    response = api_client.get("/fundamentals/AAPL", headers=auth_headers)

    assert response.status_code == 502
