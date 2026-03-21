"""
Device management handlers.

New device registration requires a signature from an existing device.
This prevents a compromised account credential from registering a rogue device
without physical access to an existing device.
"""

from __future__ import annotations

import base64
import logging
from typing import Annotated
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Request, status

from api.middleware.auth import AuthContext, require_auth
from crypto.keys import verify_device_session_response
from db import postgres as pg
from models.models import DeviceResponse, NewDeviceRequest, NewDeviceResponse, RevokeDeviceRequest

import nacl.signing
import nacl.exceptions

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/devices", tags=["devices"])


@router.get("", response_model=list[DeviceResponse])
async def list_devices(
    request: Request,
    auth: Annotated[AuthContext, Depends(require_auth)],
) -> list[DeviceResponse]:
    pool: asyncpg.Pool = request.app.state.db
    rows = await pg.get_devices_for_account(pool, auth.account_id)
    return [
        DeviceResponse(
            id=row["id"],
            name=row["device_name"],
            type=row["device_type"],
            signing_pub_key=base64.b64encode(row["signing_pub_key"]).decode(),
            is_revoked=row["is_revoked"],
            last_seen=row["last_seen"],
            created_at=row["created_at"],
        )
        for row in rows
    ]


@router.post("/register", response_model=NewDeviceResponse, status_code=status.HTTP_201_CREATED)
async def register_device(
    body: NewDeviceRequest,
    request: Request,
    auth: Annotated[AuthContext, Depends(require_auth)],
) -> NewDeviceResponse:
    """
    Register a new device. The request must be signed by an existing active device.
    This prevents unauthorized device registration even with a stolen JWT.
    """
    pool: asyncpg.Pool = request.app.state.db

    # Verify signing device is active
    signing_device = await pg.get_device(pool, auth.device_id)
    if signing_device is None or signing_device["is_revoked"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Signing device is revoked")

    # Verify Ed25519 signature from the existing device
    # Signed message: new_device_name || new_dh_pub || new_signing_pub
    new_dh_pub = base64.b64decode(body.dh_public_key)
    new_signing_pub = base64.b64decode(body.signing_pub_key)
    sig_bytes = base64.b64decode(body.sig)

    msg = body.name.encode() + new_dh_pub + new_signing_pub
    try:
        verify_key = nacl.signing.VerifyKey(bytes(signing_device["signing_pub_key"]))
        verify_key.verify(msg, sig_bytes)
    except nacl.exceptions.BadSignatureError:
        logger.warning("register_device: invalid signature from device_id=%s", auth.device_id)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid signature")

    device_id = await pg.create_device(
        pool,
        account_id=auth.account_id,
        name=body.name,
        device_type=body.type,
        dh_public_key=new_dh_pub,
        signing_pub_key=new_signing_pub,
    )

    await pg.write_audit_event(
        pool,
        event_type="device_registered",
        account_id=auth.account_id,
        device_id=device_id,
        ip_address=_client_ip(request),
    )

    logger.info("device_registered account_id=%s device_id=%s", auth.account_id, device_id)

    return NewDeviceResponse(device_id=device_id)


@router.post("/{device_id}/revoke")
async def revoke_device(
    device_id: UUID,
    body: RevokeDeviceRequest,
    request: Request,
    auth: Annotated[AuthContext, Depends(require_auth)],
) -> dict:
    """
    Revoke a device. The request must be signed by an active device.
    Revoked devices cannot participate in unlock sessions.
    After revoking, rotate vault keys.
    """
    pool: asyncpg.Pool = request.app.state.db

    # Verify revoking device is active
    revoking_device = await pg.get_device(pool, auth.device_id)
    if revoking_device is None or revoking_device["is_revoked"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Revoking device is itself revoked")

    target_device = await pg.get_device(pool, device_id)
    if target_device is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found")
    if str(target_device["account_id"]) != str(auth.account_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    if target_device["is_revoked"]:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Device already revoked")

    # Verify Ed25519 signature: signed message = "revoke:" || device_id bytes
    sig_bytes = base64.b64decode(body.sig)
    msg = b"revoke:" + device_id.bytes
    try:
        verify_key = nacl.signing.VerifyKey(bytes(revoking_device["signing_pub_key"]))
        verify_key.verify(msg, sig_bytes)
    except nacl.exceptions.BadSignatureError:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid signature")

    await pg.revoke_device(pool, device_id, revoked_by=auth.device_id)

    await pg.write_audit_event(
        pool,
        event_type="device_revoked",
        account_id=auth.account_id,
        device_id=device_id,
        ip_address=_client_ip(request),
        metadata={"revoked_by": str(auth.device_id)},
    )

    logger.info("device_revoked account_id=%s device_id=%s", auth.account_id, device_id)

    return {"status": "ok"}


def _client_ip(request: Request) -> str | None:
    from api.middleware.ratelimit import get_client_ip
    return get_client_ip(request)


@router.patch("/{device_id}/rename")
async def rename_device(
    device_id: UUID,
    request: Request,
    auth: Annotated[AuthContext, Depends(require_auth)],
) -> dict:
    """Rename a device — only the device itself or another device in the same account."""
    import json
    pool: asyncpg.Pool = request.app.state.db

    body = await request.json()
    new_name = (body.get("name") or "").strip()
    if not new_name or len(new_name) > 64:
        raise HTTPException(status_code=400, detail="Name must be 1-64 characters")

    target = await pg.get_device(pool, device_id)
    if target is None:
        raise HTTPException(status_code=404, detail="Device not found")
    if str(target["account_id"]) != str(auth.account_id):
        raise HTTPException(status_code=403, detail="Forbidden")

    await pool.execute(
        "UPDATE devices SET device_name = $1 WHERE id = $2",
        new_name, device_id,
    )
    logger.info("device_renamed account_id=%s device_id=%s", auth.account_id, device_id)
    return {"status": "ok", "name": new_name}
