"""
Session (unlock) handlers — no auth required from the extension.

Security model:
  - session_id is 32 random bytes (256-bit). Unguessable — it IS the credential.
  - POST /session/create    → unauthenticated; session_id is the secret
  - GET  /session/ws/{id}   → unauthenticated; session_id in path is the credential
  - GET  /session/retrieve/{id} → unauthenticated; single-use, atomically consumed
  - POST /session/respond   → REQUIRES Android auth (JWT); verifies Ed25519 sig

Android still authenticates because it's the one writing to the relay.
The extension only reads, using session_id as its bearer credential.

End-to-end encryption (X25519+HKDF+XChaCha20-Poly1305) means the relay
cannot read enc_vault_key even though it serves it unauthenticated.
"""

from __future__ import annotations

import asyncio
import base64
import logging
import time
from typing import Annotated

import asyncpg
import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, HTTPException, Request, WebSocket, WebSocketDisconnect, status

from api.middleware.auth import AuthContext, require_auth, create_vault_token
from api.middleware.ratelimit import rate_limit
from crypto.keys import sign_session_manifest, verify_device_session_response
from db import postgres as pg
from db import redis_client as rc
from models.models import (
    SessionCreateRequest,
    SessionCreateResponse,
    SessionRespondRequest,
    SessionRetrieveResponse,
    SessionState,
)
from ws.hub import hub

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/session", tags=["session"])

SESSION_TIMESTAMP_TOLERANCE_SECONDS = 30


def _b64d(s: str) -> bytes:
    """Decode standard or URL-safe base64, with or without padding."""
    padded = s + "==" * ((4 - len(s) % 4) % 4)
    return base64.urlsafe_b64decode(padded)


@router.post("/create", response_model=SessionCreateResponse)
async def create_session(
    body: SessionCreateRequest,
    request: Request,
    # NO auth dependency — extension has no token
    _: None = Depends(rate_limit(limit=20, window_seconds=3600)),
) -> SessionCreateResponse:
    """
    Extension creates a session. No auth token required.
    Rate-limited by IP to prevent session ID exhaustion.
    """
    settings = request.app.state.settings
    redis: aioredis.Redis = request.app.state.redis

    now = int(time.time())
    if body.expiry < now or body.expiry > now + 300:
        raise HTTPException(status_code=400, detail="Invalid expiry")

    session_id_bytes = _b64d(body.session_id)
    ext_pub_key_bytes = _b64d(body.ext_pub_key)

    existing = await rc.get_session(redis, body.session_id)
    if existing is not None:
        raise HTTPException(status_code=409, detail="Session ID already exists")

    sig_bytes = sign_session_manifest(
        settings.server_signing_key,
        session_id_bytes,
        ext_pub_key_bytes,
        body.expiry,
    )
    server_sig_b64 = base64.b64encode(sig_bytes).decode()

    session = SessionState(
        session_id=body.session_id,
        ext_pub_key=body.ext_pub_key,
        server_sig=server_sig_b64,
        expiry=body.expiry,
        status="pending",
        account_id="",  # unknown until Android responds
    )
    session_ttl = max(60, body.expiry - now + 10)  # keep alive until QR expires + buffer
    await rc.store_session(redis, session, ttl=session_ttl)

    return SessionCreateResponse(
        session_id=body.session_id,
        server_sig=server_sig_b64,
        relay_url=settings.relay_url,
    )


