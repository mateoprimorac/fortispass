"""
Data models — request/response schemas and internal domain types.
Pydantic v2 throughout.
"""

from __future__ import annotations

import base64
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, field_validator, model_validator


# ─── Helpers ────────────────────────────────────────────────────────────────

def _decode_b64(v: str, expected_len: int | None = None, field: str = "field") -> bytes:
    try:
        # Accept both standard (+/) and URL-safe (-_) base64, with or without padding
        padded = v + "==" * ((4 - len(v) % 4) % 4)
        b = base64.urlsafe_b64decode(padded)
    except Exception:
        raise ValueError(f"{field} must be valid base64")
    if expected_len is not None and len(b) != expected_len:
        raise ValueError(f"{field} must decode to exactly {expected_len} bytes, got {len(b)}")
    return b


# ─── Auth ────────────────────────────────────────────────────────────────────

class DeviceRegistrationRequest(BaseModel):
    name: str
    device_name: str = ""    # alias — use whichever is set
    type: str = "android"
    dh_public_key: str       # base64 X25519 pub key, 32 bytes
    signing_pub_key: str     # base64 Ed25519 pub key, 32 bytes

    @model_validator(mode="after")
    def _validate_keys(self) -> "DeviceRegistrationRequest":
        _decode_b64(self.dh_public_key, 32, "dh_public_key")
        _decode_b64(self.signing_pub_key, 32, "signing_pub_key")
        return self


class RegisterRequest(BaseModel):
    """Passwordless device registration — no email or password needed."""
    device_name: str
    device: DeviceRegistrationRequest
    initial_vault: str       # base64 AES-256-GCM(empty, vaultKey)
    vault_lookup_hash: str | None = None  # HMAC-SHA256(vaultKey, "fortispass-vault-lookup-v1"), base64url
    mnemonic_confirmed: bool = False      # True when recovering from a confirmed vault

    @model_validator(mode="after")
    def _validate(self) -> "RegisterRequest":
        _decode_b64(self.initial_vault, None, "initial_vault")
        return self


class RegisterResponse(BaseModel):
    account_id: str
    device_id: str
    access_token: str
    server_pub_key: str      # base64 Ed25519 — pin this in the Android app





class SessionCreateRequest(BaseModel):
    session_id: str          # base64 32 bytes
    ext_pub_key: str         # base64 X25519 ephemeral pub key, 32 bytes
    expiry: int              # unix timestamp

    @model_validator(mode="after")
    def _validate(self) -> "SessionCreateRequest":
        _decode_b64(self.session_id, 32, "session_id")
        _decode_b64(self.ext_pub_key, 32, "ext_pub_key")
        return self


class SessionCreateResponse(BaseModel):
    session_id: str
    server_sig: str
    relay_url: str


class SessionRespondRequest(BaseModel):
    session_id: str
    dev_eph_pub: str         # base64 X25519 ephemeral pub key, 32 bytes
    enc_vault_key: str       # base64 XChaCha20-Poly1305 ciphertext
    sig: str                 # base64 Ed25519 signature
    device_id: UUID
    timestamp: int

    @model_validator(mode="after")
    def _validate(self) -> "SessionRespondRequest":
        _decode_b64(self.session_id, 32, "session_id")
        _decode_b64(self.dev_eph_pub, 32, "dev_eph_pub")
        _decode_b64(self.sig, 64, "sig")
        return self


class SessionRetrieveResponse(BaseModel):
    dev_eph_pub: str
    enc_vault_key: str
    sig: str
    enc_vault_blob: str | None = None   # AES-GCM encrypted vault blob (from server)
    vault_version: int | None = None
    vault_token: str | None = None      # Short-lived JWT for extension to PUT /vault


class SessionStatusResponse(BaseModel):
    ext_pub_key: str
    expiry: int
    server_sig: str
    status: str


# ─── Vault ───────────────────────────────────────────────────────────────────

class VaultResponse(BaseModel):
    encrypted_blob: str
    version: int
    blob_hash: str


class VaultUpdateRequest(BaseModel):
    encrypted_blob: str
    version: int
    blob_hash: str


class VaultUpdateResponse(BaseModel):
    version: int


# ─── Devices ─────────────────────────────────────────────────────────────────

class DeviceResponse(BaseModel):
    id: UUID
    name: str
    type: str
    signing_pub_key: str
    is_revoked: bool
    last_seen: datetime | None
    created_at: datetime


class NewDeviceRequest(BaseModel):
    name: str
    type: Literal["android", "extension"]
    dh_public_key: str
    signing_pub_key: str
    sig: str                 # base64 Ed25519 sig from existing device


class NewDeviceResponse(BaseModel):
    device_id: UUID


class RevokeDeviceRequest(BaseModel):
    sig: str                 # base64 Ed25519 sig authorizing revocation


# ─── Recovery ────────────────────────────────────────────────────────────────

class RecoveryBlobRequest(BaseModel):
    email: str
    recovery_proof: str      # base64 HMAC-SHA256(RecoveryKey, "recovery-proof-v1" || email)


class RecoveryBlobResponse(BaseModel):
    encrypted_vault_key: str


# ─── Server pubkey ───────────────────────────────────────────────────────────

class ServerPubkeyResponse(BaseModel):
    ed25519_pub: str
    valid_from: str
    valid_until: str


# ─── Device Invite (Add Device flow) ─────────────────────────────────────────

class InviteCreateResponse(BaseModel):
    token: str
    expires_at: datetime
    inviting_dh_pub: str   # base64url — Device B needs this for ECDH


class InviteAcceptRequest(BaseModel):
    token: str
    joiner_dh_pub: str     # base64url X25519 pub, 32 bytes
    joiner_sign_pub: str   # base64url Ed25519 pub, 32 bytes
    device_name: str
    kick_device_id: str | None = None  # UUID — kick this device to make room

    @model_validator(mode="after")
    def _validate(self) -> "InviteAcceptRequest":
        _decode_b64(self.joiner_dh_pub,  32, "joiner_dh_pub")
        _decode_b64(self.joiner_sign_pub, 32, "joiner_sign_pub")
        return self


class DeviceInfo(BaseModel):
    id: str
    name: str
    created_at: datetime


class InviteAcceptResponse(BaseModel):
    status: str            # "accepted" or "at_limit"
    devices: list[DeviceInfo] = []   # populated when status == "at_limit"


class InviteDeliverRequest(BaseModel):
    token: str
    encrypted_vault_key: str  # base64 AES-GCM(sharedKey, vaultKey)


class InviteStatusResponse(BaseModel):
    state: str                 # pending | accepted | delivered | consumed
    joiner_dh_pub: str | None = None
    inviting_dh_pub: str | None = None
    encrypted_vault_key: str | None = None


class InviteCompleteRequest(BaseModel):
    token: str
    device_name: str
    dh_pub: str           # base64url, Device B's X25519 pub
    signing_pub: str      # base64url, Device B's Ed25519 pub

    @model_validator(mode="after")
    def _validate(self) -> "InviteCompleteRequest":
        _decode_b64(self.dh_pub,     32, "dh_pub")
        _decode_b64(self.signing_pub, 32, "signing_pub")
        return self

class SessionState(BaseModel):
    session_id: str
    ext_pub_key: str         # base64
    server_sig: str          # base64
    expiry: int
    status: Literal["pending", "responded", "consumed"]
    account_id: str
    # Populated after Android responds:
    dev_eph_pub: str | None = None
    enc_vault_key: str | None = None
    device_sig: str | None = None
