"""
Redis-backed rate limiting middleware.

Uses a sliding window counter per (IP, endpoint) pair.
Returns 429 with Retry-After header when limit is exceeded.
"""

from __future__ import annotations

import ipaddress
import logging
import time
from functools import lru_cache

import redis.asyncio as aioredis
from fastapi import HTTPException, Request, status

logger = logging.getLogger(__name__)


@lru_cache(maxsize=32)
def _parse_trusted_networks(csv: str) -> tuple:
    """Parse a comma-separated list of IPs/CIDRs into ip_network objects."""
    result = []
    for part in csv.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            result.append(ipaddress.ip_network(part, strict=False))
        except ValueError:
            logger.warning("trusted_proxy_ips: invalid entry %r — skipped", part)
    return tuple(result)


def _is_trusted_proxy(ip_str: str | None, networks: tuple) -> bool:
    if not ip_str or not networks:
        return False
    try:
        addr = ipaddress.ip_address(ip_str)
        return any(addr in net for net in networks)
    except ValueError:
        return False


def get_client_ip(request: Request) -> str:
    """
    Extract the real client IP.

    X-Forwarded-For is only honoured when the immediate TCP peer
    (request.client.host) is in TRUSTED_PROXY_IPS. If the server is
    directly internet-facing (no proxy configured), XFF is ignored
    entirely — a client cannot spoof its IP by injecting a header.
    """
    settings = getattr(request.app.state, "settings", None)
    trusted_csv = settings.trusted_proxy_ips if settings else ""
    trusted_networks = _parse_trusted_networks(trusted_csv)

    immediate_peer = request.client.host if request.client else None

    if _is_trusted_proxy(immediate_peer, trusted_networks):
        xff = request.headers.get("x-forwarded-for")
        if xff:
            return xff.split(",")[0].strip()

    return immediate_peer or "unknown"


async def check_rate_limit(
    redis: aioredis.Redis,
    key: str,
    limit: int,
    window_seconds: int,
) -> None:
    """
    Sliding window rate limit check.
    Raises HTTP 429 if limit exceeded.
    """
    now = int(time.time())
    window_start = now - window_seconds

    pipe = redis.pipeline()
    # Remove old entries outside the window
    pipe.zremrangebyscore(key, "-inf", window_start)
    # Count remaining entries
    pipe.zcard(key)
    # Add current request
    pipe.zadd(key, {str(now) + f":{id(pipe)}": now})
    # Set expiry
    pipe.expire(key, window_seconds + 1)
    results = await pipe.execute()

    count = results[1]
    if count >= limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded",
            headers={"Retry-After": str(window_seconds)},
        )


def rate_limit(limit: int, window_seconds: int = 60):
    """
    FastAPI dependency factory for per-IP rate limiting.

    Usage:
        @router.post("/endpoint")
        async def handler(
            request: Request,
            _: None = Depends(rate_limit(10, 60)),
            ...
        ):
    """
    async def dependency(request: Request):
        redis: aioredis.Redis = request.app.state.redis
        ip = get_client_ip(request)
        path = request.url.path
        key = f"rl:{path}:{ip}"
        await check_rate_limit(redis, key, limit, window_seconds)

    return dependency


def account_rate_limit(limit: int, window_seconds: int = 3600):
    """
    Per-account rate limiting. Requires auth context already resolved.
    Attach after require_auth in the dependency chain.
    """
    async def dependency(request: Request, account_id: str):
        redis: aioredis.Redis = request.app.state.redis
        path = request.url.path
        key = f"rl_acct:{path}:{account_id}"
        await check_rate_limit(redis, key, limit, window_seconds)

    return dependency
