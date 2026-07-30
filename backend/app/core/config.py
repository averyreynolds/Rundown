"""Central application configuration, loaded from environment variables.

Every credential and tunable this backend will ever need -- across this unit
and every later one in the backend scaffold plan -- is declared here up
front, so later implementation units (U3, U4, U5, U6, U7, U8) only ever need
to *consume* fields from this module, never change its shape.

Required, secret-bearing fields (API keys, the shared bearer token) have no
default: a missing environment variable raises a ``pydantic.ValidationError``
at ``Settings()`` construction time, not a ``NoneType`` failure deep inside a
service later (CLAUDE.md hard rule 3: "API keys never reach the client" --
the corollary is they must be loudly present and correctly typed server-side,
never silently absent). Non-secret fields (TTLs, model id, log level) get
sensible MVP defaults.
"""

from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

# Resolve backend/.env relative to this file's location (backend/app/core/config.py),
# not the process's current working directory, so Settings() loads the same
# .env regardless of whether the app/tests are invoked from backend/ or
# elsewhere.
_BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
_ENV_FILE = _BACKEND_DIR / ".env"


class Settings(BaseSettings):
    """Application configuration sourced from the environment / ``backend/.env``."""

    model_config = SettingsConfigDict(
        env_file=_ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Required secrets: no default. Missing env var => ValidationError. ---
    snaptrade_client_id: SecretStr
    snaptrade_consumer_key: SecretStr
    fmp_api_key: SecretStr
    finnhub_api_key: SecretStr
    anthropic_api_key: SecretStr
    api_bearer_token: SecretStr

    # SEC EDGAR requires a descriptive User-Agent (app name + contact email)
    # on every request, or data.sec.gov returns 403. Not a secret, but there
    # is no safe placeholder default per SEC's access policy, so it's
    # required like the fields above.
    sec_edgar_user_agent: str

    # --- Non-secret fields with sensible MVP defaults. ---
    database_url: str = "sqlite+aiosqlite:///./rundown.db"
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])
    claude_model_id: str = "claude-sonnet-5"
    log_level: str = "INFO"

    # Cache TTLs (seconds). Centralized here now; app/cache/ttl_policy.py
    # (U3) is the module that will actually read and re-export these for
    # U4 (positions), U5 (fundamentals), U6 (filings), and U7 (news).
    positions_ttl_seconds: int = 300  # 5 min: avoid hammering SnapTrade on UI polling.
    fundamentals_ttl_seconds: int = 86_400  # 24h: FMP free tier is ~250 req/day.
    news_ttl_seconds: int = 14_400  # 4h: Finnhub free tier is 60 calls/min.
    edgar_ttl_seconds: int = 604_800  # 7d: published filing text never changes.

    def secret_values(self) -> list[str]:
        """Every literal secret string this process must never let leak.

        Used by ``core/logging.py`` to redact log records *by value*, not
        just by field name -- a stringified exception from a provider SDK
        could embed a raw key even when nothing intentionally logged the
        settings field itself.
        """
        return [
            self.snaptrade_client_id.get_secret_value(),
            self.snaptrade_consumer_key.get_secret_value(),
            self.fmp_api_key.get_secret_value(),
            self.finnhub_api_key.get_secret_value(),
            self.anthropic_api_key.get_secret_value(),
            self.api_bearer_token.get_secret_value(),
        ]


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide cached ``Settings`` instance.

    Cached so environment variables are parsed once per process rather than
    on every request. Tests that need specific values should construct
    ``Settings(...)`` directly instead of going through this cache.
    """
    return Settings()
