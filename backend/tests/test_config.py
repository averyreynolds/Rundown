"""Tests for `app.core.config.Settings`.

Required environment variables are set globally for the whole test session
by `tests/conftest.py` (see the module docstring there for why). These
tests construct `Settings()` directly rather than going through
`get_settings()`'s cache, so each test observes environment changes made
via `monkeypatch` within that same test.
"""

import pytest
from pydantic import SecretStr, ValidationError

from app.core.config import Settings, get_settings


def test_settings_loads_with_all_required_env_vars_set() -> None:
    """Happy path: every required var present -> Settings() loads with correct types."""
    settings = Settings()

    assert isinstance(settings.snaptrade_client_id, SecretStr)
    assert isinstance(settings.snaptrade_consumer_key, SecretStr)
    assert isinstance(settings.fmp_api_key, SecretStr)
    assert isinstance(settings.finnhub_api_key, SecretStr)
    assert isinstance(settings.anthropic_api_key, SecretStr)
    assert isinstance(settings.api_bearer_token, SecretStr)
    assert isinstance(settings.sec_edgar_user_agent, str)
    assert isinstance(settings.database_url, str)
    assert isinstance(settings.cors_origins, list)
    assert all(isinstance(origin, str) for origin in settings.cors_origins)
    assert isinstance(settings.claude_model_id, str)
    assert isinstance(settings.log_level, str)
    assert isinstance(settings.positions_ttl_seconds, int)
    assert isinstance(settings.fundamentals_ttl_seconds, int)
    assert isinstance(settings.news_ttl_seconds, int)
    assert isinstance(settings.edgar_ttl_seconds, int)


def test_settings_has_sensible_non_secret_defaults() -> None:
    """Non-secret fields (TTLs, model id, CORS origins, log level) default sensibly."""
    settings = Settings()

    assert settings.database_url == "sqlite+aiosqlite:///./rundown.db"
    assert settings.cors_origins == ["http://localhost:3000"]
    assert settings.claude_model_id == "claude-sonnet-5"
    assert settings.log_level == "INFO"
    assert settings.positions_ttl_seconds == 300
    assert settings.fundamentals_ttl_seconds == 86_400
    assert settings.news_ttl_seconds == 14_400
    assert settings.edgar_ttl_seconds == 604_800


@pytest.mark.parametrize(
    "missing_env_var",
    [
        "SNAPTRADE_CLIENT_ID",
        "SNAPTRADE_CONSUMER_KEY",
        "FMP_API_KEY",
        "FINNHUB_API_KEY",
        "ANTHROPIC_API_KEY",
        "API_BEARER_TOKEN",
        "SEC_EDGAR_USER_AGENT",
    ],
)
def test_settings_raises_validation_error_when_required_var_missing(
    missing_env_var: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Error path: a missing required var fails loudly at construction time.

    This must surface as a `pydantic.ValidationError` raised from
    `Settings()` itself -- not a later `NoneType` failure deep inside a
    service that tries to use a silently-absent value.

    Constructed with `_env_file=None` to isolate from a real `backend/.env`
    that may exist on the machine running this suite (every contributor is
    instructed to create one in Setup): `Settings`'s `model_config` points
    at that file by path, and pydantic-settings falls back to it for any
    field `monkeypatch.delenv` removes from `os.environ`, which would mask
    exactly the failure this test exists to catch.
    """
    monkeypatch.delenv(missing_env_var, raising=False)

    with pytest.raises(ValidationError) as exc_info:
        Settings(_env_file=None)

    assert missing_env_var.lower() in str(exc_info.value).lower()


def test_get_settings_is_cached() -> None:
    """`get_settings()` returns the same instance across calls (`lru_cache`)."""
    assert get_settings() is get_settings()


def test_secret_values_returns_every_secret_literal() -> None:
    """`secret_values()` exposes every secret field's raw string for redaction."""
    settings = Settings()

    secret_values = settings.secret_values()

    assert settings.api_bearer_token.get_secret_value() in secret_values
    assert settings.anthropic_api_key.get_secret_value() in secret_values
    assert settings.fmp_api_key.get_secret_value() in secret_values
    assert settings.finnhub_api_key.get_secret_value() in secret_values
    assert settings.snaptrade_client_id.get_secret_value() in secret_values
    assert settings.snaptrade_consumer_key.get_secret_value() in secret_values
