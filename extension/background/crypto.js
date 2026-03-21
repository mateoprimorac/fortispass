/**
 * crypto.js — WebCrypto operations for the extension service worker.
 *
 * fortispass — WebCrypto operations for the extension service worker.
 *
 * COMPATIBILITY NOTES vs Android:
 * - X25519 WebCrypto: Chrome 113+. Used for session key ECDH.
 * - Ed25519 WebCrypto: Chrome 113+. Used for device sig verification.
 * - AES-256-GCM: Used for session vault-key transfer. Matches Android CryptoEngine.kt.
 *   Wire format: nonce(12) || ciphertext+tag(16).
 * - HKDF-SHA256 parameters MUST match Android KeyManager.hkdfSHA256() exactly:
 *     salt = sessionID bytes, info = "fortispass-session-v1" UTF-8, length = 32 bytes
 */

'use strict';

export function generateSessionID() {
  return crypto.getRandomValues(new Uint8Array(32));
}

export async function generateEphemeralKeyPair() {
  const keyPair = await crypto.subtle.generateKey(
    { name: 'X25519' },
    true,
    ['deriveKey', 'deriveBits']
  );
  const publicKeyRaw = await crypto.subtle.exportKey('raw', keyPair.publicKey);
  return {
    privateKey: keyPair.privateKey,
    publicKeyRaw: new Uint8Array(publicKeyRaw),
    publicKey: keyPair.publicKey,
  };
}

/**
 * Derive SessionKey via X25519 ECDH + HKDF-SHA256.
 *
 * Parameters MUST match Android KeyManager.deriveSessionKey():
 *   SharedSecret = X25519(ext_eph_priv, dev_eph_pub)
 *   SessionKey   = HKDF-SHA256(ikm=SharedSecret, salt=sessionID, info="fortispass-session-v1", len=32)
 *
 * Returns { sessionKeyBits: Uint8Array(32) } — used with libsodium for XChaCha20 decrypt.
 */
export async function deriveSessionKey(privateKey, peerPublicKeyBytes, sessionIDBytes) {
  const peerPublicKey = await crypto.subtle.importKey(
    'raw',
    peerPublicKeyBytes,
    { name: 'X25519' },
    false,
    []
  );

  const sharedSecretBits = await crypto.subtle.deriveBits(
    { name: 'X25519', public: peerPublicKey },
    privateKey,
    256
  );

  const hkdfKeyMaterial = await crypto.subtle.importKey(
    'raw',
    sharedSecretBits,
    'HKDF',
    false,
    ['deriveBits']
  );

  const sessionKeyBits = await crypto.subtle.deriveBits(
    {
      name: 'HKDF',
      hash: 'SHA-256',
      salt: sessionIDBytes,
      info: new TextEncoder().encode('fortispass-session-v1'),
    },
    hkdfKeyMaterial,
    256
  );

  return { sessionKeyBits: new Uint8Array(sessionKeyBits) };
}

/**
 * Verify Ed25519 signature from registered device.
 * Used to authenticate the session response from Android.
 */
export async function verifyDeviceSignature(message, signature, devicePubKeyBytes) {
  const pubKey = await crypto.subtle.importKey(
    'raw',
    devicePubKeyBytes,
    { name: 'Ed25519' },
    false,
    ['verify']
  );
  return await crypto.subtle.verify({ name: 'Ed25519' }, pubKey, signature, message);
}

/**
 * Verify server Ed25519 signature on QR payload.
 * Server public key must be pinned — fetched once and stored in chrome.storage.local.
 */
export async function verifyServerSignature(message, signature, serverPubKeyBytes) {
  return verifyDeviceSignature(message, signature, serverPubKeyBytes);
}

/** Best-effort zero. V8 GC may copy before this runs — accepted limitation. */
export function zeroBytes(arr) {
  if (arr instanceof Uint8Array) arr.fill(0);
}

export function base64Encode(bytes) {
  // Avoid spread operator — stack overflows on large arrays (>~65k bytes)
  let binary = '';
  for (let i = 0; i < bytes.length; i++) binary += String.fromCharCode(bytes[i]);
  return btoa(binary);
}

export function base64Decode(str) {
  return new Uint8Array(atob(str).split('').map(c => c.charCodeAt(0)));
}

export function base64UrlEncode(bytes) {
  return base64Encode(bytes).replace(/\+/g, '-').replace(/\//g, '_').replace(/=/g, '');
}
