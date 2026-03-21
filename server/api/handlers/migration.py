"""
Migration handlers.

Flow:
  1. Old device generates a migration_id (32 random bytes) and embeds it in the QR payload.
  2. Old device polls GET /migration/status/{migration_id} while the dialog is open.
  3. New device scans QR, imports credentials, then calls POST /migration/confirm.
  4. Old device sees status=confirmed and wipes itself.

Both calls use the auth_token from the QR payload — same account, same server.
No new DB tables: the confirmation flag lives in Redis with a 300s TTL.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel

from api.middleware.auth import require_auth, AuthContext
from typing import Annotated
from fastapi import Depends

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/migration", tags=["migration"])

MIGRATION_TTL = 300          # seconds — matches the 180s QR expiry with margin
MIGRATION_PREFIX = "mig:"


class MigrationConfirmRequest(BaseModel):
    migration_id: str        # base64url-encoded 32 bytes from the QR payload


@router.post("/confirm", status_code=200)
async def confirm_migration(
    body: MigrationConfirmRequest,
    request: Request,
    auth: Annotated[AuthContext, Depends(require_auth)],
):
    """
    Called by the new device after a successful import.
    Stores a confirmed flag in Redis so the old device can detect it and wipe.
    Requires valid auth (the imported auth_token) to prevent random actors from
    triggering a wipe on someone else's device.
    """
    redis = request.app.state.redis
    key = f"{MIGRATION_PREFIX}{body.migration_id}"
    await redis.setex(key, MIGRATION_TTL, "confirmed")
    logger.info("migration_confirmed", extra={"migration_id": body.migration_id[:8] + "..."})
    return {"status": "confirmed"}


@router.get("/status/{migration_id}", status_code=200)
async def migration_status(
    migration_id: str,
    request: Request,
    auth: Annotated[AuthContext, Depends(require_auth)],
):
    """
    Polled by the old device while the QR dialog is open.
    Returns {"status": "pending"} until the new device confirms, then {"status": "confirmed"}.
    Auth required — same token as the QR payload.
    """
    redis = request.app.state.redis
    key = f"{MIGRATION_PREFIX}{migration_id}"
    val = await redis.get(key)
    return {"status": "confirmed" if val == "confirmed" else "pending"}
