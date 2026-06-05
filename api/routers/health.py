"""
Cortex — api/routers/health.py
Health and readiness endpoints for load balancers and uptime monitors.

GET /health         → liveness (is the process alive?)
GET /health/ready   → readiness (can it serve traffic? DB + Redis up?)
GET /health/version → build metadata
"""

import time
import logging
from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from api.config import settings
from api.database import get_redis, get_session

log = logging.getLogger("cortex.health")
router = APIRouter()

_start_time = time.time()


@router.get("/health", summary="Liveness probe")
async def liveness():
    """Returns 200 if process is alive. Never fails — no external deps checked."""
    return {"status": "ok", "uptime_seconds": round(time.time() - _start_time)}


@router.get("/health/ready", summary="Readiness probe")
async def readiness(
    db: Annotated[AsyncSession, Depends(get_session)],
):
    """
    Returns 200 only if all critical dependencies are reachable.
    Load balancer sends traffic only when this returns 200.
    """
    checks = {}
    overall = "ok"

    # ── DB check ─────────────────────────────────────────────────────────────
    try:
        t0 = time.perf_counter()
        await db.execute(text("SELECT 1"))
        checks["postgres"] = {
            "status": "ok",
            "latency_ms": round((time.perf_counter() - t0) * 1000, 1),
        }
    except Exception as exc:
        log.error(f"Health: DB unreachable: {exc}")
        checks["postgres"] = {"status": "error", "detail": "unreachable"}
        overall = "degraded"

    # ── Redis check ───────────────────────────────────────────────────────────
    try:
        redis = get_redis()
        t0 = time.perf_counter()
        await redis.ping()
        checks["redis"] = {
            "status": "ok",
            "latency_ms": round((time.perf_counter() - t0) * 1000, 1),
        }
    except Exception as exc:
        log.error(f"Health: Redis unreachable: {exc}")
        checks["redis"] = {"status": "error", "detail": "unreachable"}
        overall = "degraded"

    http_status = 200 if overall == "ok" else 503
    return JSONResponse(
        status_code=http_status,
        content={
            "status": overall,
            "checks": checks,
            "version": settings.VERSION,
            "environment": settings.ENVIRONMENT,
        },
    )


@router.get("/health/version", summary="Build metadata")
async def version():
    return {
        "version":     settings.VERSION,
        "environment": settings.ENVIRONMENT,
        "uptime_s":    round(time.time() - _start_time),
    }
