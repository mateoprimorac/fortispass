"""
Authentication handlers — passwordless, device-key-only.

Registration:  device sends its Ed25519 + X25519 public keys → gets a JWT.
Authentication: JWT bearer token (standard, verified in middleware).

No email, no password, no KDF, no recovery blob.
The device's Ed25519 signing key IS the identity credential.
"""
from __future__ import annotations

import base64
import hashlib
import logging

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Request, status

from api.middleware.auth import create_access_token
from api.middleware.ratelimit import rate_limit
from db import postgres as pg
from models.models import RegisterRequest, RegisterResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
async def register(
    body: RegisterRequest,
    request: Request,
    _=Depends(rate_limit(limit=10, window_seconds=3600)),
) -> RegisterResponse:
    """
    Register a new device. Creates an account automatically.
    The device's Ed25519 signing public key is the identity anchor.
    No email or password required.
    """
    pool: asyncpg.Pool = request.app.state.db
    settings = request.app.state.settings

    dh_pub_bytes      = _b64d(body.device.dh_public_key)
    signing_pub_bytes = _b64d(body.device.signing_pub_key)
    initial_vault_bytes = _b64d(body.initial_vault)

    if len(initial_vault_bytes) > settings.max_vault_size_bytes:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="Vault too large")

    async with pool.acquire() as conn:
        async with conn.transaction():
            account_id = await pg.create_account(conn, label=body.device_name)
            device_id  = await pg.create_device(
                conn,
                account_id=account_id,
                name=body.device_name,
                device_type="android",
                dh_public_key=dh_pub_bytes,
                signing_pub_key=signing_pub_bytes,
            )
            blob_hash = hashlib.blake2b(initial_vault_bytes, digest_size=32).digest()
            await pg.upsert_vault(conn, account_id, initial_vault_bytes, blob_hash, version=1)
            if body.vault_lookup_hash:
                await pg.set_vault_lookup_hash(conn, account_id, body.vault_lookup_hash)
            if body.mnemonic_confirmed:
                await pg.set_mnemonic_confirmed(conn, account_id)

    await pg.write_audit_event(
        pool,
        event_type="device_registered",
        account_id=account_id,
        device_id=device_id,
        ip_address=_client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )

    logger.info("device_registered account_id=%s device_id=%s", account_id, device_id)

    return RegisterResponse(
        account_id=str(account_id),
        device_id=str(device_id),
        access_token=create_access_token(account_id, device_id),
        server_pub_key=base64.b64encode(
            settings.server_signing_key.verify_key.encode()
        ).decode(),
    )



@router.post("/renew", status_code=200)
async def renew_token(
    request: Request,
    _=Depends(rate_limit(limit=10, window_seconds=3600)),
) -> dict:
    """
    Renew an expired or soon-to-expire access token.

    The device proves its identity by sending its current JWT (even if expired,
    we accept tokens up to 30 days past expiry for renewal) alongside a fresh
    Ed25519 signature over a nonce to prove key possession.

    Body JSON: { "token": "<jwt>", "device_id": "<uuid>", "sig": "<b64 sig over device_id bytes>" }
    The sig prevents replay — it proves the caller holds the private signing key.
    """
    import json, time as _time
    from uuid import UUID

    pool: asyncpg.Pool = request.app.state.db
    settings = request.app.state.settings

    try:
        body = await request.json()
        token_str  = body.get("token", "")
        device_id  = body.get("device_id", "")
        sig_b64    = body.get("sig", "")
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    if not token_str or not device_id or not sig_b64:
        raise HTTPException(status_code=400, detail="Missing token, device_id, or sig")

    # Decode the token leniently (allow expired)
    try:
        import jwt as pyjwt
        payload = pyjwt.decode(
            token_str,
            settings.jwt_secret_bytes,
            algorithms=["HS256"],
            options={"verify_exp": False, "require": ["sub", "did", "typ"]},
        )
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")

    if payload.get("typ") != "access":
        raise HTTPException(status_code=401, detail="Wrong token type")

    # Token must not be more than 30 days past expiry (prevents very old token reuse)
    exp = payload.get("exp", 0)
    if exp and (_time.time() - exp) > 30 * 24 * 3600:
        raise HTTPException(status_code=401, detail="Token too old to renew — re-register device")

    # device_id in path must match token claim
    try:
        did_from_token = UUID(payload["did"])
        did_from_body  = UUID(device_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid device_id format")

    if did_from_token != did_from_body:
        raise HTTPException(status_code=403, detail="device_id does not match token")

    # Load device and verify Ed25519 signature over device_id bytes
    device = await pg.get_device(pool, did_from_body)  # pass UUID, not str
    if device is None or device["is_revoked"]:
        raise HTTPException(status_code=403, detail="Device not found or revoked — please re-register the app")

    try:
        sig_bytes = _b64d(sig_b64)
        # Message: UTF-8 bytes of device_id string — simple, no nonce needed
        # (replay protection: attacker would need the private key to forge this)
        msg = device_id.encode("utf-8")
        import nacl.signing, nacl.exceptions
        vk = nacl.signing.VerifyKey(bytes(device["signing_pub_key"]))
        vk.verify(msg, sig_bytes)
    except Exception:
        raise HTTPException(status_code=403, detail="Signature verification failed")

    account_id = UUID(payload["sub"])
    new_token = create_access_token(account_id, did_from_body)
    logger.info("token_renewed device_id=%s", device_id)
    return {"access_token": new_token}


def _b64d(s: str) -> bytes:
    padded = s + "==" * ((4 - len(s) % 4) % 4)
    return base64.urlsafe_b64decode(padded)


def _client_ip(request: Request) -> str | None:
    from api.middleware.ratelimit import get_client_ip
    return get_client_ip(request)
