"""
Cortex — api/cache.py
Redis caching layer.

Patterns:
  @cache(ttl=300, key_fn=...)   → decorator for route handlers
  invalidate_pattern(...)       → bust a key namespace
  check_rate_limit(...)         → sliding-window rate limiter
  acquire_lock / release_lock   → distributed lock for idempotent ops
"""

import asyncio
import functools
import hashlib
import json
import logging
from typing import Any, Callable

import redis.asyncio as aioredis

from api.database import get_redis

log = logging.getLogger("cortex.cache")

# ─── Serialization ───────────────────────────────────────────────────────────

def _serialize(value: Any) -> str:
    return json.dumps(value, default=str)


def _deserialize(raw: str) -> Any:
    return json.loads(raw)


# ─── Core get/set ────────────────────────────────────────────────────────────

async def cache_get(key: str) -> Any | None:
    redis: aioredis.Redis = get_redis()
    try:
        raw = await redis.get(key)
        if raw is None:
            return None
        return _deserialize(raw)
    except Exception as exc:
        log.warning(f"Cache GET failed for key={key}: {exc}")
        return None   # fail open — never block on cache miss


async def cache_set(key: str, value: Any, ttl: int = 300) -> bool:
    redis: aioredis.Redis = get_redis()
    try:
        await redis.setex(key, ttl, _serialize(value))
        return True
    except Exception as exc:
        log.warning(f"Cache SET failed for key={key}: {exc}")
        return False


async def cache_delete(key: str) -> None:
    redis: aioredis.Redis = get_redis()
    try:
        await redis.delete(key)
    except Exception as exc:
        log.warning(f"Cache DELETE failed for key={key}: {exc}")


async def invalidate_pattern(pattern: str) -> int:
    """
    Delete all keys matching a glob pattern.
    Use sparingly — SCAN is O(N).
    Pattern examples:
      "inspection:org:abc123:*"
      "building:*"
    """
    redis: aioredis.Redis = get_redis()
    deleted = 0
    try:
        async for key in redis.scan_iter(match=pattern, count=100):
            await redis.delete(key)
            deleted += 1
        if deleted:
            log.debug(f"Invalidated {deleted} keys matching '{pattern}'")
    except Exception as exc:
        log.warning(f"Cache invalidation failed for pattern={pattern}: {exc}")
    return deleted


# ─── Cache decorator ─────────────────────────────────────────────────────────

def cache(
    ttl: int = 300,
    key_prefix: str = "",
    key_fn: Callable | None = None,
):
    """
    Decorator for async functions. Caches the return value in Redis.

    Usage:
        @cache(ttl=60, key_prefix="buildings")
        async def get_building(building_id: str, org_id: str) -> dict:
            ...

    The cache key is built from:
      key_prefix + SHA-256 of serialized kwargs if key_fn is None
      key_fn(kwargs) if provided.

    Bypass cache on per-call basis: pass cache_bypass=True to the function.
    """
    def decorator(fn: Callable) -> Callable:
        @functools.wraps(fn)
        async def wrapper(*args, bypass_cache: bool = False, **kwargs):
            # Build cache key
            if key_fn:
                cache_key = f"{key_prefix}:{key_fn(**kwargs)}"
            else:
                key_hash = hashlib.sha256(
                    json.dumps(kwargs, sort_keys=True, default=str).encode()
                ).hexdigest()[:16]
                func_name = fn.__qualname__.replace(".", "_")
                cache_key = f"{key_prefix}:{func_name}:{key_hash}"

            # Try cache (unless bypassed)
            if not bypass_cache:
                cached = await cache_get(cache_key)
                if cached is not None:
                    log.debug(f"Cache HIT: {cache_key}")
                    return cached

            # Execute function
            result = await fn(*args, **kwargs)

            # Store result
            if result is not None:
                await cache_set(cache_key, result, ttl=ttl)
                log.debug(f"Cache SET: {cache_key} ttl={ttl}s")

            return result
        return wrapper
    return decorator


# ─── Sliding-window rate limiter ─────────────────────────────────────────────

async def check_rate_limit(
    key: str,
    limit: int,
    window_seconds: int = 60,
) -> bool:
    """
    Sliding window rate limiter using Redis sorted sets.
    Returns True if request is allowed, False if limit exceeded.

    Algorithm:
      1. Remove entries older than (now - window)
      2. Count remaining entries
      3. If count < limit: add entry, return True
      4. Else: return False
    """
    redis: aioredis.Redis = get_redis()
    try:
        import time
        now = time.time()
        window_start = now - window_seconds

        pipe = redis.pipeline(transaction=True)
        pipe.zremrangebyscore(key, "-inf", window_start)
        pipe.zcard(key)
        pipe.zadd(key, {str(now): now})
        pipe.expire(key, window_seconds + 1)
        results = await pipe.execute()

        current_count = results[1]
        return current_count < limit

    except Exception as exc:
        log.warning(f"Rate limit check failed for key={key}: {exc}")
        return True   # fail open — don't block requests on Redis failure


# ─── Distributed lock ────────────────────────────────────────────────────────

async def acquire_lock(
    lock_name: str,
    ttl_seconds: int = 30,
    retry_count: int = 3,
    retry_delay: float = 0.5,
) -> str | None:
    """
    Acquire a distributed lock. Returns lock token if acquired, None otherwise.
    Use for idempotent operations (e.g. prevent duplicate inspection submissions).

    Usage:
        token = await acquire_lock("submit:building:abc123")
        if not token:
            raise HTTPException(409, "Operation already in progress")
        try:
            ...
        finally:
            await release_lock("submit:building:abc123", token)
    """
    redis: aioredis.Redis = get_redis()
    token = secrets_token()
    full_key = f"lock:{lock_name}"

    for attempt in range(retry_count):
        acquired = await redis.set(full_key, token, nx=True, ex=ttl_seconds)
        if acquired:
            log.debug(f"Lock acquired: {full_key}")
            return token
        if attempt < retry_count - 1:
            await asyncio.sleep(retry_delay)

    log.debug(f"Lock NOT acquired: {full_key} (already held)")
    return None


async def release_lock(lock_name: str, token: str) -> bool:
    """Release a lock only if we still hold it (compare-and-delete via Lua)."""
    redis: aioredis.Redis = get_redis()
    full_key = f"lock:{lock_name}"

    lua_script = """
    if redis.call("get", KEYS[1]) == ARGV[1] then
        return redis.call("del", KEYS[1])
    else
        return 0
    end
    """
    try:
        result = await redis.eval(lua_script, 1, full_key, token)
        return bool(result)
    except Exception as exc:
        log.warning(f"Lock release failed: {full_key}: {exc}")
        return False


def secrets_token() -> str:
    import secrets
    return secrets.token_hex(16)


# ─── Convenience keys ─────────────────────────────────────────────────────────

def key_inspection_result(inspection_id: str) -> str:
    return f"inspection:result:{inspection_id}"


def key_building_list(org_id: str) -> str:
    return f"buildings:{org_id}:list"


def key_job_status(job_id: str) -> str:
    return f"job:status:{job_id}"


def key_org_stats(org_id: str) -> str:
    return f"org:{org_id}:stats"
