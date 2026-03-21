"""
Server identity endpoint.

GET /api/v1/server/pubkey — unauthenticated, rate-limited.
Returns the server's Ed25519 public key so clients can pin it on first connect.
This is the Trust-On-First-Use (TOFU) endpoint.

The fingerprint is SHA-256(raw_pubkey_bytes), displayed to the user as a
hex string so they can optionally verify it out-of-band (e.g. check the
server admin's published fingerprint).
"""
from __future__ import annotations

import base64
import hashlib
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request

from api.middleware.ratelimit import rate_limit

router = APIRouter(prefix="/server", tags=["server"])


@router.get("/pubkey")
async def get_server_pubkey(
    request: Request,
    _=Depends(rate_limit(limit=60, window_seconds=60)),
) -> dict:
    settings = request.app.state.settings
    pub_bytes = settings.server_signing_key.verify_key.encode()
    fingerprint = hashlib.sha256(pub_bytes).hexdigest()
    return {
        "ed25519_pub": base64.b64encode(pub_bytes).decode(),
        "fingerprint": ":".join(
            fingerprint[i:i+2] for i in range(0, len(fingerprint), 2)
        ),
        "algorithm": "Ed25519",
    }


@router.get("/info")
async def server_info(request: Request) -> dict:
    """Returns public server configuration — no auth required."""
    settings = request.app.state.settings
    return {
        "max_devices_per_vault": getattr(settings, "max_devices_per_vault", 3),
    }
