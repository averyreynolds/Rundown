"""Request-scoped dependencies shared across API routers.

Each `get_<provider>_service` factory is a thin adapter wiring a
request-scoped `CacheRepository` (bound to this request's DB session) and
the lifespan-shared provider client into that provider's service class.
Scheduler jobs (U9) can't use these -- there's no request to inject
through -- so they construct the same service classes directly from the
same constructors instead; this module is a convenience layer over those
constructors, not the only way to build them.
"""

import hmac
from typing import Annotated, Any

import httpx
from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.cache.cache_repository import CacheRepository
from app.core.config import Settings, get_settings
from app.db.session import get_session
from app.services.edgar_service import EdgarService
from app.services.finnhub_service import FinnhubService
from app.services.fmp_service import FmpService
from app.services.snaptrade_service import SnapTradeService

_BEARER_PREFIX = "Bearer "


def require_api_token(
    settings: Annotated[Settings, Depends(get_settings)],
    authorization: Annotated[str | None, Header()] = None,
) -> None:
    """Gate a route behind the shared-secret bearer token.

    This is the backend's actual access-control layer (see the backend
    scaffold plan's Key Technical Decisions): CORS only governs whether a
    *browser* lets calling JavaScript read a cross-origin response, it does
    nothing to stop a non-browser client from reaching the backend directly.
    Applied to every router except ``/health``, ``/docs``, ``/openapi.json``,
    and ``/redoc``.

    Raises:
        HTTPException: 401 if the ``Authorization`` header is missing,
            malformed, or does not match the configured bearer token.
    """
    if authorization is None or not authorization.startswith(_BEARER_PREFIX):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or malformed Authorization header.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    provided_token = authorization.removeprefix(_BEARER_PREFIX)
    expected_token = settings.api_bearer_token.get_secret_value()

    # Constant-time comparison: an ordinary `!=` leaks timing information
    # proportional to the number of matching leading characters.
    if not hmac.compare_digest(provided_token, expected_token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API bearer token.",
            headers={"WWW-Authenticate": "Bearer"},
        )


def get_cache_repository(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> CacheRepository:
    """Build a `CacheRepository` bound to the current request's DB session.

    Shared by every provider service (FMP now; EDGAR/Finnhub/SnapTrade
    next) so none of them constructs its own ad-hoc cache access.
    """
    return CacheRepository(session)


def get_fmp_client(request: Request) -> httpx.AsyncClient:
    """Return the shared FMP `httpx.AsyncClient` the lifespan constructed at startup."""
    return request.app.state.fmp_client  # type: ignore[no-any-return]


def get_fmp_service(
    client: Annotated[httpx.AsyncClient, Depends(get_fmp_client)],
    cache: Annotated[CacheRepository, Depends(get_cache_repository)],
) -> FmpService:
    """Build an `FmpService` from the shared client and a request-scoped cache."""
    return FmpService(client=client, cache=cache)


def get_edgar_client(request: Request) -> httpx.AsyncClient:
    """Return the shared EDGAR `httpx.AsyncClient` (SEC's `User-Agent` baked in at construction)."""
    return request.app.state.edgar_client  # type: ignore[no-any-return]


def get_edgar_service(
    client: Annotated[httpx.AsyncClient, Depends(get_edgar_client)],
    cache: Annotated[CacheRepository, Depends(get_cache_repository)],
) -> EdgarService:
    """Build an `EdgarService` from the shared client and a request-scoped cache."""
    return EdgarService(client=client, cache=cache)


def get_finnhub_client(request: Request) -> httpx.AsyncClient:
    """Return the shared Finnhub `httpx.AsyncClient` the lifespan constructed at startup."""
    return request.app.state.finnhub_client  # type: ignore[no-any-return]


def get_finnhub_service(
    client: Annotated[httpx.AsyncClient, Depends(get_finnhub_client)],
    cache: Annotated[CacheRepository, Depends(get_cache_repository)],
) -> FinnhubService:
    """Build a `FinnhubService` from the shared client and a request-scoped cache."""
    return FinnhubService(client=client, cache=cache)


def get_snaptrade_client(request: Request) -> Any:  # noqa: ANN401
    """Return the shared SnapTrade SDK client the lifespan constructed at startup.

    Typed as `Any` -- see `SnapTradeService`'s docstring for why the SDK's
    own generic type doesn't resolve cleanly under mypy strict mode.
    """
    return request.app.state.snaptrade_client


def get_snaptrade_service(
    client: Annotated[Any, Depends(get_snaptrade_client)],  # noqa: ANN401
    cache: Annotated[CacheRepository, Depends(get_cache_repository)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> SnapTradeService:
    """Build a `SnapTradeService` from the shared client, cache, and DB session.

    Takes `session` directly (unlike the other `get_*_service` factories)
    because `snaptrade_connection` is a durable credential row, not a
    cache entry -- `SnapTradeService` reads/writes it itself rather than
    routing it through `CacheRepository`, which owns `cache_entries` only.
    """
    return SnapTradeService(client=client, cache=cache, session=session)
