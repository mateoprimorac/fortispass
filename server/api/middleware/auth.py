"""
JWT authentication middleware.

Tokens contain: account_id, device_id, token_type (access|refresh).
Tokens are signed with HS256 using the server JWT secret.

This module also provides the FastAPI dependency `require_auth`
which injects account_id and device_id into route handlers.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Annotated
from uuid import UUID

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from config.settings import get_settings

logger = logging.getLogger(__name__)

_bearer = HTTPBearer(auto_error=True)


def create_access_token(account_id: UUID, device_id: UUID) -> str:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(account_id),
        "did": str(device_id),
        "typ": "access",
        "iat": now,
        "exp": now + timedelta(minutes=settings.jwt_access_expire_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret_bytes, algorithm="HS256")


def create_vault_token(account_id: UUID) -> str:
    """Short-lived token (1h) for the extension to PUT /vault after unlock."""
    settings = get_settings()
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(account_id),
        "did": "extension",
        "typ": "vault_extension",
        "iat": now,
        "exp": now + timedelta(hours=1),
    }
    return jwt.encode(payload, settings.jwt_secret_bytes, algorithm="HS256")


def create_refresh_token(account_id: UUID, device_id: UUID) -> str:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(account_id),
        "did": str(device_id),
        "typ": "refresh",
        "iat": now,
        "exp": now + timedelta(days=settings.jwt_refresh_expire_days),
    }
    return jwt.encode(payload, settings.jwt_secret_bytes, algorithm="HS256")


def _decode_token(token: str) -> dict:
    settings = get_settings()
    try:
        return jwt.decode(
            token,
            settings.jwt_secret_bytes,
            algorithms=["HS256"],
            options={"require": ["sub", "did", "typ", "exp"]},
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired")
    except jwt.InvalidTokenError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")


class AuthContext:
    def __init__(self, account_id: UUID, device_id: UUID):
        self.account_id = account_id
        self.device_id = device_id


async def require_auth(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(_bearer)],
) -> AuthContext:
    payload = _decode_token(credentials.credentials)
    typ = payload.get("typ")
    if typ == "vault_extension":
        # Short-lived token issued at session retrieve for extension vault writes
        try:
            return AuthContext(
                account_id=UUID(payload["sub"]),
                device_id=UUID("00000000-0000-0000-0000-000000000000"),
            )
        except (ValueError, KeyError):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Malformed token")
    if typ != "access":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Wrong token type")
    try:
        return AuthContext(
            account_id=UUID(payload["sub"]),
            device_id=UUID(payload["did"]),
        )
    except (ValueError, KeyError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Malformed token")
