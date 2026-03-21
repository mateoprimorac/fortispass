"""
Server-side cryptographic operations via PyNaCl (libsodium bindings).

FIX: hmac.new() does not exist — correct call is hmac.new() → actually
the stdlib is `hmac.new(key, msg, digestmod)`. Fixed below.
"""
from __future__ import annotations

import hashlib
import hmac
import struct

import nacl.encoding
import nacl.exceptions
import nacl.signing
import nacl.utils


def sign_session_manifest(
    signing_key: nacl.signing.SigningKey,
    session_id_bytes: bytes,
    ext_pub_key_bytes: bytes,
    expiry: int,
) -> bytes:
    """
    Sign: session_id(32) || ext_pub_key(32) || expiry(8, big-endian uint64)
    Must match Android: struct.pack(">Q", expiry) == big-endian uint64
    Returns 64-byte Ed25519 signature.
    """
    msg = session_id_bytes + ext_pub_key_bytes + struct.pack(">Q", expiry)
    signed = signing_key.sign(msg)
    return signed.signature  # first 64 bytes


def verify_device_session_response(
    device_signing_pub_key_bytes: bytes,
    session_id_bytes: bytes,
    dev_eph_pub_bytes: bytes,
    enc_vault_key_bytes: bytes,
    timestamp: int,
    signature_bytes: bytes,
) -> bool:
    """
    Verify Ed25519 signature on Android session response.
    msg = session_id(32) || dev_eph_pub(32) || enc_vault_key || timestamp(8, big-endian)
    Must exactly match the message built in QRScanActivity.kt.
    """
    msg = (
        session_id_bytes
        + dev_eph_pub_bytes
        + enc_vault_key_bytes
        + struct.pack(">Q", timestamp)
    )
    try:
        verify_key = nacl.signing.VerifyKey(device_signing_pub_key_bytes)
        verify_key.verify(msg, signature_bytes)
        return True
    except (nacl.exceptions.BadSignatureError, Exception):
        return False


def compute_recovery_hmac(hmac_key: bytes, encrypted_vault_key: bytes) -> bytes:
    """HMAC-SHA256 over recovery blob ciphertext for server-side integrity."""
    # FIX: correct stdlib call is hmac.new(key, msg, digestmod).digest()
    return hmac.new(hmac_key, encrypted_vault_key, hashlib.sha256).digest()


def verify_recovery_hmac(hmac_key: bytes, encrypted_vault_key: bytes, expected: bytes) -> bool:
    actual = compute_recovery_hmac(hmac_key, encrypted_vault_key)
    return hmac.compare_digest(actual, expected)


def constant_time_equal(a: bytes, b: bytes) -> bool:
    return hmac.compare_digest(a, b)


def random_bytes(n: int) -> bytes:
    return nacl.utils.random(n)
