"""
FastAPI application factory.
"""
from __future__ import annotations

import logging
import logging.config
from contextlib import asynccontextmanager

import asyncpg
import redis.asyncio as aioredis
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api.handlers import auth, device, invite, migration, recovery, server, session, vault
from config.settings import Settings
from db.postgres import create_pool
from db.redis_client import create_redis


def configure_logging() -> None:
    logging.config.dictConfig({
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "json": {
                "()": "pythonjsonlogger.jsonlogger.JsonFormatter",
                "format": "%(asctime)s %(levelname)s %(name)s %(message)s",
            }
        },
        "handlers": {
            "stdout": {
                "class": "logging.StreamHandler",
                "formatter": "json",
            }
        },
        "root": {"level": "INFO", "handlers": ["stdout"]},
    })


def create_app(settings: Settings) -> FastAPI:
    configure_logging()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.settings = settings
        app.state.db = await create_pool(settings.database_url)
        app.state.redis = await create_redis(settings.redis_url)
        logging.getLogger(__name__).info("server_startup")
        yield
        await app.state.db.close()
        await app.state.redis.aclose()
        logging.getLogger(__name__).info("server_shutdown")

    app = FastAPI(
        title="fortispass relay",
        version="1.0.0",
        lifespan=lifespan,
        docs_url=None if not settings.self_hosted else "/docs",
        redoc_url=None,
        openapi_url=None if not settings.self_hosted else "/openapi.json",
    )

    # ── Security headers ─────────────────────────────────────────────────────
    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Strict-Transport-Security"] = (
            "max-age=31536000; includeSubDomains; preload"
        )
        response.headers["Content-Security-Policy"] = "default-src 'none'"
        return response

    # ── CORS ─────────────────────────────────────────────────────────────────
    # In production restrict to your specific extension ID:
    # chrome-extension://<extension-id>
    # CORS: Chrome extension service workers don't send Origin headers for fetch(),
    # so CORS is not required for extension→server. We still configure it correctly
    # for any browser-context requests (e.g. options preflight from WebViews).
    # In production, restrict to your specific extension ID via ALLOWED_ORIGINS env var.
    allowed_origins = getattr(settings, "allowed_origins", "*").split(",") if hasattr(settings, "allowed_origins") else ["*"]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["Authorization", "Content-Type"],
        expose_headers=["X-Biokey"],   # required so JS can read response.headers.get('X-Biokey')
        allow_credentials=False,
    )

    # ── Global unhandled exception — no stack traces in responses ────────────
    @app.exception_handler(Exception)
    async def unhandled_exception(request: Request, exc: Exception):
        logging.getLogger(__name__).exception("unhandled_exception")
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error"},
        )

    # ── Routers ──────────────────────────────────────────────────────────────
    prefix = "/api/v1"
    app.include_router(auth.router, prefix=prefix)
    app.include_router(session.router, prefix=prefix)
    app.include_router(vault.router, prefix=prefix)
    app.include_router(device.router, prefix=prefix)
    app.include_router(recovery.router, prefix=prefix)
    app.include_router(invite.router, prefix=prefix)
    app.include_router(migration.router, prefix=prefix)
    app.include_router(server.router, prefix=prefix)
    @app.get("/health")
    async def health():
        from fastapi.responses import JSONResponse
        return JSONResponse({"status": "ok"}, headers={"X-Biokey": "relay"})

    return app
