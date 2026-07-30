"""Shared exception types for provider-integration services (U4-U7).

Each is mapped to exactly one HTTP status by `app/api/error_handlers.py`,
so every router surfaces provider failures the same typed way instead of
each repeating its own translation logic (CLAUDE.md hard rule 6 / the
plan's System-Wide Impact invariant: external failures surface as typed
responses, never raw exceptions or stack traces):

- `ProviderFetchError`: a transient call to an external provider failed
  (network error, 5xx, 429, timeout). The *only* exception
  `cache_through.fetch_with_cache` treats as eligible for stale-cache
  fallback. Operations with no cache to fall back to at all (e.g.
  `SnapTradeService.connect()`'s registration/login calls) raise it
  directly instead -- it also has its own 502 mapping for exactly that
  case, not just as an internal signal to `fetch_with_cache`.
- `ProviderUnavailableError`: a fetch failed and no cached value -- fresh
  or stale -- exists at all. Maps to a 502 response.
- `ProviderNotFoundError`: the requested symbol/ticker/resource doesn't
  exist at the provider (e.g. an invalid ticker). Not a transient
  failure -- never eligible for stale-cache fallback, and services raise
  it directly rather than routing it through `fetch_with_cache`. Maps to
  a 404 response.
- `NotConnectedError`: no SnapTrade connection exists yet for this local
  user. Distinguishes "nothing to show yet, prompt the user to connect"
  from a provider outage -- maps to a 409 response.
- `InsufficientContextError`: the advisor (U8) has no data to ground an
  answer in for this request (no symbols, no connected portfolio, no
  filing text). Maps to a 422 response -- the request is well-formed, it
  just can't be grounded, which CLAUDE.md forbids answering anyway.
- `AdvisorUnavailableError`: the Claude API call itself failed or timed
  out. Maps to a 502 response; never returns a partial/garbled answer
  that could be misread as advice.
"""


class ProviderFetchError(Exception):
    """A live call to an external provider failed (network, 5xx, 429, timeout)."""


class ProviderUnavailableError(Exception):
    """A provider fetch failed and no cached value -- fresh or stale -- exists."""

    def __init__(self, provider: str, cache_key: str, cause: Exception) -> None:
        super().__init__(f"{provider}:{cache_key} is unavailable and nothing is cached.")
        self.provider = provider
        self.cache_key = cache_key
        self.cause = cause


class ProviderNotFoundError(Exception):
    """The requested symbol/ticker/resource does not exist at the provider."""

    def __init__(self, provider: str, identifier: str) -> None:
        super().__init__(f"{provider} has no data for '{identifier}'.")
        self.provider = provider
        self.identifier = identifier


class NotConnectedError(Exception):
    """No SnapTrade connection exists yet for this local user."""

    def __init__(self) -> None:
        super().__init__("No SnapTrade connection exists yet. Call POST /portfolio/connect first.")


class InsufficientContextError(Exception):
    """The advisor has no data to ground an answer in for this request."""


class AdvisorUnavailableError(Exception):
    """The Claude API call failed or timed out."""

    def __init__(self, cause: Exception) -> None:
        super().__init__(f"The advisor is temporarily unavailable: {cause}")
        self.cause = cause
