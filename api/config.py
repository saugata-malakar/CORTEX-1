"""
Cortex — api/config.py
All configuration loaded from environment variables.
Validated at startup — app fails fast if required vars are missing.

Never commit .env to git. Use .env.example as a template.
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── App ──────────────────────────────────────────────────────────────────
    VERSION:     str = "1.4.0"
    ENVIRONMENT: Literal["development", "staging", "production"] = "development"
    DEBUG:       bool = False

    # ── Security ─────────────────────────────────────────────────────────────
    JWT_SECRET:   str = Field(..., min_length=32)
    ALLOWED_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:8000"]

    @field_validator("JWT_SECRET")
    @classmethod
    def jwt_secret_strength(cls, v: str) -> str:
        if len(v) < 32:
            raise ValueError("JWT_SECRET must be at least 32 characters")
        return v

    # ── Database ─────────────────────────────────────────────────────────────
    DATABASE_URL:      str = "postgresql+asyncpg://cortex:cortexpass@postgres:5432/cortex_db"
    DATABASE_URL_SYNC: str = "postgresql+psycopg2://cortex:cortexpass@postgres:5432/cortex_db"
    POSTGRES_USER:     str = "cortex"
    POSTGRES_PASSWORD: str = "cortexpass"
    POSTGRES_DB:       str = "cortex_db"

    # ── Redis ─────────────────────────────────────────────────────────────────
    REDIS_URL:      str = "redis://redis:6379/0"
    REDIS_PASSWORD: str = "redispass"

    # ── AWS / Storage ─────────────────────────────────────────────────────────
    AWS_ACCESS_KEY_ID:     str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    AWS_REGION:            str = "ap-south-1"
    S3_BUCKET:             str = "cortex-inspections"

    # ── Rate limiting ─────────────────────────────────────────────────────────
    RATE_LIMIT_PER_MINUTE: int = 120

    # ── Celery ────────────────────────────────────────────────────────────────
    CELERY_BROKER_URL:  str = "redis://redis:6379/0"
    CELERY_RESULT_URL:  str = "redis://redis:6379/0"

    # ── Observability ─────────────────────────────────────────────────────────
    SENTRY_DSN:       str = ""
    FLOWER_USER:      str = "admin"
    FLOWER_PASSWORD:  str = "flowerpass"
    GRAFANA_USER:     str = "admin"
    GRAFANA_PASSWORD: str = "grafanapass"

    # ── External APIs ─────────────────────────────────────────────────────────
    BLACKBOX_API_ENDPOINT: str = ""
    BLACKBOX_API_KEY:      str = ""


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


settings: Settings = get_settings()
