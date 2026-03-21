"""
Vault handlers.

The server stores and retrieves opaque encrypted blobs.
It cannot read vault contents. Optimistic locking prevents
conflicting concurrent updates from multiple devices.
"""

from __future__ import annotations

import base64
import hashlib
import logging
from typing import Annotated

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Request, status

from api.middleware.auth import AuthContext, require_auth
from api.middleware.ratelimit import rate_limit
from db import postgres as pg
from models.models import VaultResponse, VaultUpdateRequest, VaultUpdateResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/vault", tags=["vault"])


@router.get("", response_model=VaultResponse)
async def get_vault(
    request: Request,
    auth: Annotated[AuthContext, Depends(require_auth)],
) -> VaultResponse:
    pool: asyncpg.Pool = request.app.state.db

    row = await pg.get_vault(pool, auth.account_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vault not found")

    return VaultResponse(
        encrypted_blob=base64.b64encode(row["encrypted_blob"]).decode(),
        version=row["version"],
        blob_hash=base64.b64encode(row["blob_hash"]).decode(),
    )


@router.put("", response_model=VaultUpdateResponse)
async def update_vault(
    body: VaultUpdateRequest,
    request: Request,
    auth: Annotated[AuthContext, Depends(require_auth)],
    _: None = Depends(rate_limit(limit=60, window_seconds=3600)),
) -> VaultUpdateResponse:
    """
    Upload an updated encrypted vault blob.
    Version must be current_version + 1 (optimistic locking).
    Returns 409 on version conflict — client must fetch, merge, and retry.
    """
    pool: asyncpg.Pool = request.app.state.db
    settings = request.app.state.settings

    encrypted_blob = base64.b64decode(body.encrypted_blob)
    if len(encrypted_blob) > settings.max_vault_size_bytes:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="Vault too large")

    # Verify the client-provided hash matches the blob.
    # WebCrypto (extension) can only produce SHA-256; Android uses blake2b.
    # Accept either: compute both and accept if either matches.
    import hmac as _hmac
    provided_hash = base64.b64decode(body.blob_hash)
    blake2_hash = hashlib.blake2b(encrypted_blob, digest_size=32).digest()
    sha256_hash = hashlib.sha256(encrypted_blob).digest()
    if not (_hmac.compare_digest(blake2_hash, provided_hash) or
            _hmac.compare_digest(sha256_hash, provided_hash)):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="blob_hash mismatch")

    new_version = await pg.update_vault(
        pool,
        account_id=auth.account_id,
        encrypted_blob=encrypted_blob,
        blob_hash=provided_hash,
        expected_version=body.version,
    )

    if new_version is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Version conflict — fetch latest and retry",
        )

    logger.info("vault_updated account_id=%s version=%s", auth.account_id, new_version)

    return VaultUpdateResponse(version=new_version)
