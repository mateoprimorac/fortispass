"""
Recovery endpoints.

GET  /recovery/mnemonic-status   — returns whether this account has confirmed its mnemonic
POST /recovery/confirm-mnemonic  — marks mnemonic as confirmed for the account
POST /recovery/vault             — unauthenticated: returns encrypted vault by device_id
                                   (vault is AES-256-GCM encrypted; only the phrase holder
                                    can decrypt it — no auth token required)
"""
from __future__ import annotations
import base64
import logging
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel

from api.middleware.auth import AuthContext, require_auth, create_access_token
from api.middleware.ratelimit import rate_limit
from db import postgres as pg

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/recovery", tags=["recovery"])


# ── Mnemonic confirmation ─────────────────────────────────────────────────────

@router.get("/mnemonic-status")
async def mnemonic_status(
    request: Request,
    auth: Annotated[AuthContext, Depends(require_auth)],
):
    confirmed = await pg.get_mnemonic_confirmed(request.app.state.db, auth.account_id)
    return {"confirmed": confirmed}


@router.post("/confirm-mnemonic", status_code=200)
async def confirm_mnemonic(
    request: Request,
    auth: Annotated[AuthContext, Depends(require_auth)],
):
    await pg.set_mnemonic_confirmed(request.app.state.db, auth.account_id)
    logger.info("mnemonic_confirmed", extra={"account_id": str(auth.account_id)})
    return {"status": "confirmed"}


# ── Recovery vault fetch ──────────────────────────────────────────────────────

class VaultByDeviceRequest(BaseModel):
    vault_lookup_hash: str   # HMAC-SHA256(vaultKey, "fortispass-vault-lookup-v1"), base64url


@router.post("/vault", status_code=200)
async def recovery_vault(
    body: VaultByDeviceRequest,
    request: Request,
    _: None = Depends(rate_limit(limit=5, window_seconds=3600)),
):
    """
    Unauthenticated endpoint: returns the encrypted vault blob by vault_lookup_hash.
    The hash is HMAC-SHA256(vaultKey, "fortispass-vault-lookup-v1") — computed from the
    vault key which is derived from the recovery phrase. Only the phrase holder can
    compute the correct hash, so no auth token or device ID is needed.
    Rate-limited to 5/hour/IP.
    """
    row = await pg.get_vault_by_lookup_hash(request.app.state.db, body.vault_lookup_hash)
    if row is None:
        raise HTTPException(status_code=404, detail="Vault not found")

    logger.info("recovery_vault_fetched hash_prefix=%s", body.vault_lookup_hash[:8])

    return {
        "encrypted_blob":     base64.b64encode(row["encrypted_blob"]).decode(),
        "version":            row["version"],
        "blob_hash":          base64.b64encode(row["blob_hash"]).decode(),
        "account_id":         str(row["account_id"]),
        "mnemonic_confirmed": bool(row["mnemonic_confirmed"]),
    }
