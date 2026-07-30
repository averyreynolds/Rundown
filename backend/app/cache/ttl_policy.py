"""Centralized cache TTL policy: one place to read *and change* how long
each data type stays fresh, per CLAUDE.md's rate-limit discipline rule
("respect free-tier rate limits by caching, not by calling live").

The actual numbers live in `Settings` (`app/core/config.py`), overridable
via `backend/.env` without a code change -- this module is the single
place a service asks "how long should this be cached" without needing to
know which settings field backs which provider. Each function name
documents *why* its TTL is what it is, which a bare settings field
reference at every call site would not.
"""

from app.core.config import get_settings


def positions_ttl_seconds() -> int:
    """SnapTrade positions/balances TTL: short, to absorb rapid frontend polling."""
    return get_settings().positions_ttl_seconds


def fundamentals_ttl_seconds() -> int:
    """FMP fundamentals TTL: long, since the free tier allows ~250 requests/day."""
    return get_settings().fundamentals_ttl_seconds


def filings_ttl_seconds() -> int:
    """SEC EDGAR filings TTL: very long, since published filing text never changes."""
    return get_settings().edgar_ttl_seconds


def news_ttl_seconds() -> int:
    """Finnhub news TTL: moderate, since the free tier allows 60 calls/min."""
    return get_settings().news_ttl_seconds
