"""Central mapping from service-layer exceptions to typed HTTP responses.

Registered once in `create_app()` so every router (fundamentals, filings,
news, portfolio, advisor) surfaces provider failures the same way, per
the plan's System-Wide Impact invariant that external failures "surface
as typed HTTP error responses... never raw exceptions/stack traces" --
without each router repeating its own try/except translation.
"""

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from app.services.errors import (
    AdvisorUnavailableError,
    InsufficientContextError,
    ProviderFetchError,
    ProviderNotFoundError,
    ProviderUnavailableError,
)


async def _handle_provider_unavailable(_request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(status_code=status.HTTP_502_BAD_GATEWAY, content={"detail": str(exc)})


async def _handle_provider_not_found(_request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"detail": str(exc)})


async def _handle_insufficient_context(_request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, content={"detail": str(exc)}
    )


def register_error_handlers(app: FastAPI) -> None:
    """Attach every service-layer exception -> HTTP-response mapping to `app`."""
    app.add_exception_handler(ProviderUnavailableError, _handle_provider_unavailable)
    app.add_exception_handler(ProviderNotFoundError, _handle_provider_not_found)
    # `ProviderFetchError` is normally caught internally by
    # `cache_through.fetch_with_cache`, which translates it into a
    # `ProviderUnavailableError` (handled above) or a stale-cache
    # fallback. Operations with no cache to fall back to at all --
    # `SnapTradeService.connect()`'s registration/login calls -- raise it
    # directly instead, so it needs the same 502 mapping here or it would
    # otherwise reach the client as an unhandled 500.
    app.add_exception_handler(ProviderFetchError, _handle_provider_unavailable)
    # The advisor (U8) is never allowed to return a partial/garbled answer
    # on a Claude API failure -- same 502 shape as any other provider.
    app.add_exception_handler(AdvisorUnavailableError, _handle_provider_unavailable)
    app.add_exception_handler(InsufficientContextError, _handle_insufficient_context)
