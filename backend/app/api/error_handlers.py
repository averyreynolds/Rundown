"""Central mapping from service-layer exceptions to typed HTTP responses.

Registered once in `create_app()` so every router (fundamentals, filings,
news, portfolio; advisor next) surfaces provider failures the same way,
per the plan's System-Wide Impact invariant that external failures
"surface as typed HTTP error responses... never raw exceptions/stack
traces" -- without each router repeating its own try/except translation.
"""

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from app.services.errors import (
    NotConnectedError,
    ProviderFetchError,
    ProviderNotFoundError,
    ProviderUnavailableError,
)


async def _handle_provider_unavailable(_request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(status_code=status.HTTP_502_BAD_GATEWAY, content={"detail": str(exc)})


async def _handle_provider_not_found(_request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"detail": str(exc)})


async def _handle_not_connected(_request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(status_code=status.HTTP_409_CONFLICT, content={"detail": str(exc)})


def register_error_handlers(app: FastAPI) -> None:
    """Attach every service-layer exception -> HTTP-response mapping to `app`."""
    app.add_exception_handler(ProviderUnavailableError, _handle_provider_unavailable)
    app.add_exception_handler(ProviderNotFoundError, _handle_provider_not_found)
    app.add_exception_handler(NotConnectedError, _handle_not_connected)
    # `ProviderFetchError` is normally caught internally by
    # `cache_through.fetch_with_cache`, which translates it into a
    # `ProviderUnavailableError` (handled above) or a stale-cache
    # fallback. Operations with no cache to fall back to at all --
    # `SnapTradeService.connect()`'s registration/login calls -- raise it
    # directly instead, so it needs the same 502 mapping here or it would
    # otherwise reach the client as an unhandled 500.
    app.add_exception_handler(ProviderFetchError, _handle_provider_unavailable)