@router.get("/retrieve/{session_id}", response_model=SessionRetrieveResponse)
async def retrieve_session(
    session_id: str,
    request: Request,
    # NO auth — session_id itself is the 256-bit credential
    _: None = Depends(rate_limit(limit=60, window_seconds=60)),
) -> SessionRetrieveResponse:
    """
    Extension retrieves enc_vault_key + enc_vault_blob. Single-use — atomically consumed.
    session_id (32 random bytes) is the only credential needed.
    The response is useless without the extension's ephemeral private key.
    """
    redis: aioredis.Redis = request.app.state.redis
    pool: asyncpg.Pool = request.app.state.db

    session = await rc.get_session(redis, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    if session.status != "responded":
        raise HTTPException(status_code=404, detail="Session not yet responded")

    consumed = await rc.consume_session(redis, session_id)
    if not consumed:
        raise HTTPException(status_code=409, detail="Session already consumed")

    # Also fetch and include the vault blob so the extension can decrypt it
    # without needing a separate auth token.
    enc_vault_blob_b64 = None
    vault_version = None
    try:
        from uuid import UUID
        account_id = UUID(session.account_id)
        row = await pg.get_vault(pool, account_id)
        if row is not None:
            enc_vault_blob_b64 = base64.b64encode(row["encrypted_blob"]).decode()
            vault_version = row["version"]
    except Exception:
        pass  # Non-fatal: extension can still decrypt credentials, vault will just be empty

    vault_token = None
    try:
        vault_token = create_vault_token(UUID(session.account_id))
    except Exception:
        pass

    return SessionRetrieveResponse(
        dev_eph_pub=session.dev_eph_pub,
        enc_vault_key=session.enc_vault_key,
        sig=session.device_sig,
        enc_vault_blob=enc_vault_blob_b64,
        vault_version=vault_version,
        vault_token=vault_token,
    )



@router.post("/ack/{session_id}")
async def ack_session(
    session_id: str,
    request: Request,
    # No auth — session_id (256-bit random) is the credential, same model as /retrieve
    _: None = Depends(rate_limit(limit=60, window_seconds=60)),
) -> dict:
    """
    Android calls this immediately after QR scan validates (before biometric prompt).
    Notifies the extension to hide the QR and show 'waiting for biometric'.
    session_id in path is the only credential needed — it's 256-bit random.
    """
    redis: aioredis.Redis = request.app.state.redis
    session = await rc.get_session(redis, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found or expired")
    if session.status != "pending":
        raise HTTPException(status_code=409, detail="Session not in pending state")
    await hub.notify(session_id, {"event": "biometric_started"})
    return {"status": "ok"}


@router.post("/respond")
async def respond_to_session(
    body: SessionRespondRequest,
    request: Request,
    # Android MUST authenticate — it's writing to the relay
    auth: Annotated[AuthContext, Depends(require_auth)],
) -> dict:
    """
    Android delivers enc_vault_key after biometric auth.
    Verifies device Ed25519 signature before storing.
    """
    pool: asyncpg.Pool = request.app.state.db
    redis: aioredis.Redis = request.app.state.redis

    now = int(time.time())
    if abs(body.timestamp - now) > SESSION_TIMESTAMP_TOLERANCE_SECONDS:
        raise HTTPException(status_code=400, detail="Timestamp out of range")

    session = await rc.get_session(redis, body.session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found or expired")
    if session.status != "pending":
        raise HTTPException(status_code=409, detail="Session already used")
    if session.expiry <= now:
        raise HTTPException(status_code=410, detail="Session expired")

    device = await pg.get_device(pool, body.device_id)
    if device is None or device["is_revoked"]:
        raise HTTPException(status_code=403, detail="Device not found or revoked")
    if str(device["account_id"]) != str(auth.account_id):
        raise HTTPException(status_code=403, detail="Device does not belong to account")

    valid = verify_device_session_response(
        device_signing_pub_key_bytes=bytes(device["signing_pub_key"]),
        session_id_bytes=_b64d(body.session_id),
        dev_eph_pub_bytes=_b64d(body.dev_eph_pub),
        enc_vault_key_bytes=_b64d(body.enc_vault_key),
        timestamp=body.timestamp,
        signature_bytes=_b64d(body.sig),
    )
    if not valid:
        await pg.write_audit_event(pool, event_type="unlock_failed",
            account_id=auth.account_id, device_id=body.device_id,
            ip_address=_client_ip(request), metadata={"reason": "invalid_signature"})
        raise HTTPException(status_code=403, detail="Invalid signature")

    # Tag session with account so retrieve can't be called before respond
    session.status = "responded"
    session.account_id = str(auth.account_id)
    session.dev_eph_pub = body.dev_eph_pub
    session.enc_vault_key = body.enc_vault_key
    session.device_sig = body.sig
    await rc.update_session(redis, session)

    await pg.update_device_last_seen(pool, body.device_id)
    await pg.write_audit_event(pool, event_type="unlock_success",
        account_id=auth.account_id, device_id=body.device_id,
        ip_address=_client_ip(request))

    await hub.notify(body.session_id, {"event": "session_responded"})
    logger.info("session_responded account_id=%s", auth.account_id)
    return {"status": "ok"}


@router.delete("/{session_id}")
async def delete_session(
    session_id: str,
    request: Request,
) -> dict:
    """
    Extension or Android cancels a session.
    - Extension cancel: session is pending, user closed popup
    - Android cancel: biometric failed/cancelled, sends biometric_failed event first
    No auth needed — session_id is the credential.
    """
    redis: aioredis.Redis = request.app.state.redis
    event_type = request.query_params.get("reason", "cancelled")
    session = await rc.get_session(redis, session_id)
    # Only cancel pending sessions — don't let anyone cancel a responded session
    if session and session.status == "pending":
        if event_type == "biometric_failed":
            await hub.notify(session_id, {"event": "biometric_failed"})
        await rc.delete_session(redis, session_id)
        await hub.cleanup_session(session_id)
    return {"status": "ok"}


@router.websocket("/ws/{session_id}")
async def session_websocket(websocket: WebSocket, session_id: str):
    """
    Extension subscribes here after displaying QR.
    No auth handshake — session_id in the path is the credential.

    IMPORTANT: accept() MUST come before any close(). Closing an unaccepted
    WebSocket drops the TCP connection without completing the upgrade handshake,
    which the browser reports as code 1006 (abnormal closure).
    """
    await websocket.accept()

    redis: aioredis.Redis = websocket.app.state.redis

    # Retry to handle the race between POST /create and WS connect
    session = None
    for _ in range(10):
        session = await rc.get_session(redis, session_id)
        if session is not None:
            break
        await asyncio.sleep(0.1)

    if session is None or session.status != "pending":
        await websocket.close(code=4004, reason="Session not found")
        return

    await hub.register(session_id, websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        await hub.disconnect(session_id)


def _client_ip(request: Request) -> str | None:
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else None
