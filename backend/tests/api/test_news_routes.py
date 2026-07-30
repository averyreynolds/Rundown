"""Integration tests for `GET /news`.

Uses the shared `api_client` fixture (see `conftest.py`) for lifespan
startup and per-test DB isolation.
"""

import httpx
import respx
from fastapi.testclient import TestClient

from tests.fixtures.synthetic_news import synthetic_news_items

_NEWS_URL = "https://finnhub.io/api/v1/company-news"


@respx.mock
def test_get_news_with_valid_token_returns_200(
    api_client: TestClient, auth_headers: dict[str, str]
) -> None:
    respx.get(_NEWS_URL, params={"symbol": "AAPL"}).mock(
        return_value=httpx.Response(200, json=synthetic_news_items(2))
    )

    response = api_client.get("/news", params={"symbols": ["AAPL"]}, headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "Finnhub"
    assert len(body["value"]) == 2


def test_get_news_without_bearer_token_returns_401(api_client: TestClient) -> None:
    response = api_client.get("/news", params={"symbols": ["AAPL"]})

    assert response.status_code == 401


@respx.mock
def test_get_news_with_no_articles_returns_empty_list(
    api_client: TestClient, auth_headers: dict[str, str]
) -> None:
    respx.get(_NEWS_URL, params={"symbol": "AAPL"}).mock(return_value=httpx.Response(200, json=[]))

    response = api_client.get("/news", params={"symbols": ["AAPL"]}, headers=auth_headers)

    assert response.status_code == 200
    assert response.json()["value"] == []


@respx.mock
def test_get_news_when_finnhub_down_with_no_cache_returns_502(
    api_client: TestClient, auth_headers: dict[str, str]
) -> None:
    respx.get(_NEWS_URL, params={"symbol": "AAPL"}).mock(return_value=httpx.Response(429))

    response = api_client.get("/news", params={"symbols": ["AAPL"]}, headers=auth_headers)

    assert response.status_code == 502
