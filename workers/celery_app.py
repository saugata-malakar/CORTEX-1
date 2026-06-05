"""
Cortex — workers/celery_app.py + workers/tasks.py
Celery configuration and inspection pipeline task.

Queue topology:
  pipeline  → long-running inspection jobs (1-2 per worker to avoid memory pressure)
  default   → short async ops (email sends, webhook notifications)

Task design:
  - Idempotent: safe to retry if interrupted
  - Progress reporting: updates DB + Redis every pipeline stage
  - Structured error handling: known failures get user-friendly messages
  - Result stored in DB, not Celery result backend (avoids Redis bloat)
"""

# ─────────────────────────────────────────────────────────────────────────────
# celery_app.py
# ─────────────────────────────────────────────────────────────────────────────

import os
from celery import Celery

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
REDIS_PASS = os.getenv("REDIS_PASSWORD", "")

if REDIS_PASS:
    broker_url = REDIS_URL.replace("redis://", f"redis://:{REDIS_PASS}@")
    result_backend = broker_url
else:
    broker_url = REDIS_URL
    result_backend = REDIS_URL

celery_app = Celery(
    "cortex",
    broker=broker_url,
    backend=result_backend,
    include=["workers.tasks"],
)

celery_app.conf.update(
    # Serialization
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],

    # Routing
    task_routes={
        "workers.tasks.run_inspection_pipeline": {"queue": "pipeline"},
        "workers.tasks.*": {"queue": "default"},
    },

    # Reliability
    task_acks_late=True,           # ack only after task completes (not on receive)
    task_reject_on_worker_lost=True,
    task_track_started=True,

    # Retries
    task_max_retries=3,
    task_default_retry_delay=30,

    # Timeouts
    task_soft_time_limit=600,      # 10 min soft → raises SoftTimeLimitExceeded
    task_time_limit=660,           # 11 min hard → SIGKILL

    # Result TTL
    result_expires=86400,          # 24 hours in Redis

    # Worker
    worker_prefetch_multiplier=1,  # one task at a time per worker thread
    worker_max_tasks_per_child=50, # restart worker after 50 tasks (memory leak guard)

    # Beat schedule (recurring tasks)
    beat_schedule={
        "cleanup-expired-tokens": {
            "task": "workers.tasks.cleanup_expired_tokens",
            "schedule": 3600,   # every hour
        },
        "refresh-org-stats-cache": {
            "task": "workers.tasks.refresh_org_stats",
            "schedule": 300,    # every 5 min
        },
    },
)
