"""FastAPI application factory and module-level app instance.

`create_app()` builds the app; the module-level `app = create_app()` at the
bottom of this file is what `uvicorn app.main:app` finds and serves.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from anthropic import AsyncAnthropic
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import APIRouter, Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from snaptrade_client.auth import SnapTradeAuth
from snaptrade_client.client import SnapTrade

from app.api.dependencies import require_api_token
from app.api.error_handlers import register_error_handlers
from app.api.routers import advisor, filings, fundamentals, health, news, portfolio
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.db.session import create_engine, create_session_factory, init_models
from app.scheduler.jobs import register_jobs

_FMP_BASE_URL = "https://financialmodelingprep.com"
_FINNHUB_BASE_URL = "https://finnhub.io"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application startup/shutdown.

    U1 wired up settings + logging; U3 added the DB engine; U5 added the
    shared FMP `httpx.AsyncClient`; U6 added the shared EDGAR client; U7
    added the shared Finnhub client; U4 added the shared SnapTrade SDK
    client; U9 starts the scheduler; U8 adds the shared Anthropic client
    below.

    Teardown is the reverse of startup: the scheduler is stopped *first*
    (waiting for any in-flight job to finish) *before* the HTTP clients
    are closed and the DB engine is disposed, so a mid-flight job never
    touches an already-closed resource during a dev-server restart.
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

    app.state.finnhub_client = httpx.AsyncClient(
        base_url=_FINNHUB_BASE_URL,
        params={"token": settings.finnhub_api_key.get_secret_value()},
    )

    # No `.aclose()` needed at teardown, unlike the httpx clients above:
    # the SDK's async methods open a fresh aiohttp session per call rather
    # than holding one open (see snaptrade_service.py's docstring).
    #
    # `auth=` (not bare `client_id=`/`consumer_key=` kwargs) is required:
    # `Configuration.auth_mode` only gets set from the `auth` object, and
    # the SDK's request-signing hook (`request_after_hook.py`) silently
    # skips computing the request signature entirely when `auth_mode` is
    # `None` -- passing the keys directly still lets the client construct,
    # but every request 403s with "Authentication credentials were not
    # provided" since nothing ever gets signed.
    #
    # `personal_api_key` (not `commercial_api_key`): CLAUDE.md's free-tier
    # table specifies "Personal tier" for SnapTrade, and this matters
    # beyond which auth mode signs the request -- SnapTrade rejects the
    # partner/commercial-tier user-registration endpoint outright for
    # Personal keys (verified live: 400 "registerUser is not available for
    # personal keys"). See `snaptrade_service.py`'s module docstring for
    # the full auth-mode story, including why this app never calls that
    # endpoint at all.
    app.state.snaptrade_client = SnapTrade(
        auth=SnapTradeAuth.personal_api_key(
            consumer_key=settings.snaptrade_consumer_key.get_secret_value(),
            client_id=settings.snaptrade_client_id.get_secret_value(),
        ),
    )

    app.state.claude_client = AsyncAnthropic(api_key=settings.anthropic_api_key.get_secret_value())

    # Started only after every resource the jobs depend on is ready.
    # Single-process/single-worker only (`uvicorn --workers 1`): APScheduler
    # assumes one process, and a multi-worker deployment would create N
    # independent schedulers each refreshing the cache redundantly.
    scheduler = AsyncIOScheduler()
    register_jobs(scheduler, app.state)
    scheduler.start()
    app.state.scheduler = scheduler

    yield

    # Stop the scheduler first and wait for any in-flight job to finish,
    # before the HTTP clients/DB engine it depends on are torn down below.
    # `AsyncIOScheduler.shutdown()` is a plain sync method, not a
    # coroutine, despite the "asyncio" in its name.
    scheduler.shutdown(wait=True)
    await app.state.claude_client.close()
    await app.state.finnhub_client.aclose()
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
    # defense-in-depth, not a substitute for it).
    protected_router = APIRouter(dependencies=[Depends(require_api_token)])
    protected_router.include_router(portfolio.router)
    protected_router.include_router(fundamentals.router)
    protected_router.include_router(filings.router)
    protected_router.include_router(news.router)
    protected_router.include_router(advisor.router)
    app.include_router(protected_router)

    return app


app = create_app()
