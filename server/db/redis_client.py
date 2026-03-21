"""
Redis session store.
Sessions are stored as JSON with a 60-second TTL.
All session keys are prefixed with "session:" to avoid namespace collisions.
"""

from __future__ import annotations

import json
from typing import Any

import redis.asyncio as aioredis

from models.models import SessionState

SESSION_TTL_SECONDS = 60
SESSION_KEY_PREFIX = "session:"


async def create_redis(url: str) -> aioredis.Redis:
    client = aioredis.from_url(url, decode_responses=True)
    await client.ping()
    return client


def _session_key(session_id: str) -> str:
    # Normalize: strip trailing = padding so Android (which adds =) and the
    # extension (which strips =) always resolve to the same Redis key.
    return f"{SESSION_KEY_PREFIX}{session_id.rstrip('=')}"


async def store_session(
    redis: aioredis.Redis,
    session: SessionState,
    ttl: int = SESSION_TTL_SECONDS,
) -> None:
    await redis.setex(
        _session_key(session.session_id),
        ttl,
        session.model_dump_json(),
    )


async def get_session(redis: aioredis.Redis, session_id: str) -> SessionState | None:
    raw = await redis.get(_session_key(session_id))
    if raw is None:
        return None
    return SessionState.model_validate_json(raw)


async def update_session(
    redis: aioredis.Redis,
    session: SessionState,
    ttl: int = SESSION_TTL_SECONDS,
) -> None:
    # Preserve remaining TTL if the key still exists, otherwise use default.
    remaining = await redis.ttl(_session_key(session.session_id))
    effective_ttl = remaining if remaining > 0 else ttl
    await redis.setex(
        _session_key(session.session_id),
        effective_ttl,
        session.model_dump_json(),
    )


async def consume_session(redis: aioredis.Redis, session_id: str) -> bool:
    """
    Atomically mark session as consumed using a Lua script.
    Returns True if the transition succeeded (was 'responded' → 'consumed').
    Returns False if the session was already consumed or does not exist.
    This prevents TOCTOU double-retrieval.
    """
    lua_script = """
        local key = KEYS[1]
        local raw = redis.call('GET', key)
        if not raw then
            return 0
        end
        local data = cjson.decode(raw)
        if data['status'] ~= 'responded' then
            return 0
        end
        data['status'] = 'consumed'
        local ttl = redis.call('TTL', key)
        if ttl < 1 then ttl = 5 end
        redis.call('SETEX', key, ttl, cjson.encode(data))
        return 1
    """
    result = await redis.eval(lua_script, 1, _session_key(session_id))
    return bool(result)


async def delete_session(redis: aioredis.Redis, session_id: str) -> None:
    await redis.delete(_session_key(session_id))
