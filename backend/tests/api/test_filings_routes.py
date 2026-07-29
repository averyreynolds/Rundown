"""Integration tests for `GET /filings/{symbol}` and
`GET /filings/{symbol}/{accession_number}`.

Uses the shared `api_client` fixture (see `conftest.py`) for lifespan
startup and per-test DB isolation.
"""

import httpx
import respx
from fastapi.testclient import TestClient

from tests.fixtures.synthetic_filing import (
    SYNTHETIC_FILING_TEXT,
    SYNTHETIC_TICKER_MAP,
    synthetic_submissions,
)

_TICKER_MAP_URL = "https://www.sec.gov/files/company_tickers.json"
_SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK0000320193.json"
_FILING_TEXT_URL = (
    "https://www.sec.gov/Archives/edgar/data/320193/000032019324000123/synthetic-10k.htm"
)


def _mock_ticker_map_and_submissions() -> None:
    respx.get(_TICKER_MAP_URL).mock(return_value=httpx.Response(200, json=SYNTHETIC_TICKER_MAP))
    respx.get(_SUBMISSIONS_URL).mock(return_value=httpx.Response(200, json=synthetic_submissions()))


@respx.mock
def test_list_filings_with_valid_token_returns_200(
    api_client: TestClient, auth_headers: dict[str, str]
) -> None:
    _mock_ticker_map_and_submissions()

    response = api_client.get("/filings/SYNT", headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "SEC EDGAR"
    assert [f["form"] for f in body["value"]] == ["10-K", "10-Q", "8-K"]


def test_list_filings_without_bearer_token_returns_401(api_client: TestClient) -> None:
    response = api_client.get("/filings/SYNT")

    assert response.status_code == 401


@respx.mock
def test_get_filing_text_returns_200(api_client: TestClient, auth_headers: dict[str, str]) -> None:
    _mock_ticker_map_and_submissions()
    respx.get(_FILING_TEXT_URL).mock(return_value=httpx.Response(200, text=SYNTHETIC_FILING_TEXT))

    response = api_client.get("/filings/SYNT/0000320193-24-000123", headers=auth_headers)

    assert response.status_code == 200
    assert response.json()["value"]["text"] == SYNTHETIC_FILING_TEXT


@respx.mock
def test_list_filings_for_unknown_symbol_returns_404(
    api_client: TestClient, auth_headers: dict[str, str]
) -> None:
    respx.get(_TICKER_MAP_URL).mock(return_value=httpx.Response(200, json=SYNTHETIC_TICKER_MAP))

    response = api_client.get("/filings/NOTREAL", headers=auth_headers)

    assert response.status_code == 404


@respx.mock
def test_list_filings_when_edgar_down_with_no_cache_returns_502(
    api_client: TestClient, auth_headers: dict[str, str]
) -> None:
    respx.get(_TICKER_MAP_URL).mock(return_value=httpx.Response(403))

    response = api_client.get("/filings/SYNT", headers=auth_headers)

    assert response.status_code == 502
