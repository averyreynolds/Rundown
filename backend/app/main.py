"""FastAPI application factory and module-level app instance.

`create_app()` builds the app; the module-level `app = create_app()` at the
bottom of this file is what `uvicorn app.main:app` finds and serves.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from fastapi import APIRouter, Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.dependencies import require_api_token
from app.api.error_handlers import register_error_handlers
from app.api.routers import filings, fundamentals, health
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.db.session import create_engine, create_session_factory, init_models

_FMP_BASE_URL = "https://financialmodelingprep.com"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application startup/shutdown.

    U1 wired up settings + logging; U3 added the DB engine; U5 added the
    shared FMP `httpx.AsyncClient`; U6 adds the shared EDGAR client below.
    Later units extend this same function to construct further shared
    resources on startup and tear them down (in reverse order) on
    shutdown:

      - U4/U7/U8: construct one long-lived shared `httpx.AsyncClient` (or
        SDK client) per remaining provider -- SnapTrade, Finnhub,
        Anthropic -- and store each on `app.state`.
      - U9: start APScheduler's `AsyncIOScheduler` *after* the resources
        above are ready; on shutdown, stop the scheduler *first* (waiting
        for any in-flight job) *before* disposing the DB engine or closing
        the HTTP clients, so a mid-flight job never touches an
        already-closed resource during a dev-server restart.
    """
    settings = get_settings()
    configure_logging(settings.secret_values(), log_level=settings.log_level)

    engine = create_engine(settings.database_url)
    await init_models(engine)
    app.state.session_factory = create_session_factory(engine)

    # One long-lived client per provider, per the Key Technical Decision on
    # shared clients: the API key is a default query param here, not
    # repeated (or accidentally omitted) at every call site.
    app.state.fmp_client = httpx.AsyncClient(
        base_url=_FMP_BASE_URL,
        params={"apikey": settings.fmp_api_key.get_secret_value()},
    )

    # SEC requires a descriptive User-Agent (app name + a real contact
    # email) on every data.sec.gov request or it returns 403. Baked in
    # once here, at the header level, rather than per call site, so it's
    # structurally impossible for a future EDGAR call to forget it.
    app.state.edgar_client = httpx.AsyncClient(
        headers={"User-Agent": settings.sec_edgar_user_agent},
    )

    yield

    # Teardown is the reverse of startup. Once U9's scheduler exists, its
    # shutdown must be awaited *before* the clients/engine below are torn
    # down, so an in-flight job never touches an already-closed resource.
    await app.state.edgar_client.aclose()
    await app.state.fmp_client.aclose()
    await engine.dispose()


def create_app() -> FastAPI:
    """Build and configure the FastAPI application (the "app factory")."""
    settings = get_settings()

    app = FastAPI(
        title="Rundown Backend",
        description=(
            "Portfolio intelligence dashboard backend: read-only brokerage "
            "holdings, fundamentals, filings, news, and a grounded, "
            "citation-backed AI advisor. See backend/README.md for setup."
        ),
        version="0.1.0",
        lifespan=lifespan,
    )

    # Secondary, browser-only restriction -- NOT the access-control layer.
    # See `require_api_token` below for the actual gate.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_error_handlers(app)

    # `/health` is registered directly on `app` -- deliberately exempt from
    # the bearer-token gate as an unauthenticated liveness probe. FastAPI's
    # own `/docs`, `/openapi.json`, and `/redoc` are exempt by construction:
    # they're built into `app` itself, never added to `protected_router`.
    app.include_router(health.router)

    # Every other router belongs on `protected_router`, not directly on
    # `app`, so it automatically inherits the shared-secret bearer-token
    # gate -- the backend's real access-control layer (CORS above is
    # defense-in-depth, not a substitute for it). Later units add their
    # router here, e.g.:
    #   protected_router.include_router(portfolio.router)
    protected_router = APIRouter(dependencies=[Depends(require_api_token)])
    protected_router.include_router(fundamentals.router)
    protected_router.include_router(filings.router)
    app.include_router(protected_router)

    return app


app = create_app()
