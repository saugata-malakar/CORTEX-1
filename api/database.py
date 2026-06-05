"""
Cortex — api/database.py
Async database and cache connection pools.

Uses:
  - SQLAlchemy 2.0 async engine (asyncpg driver)
  - redis.asyncio for non-blocking Redis ops
  - Alembic-compatible Base for schema migrations
"""

import logging
from typing import AsyncGenerator

import redis.asyncio as aioredis
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from api.config import settings

log = logging.getLogger("cortex.db")

# ─── SQLAlchemy setup ────────────────────────────────────────────────────────

class Base(DeclarativeBase):
    """All ORM models inherit from this."""
    pass


_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker | None = None
_redis: aioredis.Redis | None = None


async def init_db() -> None:
    global _engine, _session_factory

    db_url = settings.DATABASE_URL
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql+asyncpg://", 1)
    elif db_url.startswith("postgresql://") and "+asyncpg" not in db_url:
        db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)

    _engine = create_async_engine(
        db_url,
        echo=settings.ENVIRONMENT == "development",
        pool_size=10,           # base connections kept alive
        max_overflow=20,        # extra connections on burst
        pool_timeout=30,        # seconds to wait for a connection
        pool_recycle=1800,      # recycle stale connections every 30 min
        pool_pre_ping=True,     # verify connections before using
    )

    _session_factory = async_sessionmaker(
        _engine,
        class_=AsyncSession,
        expire_on_commit=False,  # prevent lazy-load after commit
        autocommit=False,
        autoflush=False,
    )

    # Create tables for dev (prod uses Alembic migrations)
    if settings.ENVIRONMENT == "development":
        async with _engine.begin() as conn:
            from api import models  # noqa: F401 — ensure models are imported
            await conn.run_sync(Base.metadata.create_all)

    log.info(f"DB pool ready: pool_size=10 max_overflow=20")


async def close_db() -> None:
    global _engine
    if _engine:
        await _engine.dispose()
        log.info("DB pool closed")


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency — yields a transactional session."""
    if _session_factory is None:
        raise RuntimeError("Database not initialised. Call init_db() first.")
    async with _session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


# ─── Redis setup ─────────────────────────────────────────────────────────────

async def init_redis() -> None:
    global _redis
    _redis = aioredis.from_url(
        settings.REDIS_URL,
        password=settings.REDIS_PASSWORD,
        encoding="utf-8",
        decode_responses=True,
        max_connections=50,
        socket_connect_timeout=5,
        socket_timeout=5,
        retry_on_timeout=True,
    )
    # Verify connection
    await _redis.ping()
    log.info("Redis pool ready: max_connections=50")


async def close_redis() -> None:
    global _redis
    if _redis:
        await _redis.aclose()
        log.info("Redis pool closed")


def get_redis() -> aioredis.Redis:
    """FastAPI dependency — returns the shared Redis client."""
    if _redis is None:
        raise RuntimeError("Redis not initialised. Call init_redis() first.")
    return _redis
