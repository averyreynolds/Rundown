"""Shared pytest fixtures for the backend test suite.

The required, secret-bearing environment variables are set at *module
import time* below, not inside a fixture. `app/main.py` builds its
module-level `app = create_app()` object (and that construction calls
`get_settings()`, which constructs `Settings()`) at import time, so those
values must already be in the environment before anything in the suite
first runs `from app.main import app` -- including at pytest *collection*
time, which happens before any fixture (even a session-scoped autouse one)
gets to run. conftest.py is imported before pytest collects any test module
in this directory tree, so setting `os.environ` here is the one place that
is guaranteed to run early enough.

Each placeholder is a distinct string (not the same value reused for every
variable) so tests -- particularly the logging-redaction test -- can assert
that a *specific* secret was scrubbed, not just that redaction ran at all.
"""

import os

import pytest

PLACEHOLDER_ENV: dict[str, str] = {
    "SNAPTRADE_CLIENT_ID": "test-snaptrade-client-id-placeholder",
    "SNAPTRADE_CONSUMER_KEY": "test-snaptrade-consumer-key-placeholder",
    "FMP_API_KEY": "test-fmp-api-key-placeholder",
    "FINNHUB_API_KEY": "test-finnhub-api-key-placeholder",
    "ANTHROPIC_API_KEY": "test-anthropic-api-key-placeholder",
    "SEC_EDGAR_USER_AGENT": "Rundown Test Suite (test@example.com)",
    "API_BEARER_TOKEN": "test-bearer-token-placeholder",
}

os.environ.update(PLACEHOLDER_ENV)


@pytest.fixture
def bearer_token() -> str:
    """The placeholder bearer token configured for the whole test session."""
    return PLACEHOLDER_ENV["API_BEARER_TOKEN"]


@pytest.fixture
def auth_headers(bearer_token: str) -> dict[str, str]:
    """`Authorization` header carrying the test session's bearer token."""
    return {"Authorization": f"Bearer {bearer_token}"}
