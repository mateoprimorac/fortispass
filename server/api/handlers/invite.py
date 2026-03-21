"""
Device invite endpoints — "Add Device" pairing flow.

Protocol:
  1. POST /invite/create      (Device A, authenticated)
     → stores invite, returns token + Device A's DH pub

  2. POST /invite/accept       (Device B, unauthenticated)
     → stores Device B's DH+signing pub; checks device limit
     → if at limit: returns 409 with device list for kick-out
     → if ok:       returns 200 "accepted"

  3. GET  /invite/{token}/status  (Device A polls, authenticated)
     → returns state + joiner_dh_pub once accepted

  4. POST /invite/deliver      (Device A, authenticated)
     → stores AES-GCM(sharedKey, vaultKey) encrypted by Device A

  5. POST /invite/complete     (Device B, unauthenticated)
     → creates device record on server, issues JWT, returns auth token
     → invite state → consumed

Security:
  - Token is 32 random bytes (256-bit) — unguessable
  - Vault key is encrypted with ECDH(A_priv, B_pub) shared secret
  - Server never sees the vault key in plaintext
  - Invite expires after 5 minutes
"""
from __future__ import annotations

import base64
import logging
import os
from datetime import datetime, timezone
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status

from api.middleware.auth import AuthContext, create_access_token, require_auth
from api.middleware.ratelimit import rate_limit
from db import postgres as pg
from models.models import (
    DeviceInfo,
    InviteAcceptRequest,
    InviteAcceptResponse,
    InviteCompleteRequest,
    InviteCreateResponse,
    InviteDeliverRequest,
    InviteStatusResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/invite", tags=["invite"])


def _b64u(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def _b64d(s: str) -> bytes:
    padded = s + "==" * ((4 - len(s) % 4) % 4)
    return base64.urlsafe_b64decode(padded)


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ── 1. Create invite ──────────────────────────────────────────────────────────

@router.post("/create", response_model=InviteCreateResponse, status_code=201)
async def create_invite(
    request: Request,
    auth: Annotated[AuthContext, Depends(require_auth)],
    _: None = Depends(rate_limit(limit=10, window_seconds=3600)),
) -> InviteCreateResponse:
    """Device A calls this to generate an invite QR."""
    pool = request.app.state.db

    device = await pg.get_device(pool, auth.device_id)
    if device is None or device["is_revoked"]:
        raise HTTPException(403, "Device revoked")

    token = _b64u(os.urandom(32))
    inviting_dh_pub = bytes(device["dh_public_key"])

    invite = await pg.get_invite(pool, token)
    # Vanishingly unlikely collision — just regenerate
    while invite is not None:
        token = _b64u(os.urandom(32))
        invite = await pg.get_invite(pool, token)

    await pg.create_invite(pool, token, auth.account_id, auth.device_id, inviting_dh_pub)

    # Fetch expires_at from DB
    row = await pg.get_invite(pool, token)
    logger.info("invite_created account_id=%s", auth.account_id)

    return InviteCreateResponse(
        token=token,
        expires_at=row["expires_at"],
        inviting_dh_pub=_b64u(inviting_dh_pub),
    )


# ── 2. Accept invite ──────────────────────────────────────────────────────────

@router.post("/accept", response_model=InviteAcceptResponse)
async def accept_invite(
    body: InviteAcceptRequest,
    request: Request,
    _: None = Depends(rate_limit(limit=20, window_seconds=3600)),
) -> InviteAcceptResponse:
    """Device B calls this after scanning the QR."""
    pool     = request.app.state.db
    settings = request.app.state.settings

    invite = await pg.get_invite(pool, body.token)
    if invite is None:
        raise HTTPException(404, "Invite not found")
    if invite["state"] != "pending":
        raise HTTPException(409, "Invite already used")
    if invite["expires_at"].replace(tzinfo=timezone.utc) < _now():
        raise HTTPException(410, "Invite expired")

    account_id = invite["account_id"]
    max_devices = getattr(settings, "max_devices_per_vault", 3)
    active = await pg.count_active_devices(pool, account_id)

    if active >= max_devices:
        # At limit — return device list so user can pick one to kick
        if body.kick_device_id is None:
            devices_rows = await pg.get_active_devices_for_account(pool, account_id)
            return InviteAcceptResponse(
                status="at_limit",
                devices=[
                    DeviceInfo(
                        id=str(r["id"]),
                        name=r["device_name"],
                        created_at=r["created_at"],
                    )
                    for r in devices_rows
                ],
            )
        # Kick the specified device
        try:
            kick_id = UUID(body.kick_device_id)
        except ValueError:
            raise HTTPException(400, "Invalid kick_device_id")

        kick_dev = await pg.get_device(pool, kick_id)
        if kick_dev is None or str(kick_dev["account_id"]) != str(account_id):
            raise HTTPException(403, "Cannot kick device from another account")
        await pg.revoke_device(pool, kick_id, revoked_by=invite["inviting_device"])
        logger.info("device_kicked_for_invite account_id=%s kicked=%s", account_id, kick_id)

    joiner_dh   = _b64d(body.joiner_dh_pub)
    joiner_sign = _b64d(body.joiner_sign_pub)

    await pg.set_invite_accepted(pool, body.token, joiner_dh, joiner_sign, body.device_name)
    logger.info("invite_accepted account_id=%s", account_id)

    return InviteAcceptResponse(status="accepted")


# ── 3. Poll status ────────────────────────────────────────────────────────────

@router.get("/{token}/status", response_model=InviteStatusResponse)
async def invite_status(
    token: str,
    request: Request,
    auth: Annotated[AuthContext, Depends(require_auth)],
) -> InviteStatusResponse:
    """Device A polls this to know when Device B has accepted and to get B's DH pub."""
    pool = request.app.state.db

    invite = await pg.get_invite(pool, token)
    if invite is None:
        raise HTTPException(404, "Invite not found")
    if str(invite["account_id"]) != str(auth.account_id):
        raise HTTPException(403, "Forbidden")
    if invite["expires_at"].replace(tzinfo=timezone.utc) < _now():
        raise HTTPException(410, "Invite expired")

    inviting_dh_pub_b64 = (
        _b64u(bytes(invite["inviting_dh_pub"]))
        if invite["inviting_dh_pub"] else None
    )
    joiner_dh_pub = (
        _b64u(bytes(invite["joiner_dh_pub"]))
        if invite["joiner_dh_pub"] else None
    )
    enc_key = (
        base64.b64encode(bytes(invite["encrypted_vault_key"])).decode()
        if invite["encrypted_vault_key"] else None
    )

    return InviteStatusResponse(
        state=invite["state"],
        joiner_dh_pub=joiner_dh_pub,
        inviting_dh_pub=inviting_dh_pub_b64,
        encrypted_vault_key=enc_key,
    )


# ── 4. Deliver encrypted vault key ────────────────────────────────────────────

@router.post("/deliver")
async def deliver_vault_key(
    body: InviteDeliverRequest,
    request: Request,
    auth: Annotated[AuthContext, Depends(require_auth)],
) -> dict:
    """Device A posts the vault key encrypted with ECDH(A_priv, B_pub)."""
    pool = request.app.state.db

    invite = await pg.get_invite(pool, body.token)
    if invite is None:
        raise HTTPException(404, "Invite not found")
    if str(invite["account_id"]) != str(auth.account_id):
        raise HTTPException(403, "Forbidden")
    if invite["state"] != "accepted":
        raise HTTPException(409, f"Invite not in accepted state (is: {invite['state']})")
    if invite["expires_at"].replace(tzinfo=timezone.utc) < _now():
        raise HTTPException(410, "Invite expired")

    enc_bytes = base64.b64decode(body.encrypted_vault_key)
    await pg.set_invite_delivered(pool, body.token, enc_bytes)
    logger.info("invite_delivered account_id=%s", auth.account_id)
    return {"status": "delivered"}


# ── 5. Complete — Device B registers ──────────────────────────────────────────

@router.post("/complete")
async def complete_invite(
    body: InviteCompleteRequest,
    request: Request,
    _: None = Depends(rate_limit(limit=10, window_seconds=3600)),
) -> dict:
    """
    Device B calls this after receiving and decrypting the vault key.
    Creates the device record and returns a JWT.
    """
    pool = request.app.state.db

    invite = await pg.get_invite(pool, body.token)
    if invite is None:
        raise HTTPException(404, "Invite not found")
    if invite["state"] != "delivered":
        raise HTTPException(409, f"Vault key not yet delivered (state: {invite['state']})")
    if invite["expires_at"].replace(tzinfo=timezone.utc) < _now():
        raise HTTPException(410, "Invite expired")

    # Device B already supplied its keys at /accept — use those
    dh_pub   = _b64d(body.dh_pub)
    sign_pub = _b64d(body.signing_pub)
    account_id = invite["account_id"]

    device_id = await pg.create_device(
        pool,
        account_id=account_id,
        name=body.device_name,
        device_type="android",
        dh_public_key=dh_pub,
        signing_pub_key=sign_pub,
    )

    await pg.set_invite_consumed(pool, body.token)

    mnemonic_confirmed = await pg.get_mnemonic_confirmed(pool, account_id)

    # Fetch vault so Device B can store it
    vault_row = await pg.get_vault(pool, account_id)
    vault_blob_b64 = (
        base64.b64encode(bytes(vault_row["encrypted_blob"])).decode()
        if vault_row else None
    )

    settings = request.app.state.settings
    server_pub = base64.b64encode(
        settings.server_signing_key.verify_key.encode()
    ).decode()

    await pg.write_audit_event(
        pool, event_type="device_added_via_invite",
        account_id=account_id, device_id=device_id,
    )
    logger.info("invite_complete account_id=%s device_id=%s", account_id, device_id)

    return {
        "access_token":       create_access_token(account_id, device_id),
        "device_id":          str(device_id),
        "account_id":         str(account_id),
        "server_pub_key":     server_pub,
        "mnemonic_confirmed": mnemonic_confirmed,
        "encrypted_vault_blob": vault_blob_b64,
    }
