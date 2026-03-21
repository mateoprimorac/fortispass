# Cross-Component Compatibility Notes

This document records every interface point between the three components
and the exact formats required for interoperability.

---

## 1. Base64 Encoding Conventions

| Location | Encoding | Why |
|---|---|---|
| Extension → Server API (session_id, ext_pub_key) | Standard base64 (`btoa`) | Server stores and echoes as-is |
| Extension → QR payload (sid, epk, sig) | URL-safe base64 (no padding) | QR avoids `+`, `/`, `=` chars |
| Android QR decode (sid, epk, sig) | URL-safe (`Base64.URL_SAFE`) | Matches extension QR encoding |
| Android → Server API (all fields) | Standard base64 (`Base64.NO_WRAP`) | Matches Python `base64.b64decode()` |
| Server → Client responses | Standard base64 | Consistent throughout |

**Critical:** Android re-encodes `session_id` from URL-safe (QR) to standard base64 before `POST /session/respond`. Done in `QRScanActivity.kt` with `Base64.encodeToString(sessionIDBytes, Base64.NO_WRAP)`.

---

## 2. Cryptographic Message Formats

### Session manifest signature (server signs → Android verifies)
```
msg = session_id(32) || ext_pub_key(32) || expiry_uint64_big_endian(8)
```
- Server: `crypto/keys.py::sign_session_manifest()` — `struct.pack(">Q", expiry)`
- Android: `QRScanActivity.kt::bigEndian8(expiry)` — manual big-endian

### Session response signature (Android signs → server verifies)
```
msg = session_id(32) || dev_eph_pub(32) || enc_vault_key(var) || timestamp_uint64_big_endian(8)
```
- Android: `CryptoEngine.kt::signSessionResponse()` — `ByteBuffer.order(ByteOrder.BIG_ENDIAN)`
- Server: `crypto/keys.py::verify_device_session_response()` — `struct.pack(">Q", timestamp)`

### Session key derivation (Android and Extension must produce identical output)
```
SharedSecret = X25519(eph_priv, peer_eph_pub)
SessionKey   = HKDF-SHA256(ikm=SharedSecret, salt=session_id_bytes, info="fortispass-session-v1", len=32)
```
- Android: `KeyManager.kt::deriveSessionKey()` / `hkdfSHA256()`
- Extension: `crypto.js::deriveSessionKey()` via WebCrypto

### Ciphertext wire format (XChaCha20-Poly1305 IETF)
```
on_wire = nonce(24) || ciphertext_with_tag
```
- Android encrypt: `CryptoEngine.kt::_encrypt()`
- Extension decrypt: `sodium.js::decryptXChaCha20Poly1305()`

---

## 3. Bugs Fixed During Audit

| ID | Component | Bug | Fix |
|---|---|---|---|
| B1 | Server | FastAPI route `/retrieve/{id}` matched by `/{id}` wildcard | Reordered: specific routes before wildcards |
| B2 | Server | WebSocket double `accept()` — hub and handler both called it | Added `hub.register()` for pre-accepted sockets |
| B3 | Server | `python-json-logger` missing from requirements.txt | Added to requirements |
| B4 | Server | Deprecated `@app.on_event` in FastAPI 0.111 | Replaced with `asynccontextmanager` lifespan |
| B5 | Android/Extension | Base64 mismatch: URL-safe from QR sent directly to API | Android re-encodes to standard b64 for API |
| B6 | Extension | CSP missing `wasm-unsafe-eval` — libsodium WASM blocked | Added to manifest.json CSP |
