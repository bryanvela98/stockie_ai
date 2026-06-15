"""
Description: FastAPI application factory.  Creates and configures the app instance,
             registers all routers, configures structured logging, and attaches
             lifespan hooks.  Import `app` from this module to run with uvicorn.
Last Modified By: bvela
Created: 2026-05-22
Last Modified:
    2026-05-22 - File created; registered /health router and structured logging setup.
    2026-06-01 - Registered tickers router with /tickers prefix.
    2026-06-13 - Registered fundamentals router (fundamentals, DCF, peers endpoints).
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI

from app.api.v1.fundamentals import router as fundamentals_router
from app.api.v1.health import router as health_router
from app.api.v1.tickers import router as tickers_router
from app.core.config import get_settings
from app.core.logging import configure_logging

_log = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncIterator[None]:
    """FastAPI lifespan context manager.

    Runs startup logic before yielding, then teardown logic after.
    Add DB pool initialisation, cache warm-up, etc. here in later sprints.
    """
    settings = get_settings()
    _log.info(
        "startup complete",
        version=settings.app_version,
        env=settings.app_env,
        debug=settings.app_debug,
    )
    yield
    _log.info("shutdown complete")


def create_app() -> FastAPI:
    """Construct and configure the FastAPI application instance.

    Returns:
        A fully configured FastAPI app ready to be served by uvicorn.
    """
    settings = get_settings()
    configure_logging(settings)

    application = FastAPI(
        title="Stockie AI API",
        version=settings.app_version,
        description="Market analysis and recommendation engine for US equities and ETFs.",
        docs_url="/docs" if not settings.is_production else None,
        redoc_url="/redoc" if not settings.is_production else None,
        lifespan=lifespan,
    )

    application.include_router(health_router)
    application.include_router(tickers_router, prefix="/tickers")
    application.include_router(fundamentals_router, prefix="/tickers")

    return application


app = create_app()
