"""
Cortex — api/main.py
FastAPI application entry point.

Startup order:
  1. Settings loaded from env
  2. Database pool initialised (async SQLAlchemy)
  3. Redis connection pool initialised
  4. Routers registered with /api/v1 prefix
  5. Middleware stack assembled (CORS, auth, rate-limit, prometheus)
  6. Sentry SDK attached
"""

import time
import logging
from contextlib import asynccontextmanager

import sentry_sdk
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration

from api.config import settings
from api.database import init_db, close_db, init_redis, close_redis
from api.routers import health, auth, inspections

log = logging.getLogger("cortex.api")

def _scrub_pii(event, hint):
    """Strip sensitive fields before sending to Sentry."""
    if "request" in event:
        headers = event["request"].get("headers", {})
        for key in ("authorization", "cookie", "x-api-key"):
            if key in headers:
                headers[key] = "[Filtered]"
    return event

# ─── Sentry ──────────────────────────────────────────────────────────────────
if settings.SENTRY_DSN:
    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        environment=settings.ENVIRONMENT,
        release=f"cortex@{settings.VERSION}",
        traces_sample_rate=0.1,
        profiles_sample_rate=0.05,
        integrations=[
            FastApiIntegration(transaction_style="endpoint"),
            SqlalchemyIntegration(),
        ],
        # Never send PII
        send_default_pii=False,
        before_send=_scrub_pii,
    )

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup → yield → shutdown."""
    log.info(f"Cortex API v{settings.VERSION} starting ({settings.ENVIRONMENT})")
    await init_db()
    await init_redis()
    log.info("Database and Redis pools ready")
    yield
    await close_db()
    await close_redis()
    log.info("Cortex API shutdown complete")


# ─── App factory ─────────────────────────────────────────────────────────────
def create_app() -> FastAPI:
    application = FastAPI(
        title="Cortex Structural Intelligence API",
        version=settings.VERSION,
        description="Production API for facade defect detection and inspection management.",
        docs_url="/api/docs" if settings.ENVIRONMENT != "production" else None,
        redoc_url="/api/redoc" if settings.ENVIRONMENT != "production" else None,
        openapi_url="/api/openapi.json" if settings.ENVIRONMENT != "production" else None,
        lifespan=lifespan,
    )

    # ── CORS ─────────────────────────────────────────────────────────────────
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["*"],
    )

    # ── Request timing + request-id middleware ────────────────────────────────
    @application.middleware("http")
    async def add_request_metadata(request: Request, call_next):
        import uuid
        request_id = request.headers.get("x-request-id", str(uuid.uuid4())[:8])
        start = time.perf_counter()
        response: Response = await call_next(request)
        elapsed = round((time.perf_counter() - start) * 1000, 1)
        response.headers["x-request-id"] = request_id
        response.headers["x-response-time-ms"] = str(elapsed)
        log.info(
            f"{request.method} {request.url.path} "
            f"→ {response.status_code} ({elapsed}ms) [{request_id}]"
        )
        return response

    # ── Rate limiting (via Redis sliding window) ──────────────────────────────
    @application.middleware("http")
    async def rate_limit(request: Request, call_next):
        from api.cache import check_rate_limit
        # Skip rate limit for health check and internal calls
        if request.url.path in ("/api/v1/health", "/metrics"):
            return await call_next(request)
        client_ip = request.client.host
        allowed = await check_rate_limit(
            key=f"rl:{client_ip}",
            limit=settings.RATE_LIMIT_PER_MINUTE,
            window_seconds=60,
        )
        if not allowed:
            from fastapi.responses import JSONResponse
            return JSONResponse(
                status_code=429,
                content={"error": {"code": "RATE_LIMIT_EXCEEDED",
                                   "message": "Too many requests. Retry after 60s."}},
                headers={"Retry-After": "60"},
            )
        return await call_next(request)

    # ── Prometheus metrics ────────────────────────────────────────────────────
    Instrumentator(
        should_group_status_codes=True,
        should_ignore_untemplated=True,
        excluded_handlers=["/metrics", "/api/v1/health"],
    ).instrument(application).expose(application, endpoint="/metrics")

    # ── Routers ───────────────────────────────────────────────────────────────
    PREFIX = "/api/v1"
    application.include_router(health.router,      prefix=PREFIX, tags=["system"])
    application.include_router(auth.router,         prefix=PREFIX, tags=["auth"])
    application.include_router(inspections.router,  prefix=PREFIX, tags=["inspections"])

    return application


app = create_app()
