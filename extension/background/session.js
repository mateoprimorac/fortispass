/**
 * session.js — NOTE: This file is NOT imported by the service worker.
 *
 * The service worker (service-worker.js) is a classic (non-module) script and
 * implements all session logic inline using AES-256-GCM via WebCrypto.
 *
 * This file is kept as a readable reference for the session protocol only.
 * Do not import it — it will not work in the service worker context.
 *
 * Protocol summary:
 *   1. Extension generates 32-byte sessionID + X25519 ephemeral keypair
 *   2. POST /api/v1/session/create  → server signs (sessionID || extEphPub || expiry)
 *   3. Extension encodes signed QR payload (v=1, sid, epk, url, exp, sig)
 *   4. Android scans QR, verifies server Ed25519 sig via pinned TOFU key
 *   5. Android authenticates biometric, unwraps vaultKey from hardware keystore
 *   6. Android generates ephemeral X25519 keypair, derives sessionKey via HKDF-SHA256
 *   7. Android encrypts vaultKey with AES-256-GCM(sessionKey), signs response
 *   8. POST /api/v1/session/respond  → server stores, notifies extension via WebSocket
 *   9. Extension GET /api/v1/session/retrieve → gets enc_vault_key
 *  10. Extension derives same sessionKey, decrypts vaultKey with AES-256-GCM
 *  11. Vault key lives in service worker memory until auto-lock alarm fires
 *
 * Cipher: AES-256-GCM, 12-byte nonce, 128-bit tag — matches Android CryptoEngine.kt
 * KDF: HKDF-SHA256(ikm=X25519_shared, salt=sessionID, info="fortispass-session-v1", len=32)
 */
'use strict';
