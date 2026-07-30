"""End-to-end smoke test: proves the whole app wires together, not just its
parts in isolation.

Hits `/health`, `/docs`, and one representative route from each
implemented router (portfolio, fundamentals, filings, news, advisor),
with every external call mocked.
"""

from collections.abc import Callable
from typing import Any

import httpx
import respx
from fastapi.testclient import TestClient

from tests.fixtures.synthetic_advisor import fake_anthropic_client
from tests.fixtures.synthetic_filing import SYNTHETIC_TICKER_MAP, synthetic_submissions
from tests.fixtures.synthetic_news import synthetic_news_items
from tests.fixtures.synthetic_positions import (
    synthetic_account,
    synthetic_balance,
    synthetic_stock_position,
)

_IMPLEMENTED_ROUTE_PREFIXES = (
    "/health",
    "/portfolio",
    "/fundamentals",
    "/filings",
    "/news",
    "/advisor",
)


def test_health_is_reachable_without_a_bearer_token(api_client: TestClient) -> None:
    assert api_client.get("/health").status_code == 200


def test_docs_and_openapi_are_reachable_without_a_bearer_token(api_client: TestClient) -> None:
    assert api_client.get("/docs").status_code == 200
    assert api_client.get("/openapi.json").status_code == 200


def test_openapi_lists_every_implemented_router(api_client: TestClient) -> None:
    paths = api_client.get("/openapi.json").json()["paths"]
    for prefix in _IMPLEMENTED_ROUTE_PREFIXES:
        assert any(path.startswith(prefix) for path in paths), f"missing routes under {prefix}"


def _mock_every_provider() -> None:
    respx.get("https://financialmodelingprep.com/stable/ratios").mock(
        return_value=httpx.Response(200, json=[{"symbol": "AAPL", "priceToEarningsRatio": 20}])
    )
    respx.get("https://financialmodelingprep.com/stable/key-metrics-ttm").mock(
        return_value=httpx.Response(200, json=[{"symbol": "AAPL", "revenuePerShareTTM": 5}])
    )
    respx.get("https://www.sec.gov/files/company_tickers.json").mock(
        return_value=httpx.Response(200, json=SYNTHETIC_TICKER_MAP)
    )
    respx.get("https://data.sec.gov/submissions/CIK0000320193.json").mock(
        return_value=httpx.Response(200, json=synthetic_submissions())
    )
    respx.get("https://finnhub.io/api/v1/company-news").mock(
        return_value=httpx.Response(200, json=synthetic_news_items())
    )


@respx.mock
def test_one_route_per_router_succeeds_with_bearer_token(
    api_client: TestClient,
    auth_headers: dict[str, str],
    set_fake_snaptrade_client: Callable[..., Any],
    set_fake_claude_client: Callable[..., Any],
) -> None:
    set_fake_snaptrade_client(
        accounts=[synthetic_account()],
        balance=synthetic_balance(),
        positions=[synthetic_stock_position()],
    )
    set_fake_claude_client(fake_anthropic_client("Your AAPL position is 100% of your portfolio."))
    _mock_every_provider()

    connect_response = api_client.post("/portfolio/connect", headers=auth_headers)
    assert connect_response.status_code == 200, connect_response.text

    get_routes_and_expected_schema_keys = {
        "/portfolio/positions": {"value", "source", "as_of"},
        "/fundamentals/AAPL": {"value", "source", "as_of"},
        "/filings/SYNT": {"value", "source", "as_of"},
        "/news?symbols=AAPL": {"value", "source", "as_of"},
    }
    for path, expected_keys in get_routes_and_expected_schema_keys.items():
        response = api_client.get(path, headers=auth_headers)
        assert response.status_code == 200, f"{path} -> {response.status_code}: {response.text}"
        assert expected_keys.issubset(response.json().keys()), path

    advisor_response = api_client.post(
        "/advisor/chat",
        headers=auth_headers,
        json={"question": "How is my AAPL position doing?", "context_refs": {"symbols": ["AAPL"]}},
    )
    assert advisor_response.status_code == 200, advisor_response.text
    assert {"answer", "citations"}.issubset(advisor_response.json().keys())


@respx.mock
def test_every_implemented_route_except_health_and_docs_requires_bearer_token(
    api_client: TestClient,
    set_fake_snaptrade_client: Callable[..., Any],
    set_fake_claude_client: Callable[..., Any],
) -> None:
    """Confirms U1's access-control gate is wired into every router, not
    just the one it was originally written against."""
    set_fake_snaptrade_client()
    set_fake_claude_client(fake_anthropic_client())

    for path in (
        "/portfolio/positions",
        "/fundamentals/AAPL",
        "/filings/SYNT",
        "/news?symbols=AAPL",
    ):
        response = api_client.get(path)
        assert response.status_code == 401, path

    advisor_response = api_client.post("/advisor/chat", json={"question": "Anything?"})
    assert advisor_response.status_code == 401


def test_cors_preflight_from_configured_frontend_origin_succeeds(api_client: TestClient) -> None:
    response = api_client.options(
        "/portfolio/positions",
        headers={"Origin": "http://localhost:3000", "Access-Control-Request-Method": "GET"},
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"


def test_cors_preflight_from_an_unconfigured_origin_is_rejected(api_client: TestClient) -> None:
    response = api_client.options(
        "/portfolio/positions",
        headers={"Origin": "http://evil.example.com", "Access-Control-Request-Method": "GET"},
    )
    assert response.status_code == 400
