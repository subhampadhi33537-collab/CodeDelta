"""
CodeDelta backend – FastAPI application factory.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.db.pool import close_db_pool, init_db_pool
from app.routers import auth, health

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle."""
    settings = get_settings()
    # Initialize DB pool if credentials exist
    if settings.DATABASE_URL or settings.DATABASE_HOST:
        try:
            await init_db_pool(settings)
        except Exception as exc:
            logger.warning("Could not initialize DB pool at startup: %s", exc)

    yield

    # Teardown
    try:
        await close_db_pool()
    except Exception as exc:
        logger.warning("Error closing DB pool at shutdown: %s", exc)


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
        lifespan=lifespan,
    )

    # ── Security Headers Middleware ───────────────────────────────────────────
    @app.middleware("http")
    async def add_security_headers(request: Request, call_next) -> Response:
        response: Response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response

    # ── CORS ──────────────────────────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[str(o) for o in settings.ALLOWED_ORIGINS],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Routers ───────────────────────────────────────────────────────────────
    app.include_router(health.router, prefix="/api")
    app.include_router(auth.router, prefix="/api")

    return app


# Top-level app instance – used by uvicorn
app = create_app()
