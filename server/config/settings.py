"""
Configuration — loaded from environment variables.
Never log or expose these values.
"""

from __future__ import annotations

import base64
import secrets
from functools import lru_cache

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

import nacl.signing


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Network
    listen_host: str = "0.0.0.0"
    listen_port: int = 8080

    # Database
    database_url: str  # e.g. postgresql://fortispass:pass@postgres:5432/fortispass

    # Redis
    redis_url: str  # e.g. redis://:pass@redis:6379/0

    # JWT — base64-encoded 32-byte key
    jwt_secret: str
    jwt_access_expire_minutes: int = 43200  # 30 days — device tokens don't need short expiry (revocation via device table)
    jwt_refresh_expire_days: int = 7

    # Ed25519 signing key for QR payloads — base64-encoded 32-byte seed.
    # If not set, a random key is generated (ephemeral — not suitable for production).
    server_sign_key_seed: str = ""

    # HMAC key for recovery blob integrity — base64-encoded 32-byte key
    server_hmac_key: str

    # Deployment mode
    self_hosted: bool = False

    # Vault constraints
    max_vault_size_bytes: int = 10 * 1024 * 1024  # 10 MB
    max_devices_per_vault: int = 3                 # Override with --max-devices flag

    # Trusted reverse proxy IPs/CIDRs (comma-separated).
    # X-Forwarded-For is only trusted when the immediate peer is in this list.
    # Example: "127.0.0.1,10.0.0.0/8,172.16.0.0/12"
    # Leave empty to disable XFF (direct connections only — safe default).
    trusted_proxy_ips: str = ""

    # Relay URL returned in session create responses
    relay_url: str = "https://relay.example.com"

    # ------------------------------------------------------------------ #
    # Derived — populated in model_validator                              #
    # ------------------------------------------------------------------ #
    _jwt_secret_bytes: bytes = b""
    _server_hmac_key_bytes: bytes = b""
    _server_signing_key: nacl.signing.SigningKey | None = None
    _server_verify_key_bytes: bytes = b""

    @model_validator(mode="after")
    def _derive_keys(self) -> "Settings":
        # JWT secret
        try:
            secret = base64.b64decode(self.jwt_secret)
        except Exception:
            raise ValueError("jwt_secret must be valid base64")
        if len(secret) < 32:
            raise ValueError("jwt_secret must decode to at least 32 bytes")
        object.__setattr__(self, "_jwt_secret_bytes", secret)

        # Server HMAC key
        try:
            hmac_key = base64.b64decode(self.server_hmac_key)
        except Exception:
            raise ValueError("server_hmac_key must be valid base64")
        if len(hmac_key) < 32:
            raise ValueError("server_hmac_key must decode to at least 32 bytes")
        object.__setattr__(self, "_server_hmac_key_bytes", hmac_key)

        # Server Ed25519 signing key
        if self.server_sign_key_seed:
            try:
                seed = base64.b64decode(self.server_sign_key_seed)
            except Exception:
                raise ValueError("server_sign_key_seed must be valid base64")
            if len(seed) != 32:
                raise ValueError("server_sign_key_seed must decode to exactly 32 bytes")
            signing_key = nacl.signing.SigningKey(seed)
        else:
            # Ephemeral — warn loudly
            import logging
            logging.getLogger(__name__).warning(
                "SERVER_SIGN_KEY_SEED not set — generating ephemeral signing key. "
                "Set this in production or QR verification will break on restart."
            )
            signing_key = nacl.signing.SigningKey.generate()

        object.__setattr__(self, "_server_signing_key", signing_key)
        object.__setattr__(
            self,
            "_server_verify_key_bytes",
            bytes(signing_key.verify_key),
        )

        return self

    @property
    def jwt_secret_bytes(self) -> bytes:
        return self._jwt_secret_bytes

    @property
    def server_hmac_key_bytes(self) -> bytes:
        return self._server_hmac_key_bytes

    @property
    def server_signing_key(self) -> nacl.signing.SigningKey:
        return self._server_signing_key  # type: ignore[return-value]

    @property
    def server_verify_key_bytes(self) -> bytes:
        return self._server_verify_key_bytes


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
