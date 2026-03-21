/**
 * sodium.js — libsodium wrapper for the service worker.
 *
 * Uses importScripts() (synchronous, allowed in service workers).
 * The package embeds WASM as base64 inside the JS file — no separate .wasm needed.
 *
 * SETUP: Copy ONE file:
 *   node_modules/libsodium-wrappers-sumo/dist/modules-sumo/libsodium-wrappers.js
 *   → extension/lib/libsodium-wrappers.js
 */

'use strict';

let _sodium = null;
let _loadError = null;

function getSodium() {
  if (_sodium) return _sodium;
  if (_loadError) throw _loadError;

  try {
    importScripts(self.location.origin + '/lib/libsodium-wrappers.js');

    // After importScripts the UMD bundle has run and attached to self.
    // The sumo build exposes itself as self.sodium or via module.exports
    // depending on the environment — in a SW global scope it's self.sodium.
    const sodium = self.sodium;
    if (!sodium) throw new Error('libsodium global not found after importScripts');

    _sodium = sodium;
    return _sodium;
  } catch (e) {
    _loadError = new Error(
      'libsodium failed to load. Make sure extension/lib/libsodium-wrappers.js exists. ' +
      e.message
    );
    throw _loadError;
  }
}

export async function decryptXChaCha20Poly1305(blob, keyBytes) {
  const sodium = getSodium();
  if (blob.length <= 24) throw new Error('Ciphertext too short');
  const nonce = blob.slice(0, 24);
  const ciphertext = blob.slice(24);
  try {
    return sodium.crypto_aead_xchacha20poly1305_ietf_decrypt(
      null, ciphertext, null, nonce, keyBytes
    );
  } catch {
    throw new Error('Decryption failed — wrong key or corrupted data');
  }
}

export async function encryptXChaCha20Poly1305(plaintext, keyBytes) {
  const sodium = getSodium();
  const nonce = sodium.randombytes_buf(24);
  const ciphertext = sodium.crypto_aead_xchacha20poly1305_ietf_encrypt(
    plaintext, null, null, nonce, keyBytes
  );
  const out = new Uint8Array(24 + ciphertext.length);
  out.set(nonce, 0);
  out.set(ciphertext, 24);
  return out;
}
