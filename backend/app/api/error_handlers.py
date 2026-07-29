"""Central mapping from service-layer exceptions to typed HTTP responses.

Registered once in `create_app()` so every router (fundamentals now;
filings/news/portfolio/advisor next) surfaces provider failures the same
way, per the plan's System-Wide Impact invariant that external failures
"surface as typed HTTP error responses... never raw exceptions/stack
traces" -- without each router repeating its own try/except translation.
"""

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from app.services.errors import ProviderNotFoundError, ProviderUnavailableError


async def _handle_provider_unavailable(
    _request: Request, exc: Exception
) -> JSONResponse:
    return JSONResponse(status_code=status.HTTP_502_BAD_GATEWAY, content={"detail": str(exc)})


async def _handle_provider_not_found(_request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"detail": str(exc)})


def register_error_handlers(app: FastAPI) -> None:
    """Attach every service-layer exception -> HTTP-response mapping to `app`."""
    app.add_exception_handler(ProviderUnavailableError, _handle_provider_unavailable)
    app.add_exception_handler(ProviderNotFoundError, _handle_provider_not_found)
