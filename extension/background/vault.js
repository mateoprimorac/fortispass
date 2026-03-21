/**
 * vault.js — Vault decryption and credential access.
 *
 * VaultKey is retrieved from memory for each operation and zeroed immediately after.
 * Decrypted vault data is zeroed after use.
 * Content scripts receive ONLY the username/password at fill time — never the raw vault.
 */

'use strict';

import { memory } from './memory.js';
import { zeroBytes } from './crypto.js';
import { decryptXChaCha20Poly1305, encryptXChaCha20Poly1305 } from './sodium.js';

const DB_NAME = 'fortispass_vault';
const DB_STORE = 'encrypted_vault';

export async function getCredentialsForDomain(domain) {
  if (!memory.isUnlocked()) throw new Error('Vault is locked');
  const blob = await _getEncryptedBlob();
  if (!blob) return [];

  let vaultKey = null;
  let plaintext = null;
  try {
    vaultKey = memory.getVaultKey();
    plaintext = await decryptXChaCha20Poly1305(blob, vaultKey);
    const vault = JSON.parse(new TextDecoder().decode(plaintext));
    return (vault.credentials || [])
      .filter(c => c.uri && _matchesDomain(c.uri, domain))
      .map(c => ({ id: c.id, name: c.name, username: c.username, uri: c.uri }));
  } finally {
    if (vaultKey) zeroBytes(vaultKey);
    if (plaintext) zeroBytes(plaintext);
  }
}

export async function fillCredential(credentialID) {
  if (!memory.isUnlocked()) throw new Error('Vault is locked');
  const blob = await _getEncryptedBlob();
  let vaultKey = null;
  let plaintext = null;
  try {
    vaultKey = memory.getVaultKey();
    plaintext = await decryptXChaCha20Poly1305(blob, vaultKey);
    const vault = JSON.parse(new TextDecoder().decode(plaintext));
    const cred = (vault.credentials || []).find(c => c.id === credentialID);
    if (!cred) throw new Error('Credential not found');
    return { username: cred.username, password: cred.password };
  } finally {
    if (vaultKey) zeroBytes(vaultKey);
    if (plaintext) zeroBytes(plaintext);
  }
}

export async function saveVault(vaultJSON) {
  if (!memory.isUnlocked()) throw new Error('Vault is locked');
  let vaultKey = null;
  try {
    vaultKey = memory.getVaultKey();
    const plaintext = new TextEncoder().encode(JSON.stringify(vaultJSON));
    const encrypted = await encryptXChaCha20Poly1305(plaintext, vaultKey);
    await _storeEncryptedBlob(encrypted);
    return encrypted;
  } finally {
    if (vaultKey) zeroBytes(vaultKey);
  }
}

function _matchesDomain(uri, domain) {
  try {
    const url = new URL(uri.startsWith('http') ? uri : `https://${uri}`);
    return url.hostname === domain || url.hostname.endsWith(`.${domain}`);
  } catch { return false; }
}

function _openDB() {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, 1);
    req.onupgradeneeded = e => e.target.result.createObjectStore(DB_STORE);
    req.onsuccess = e => resolve(e.target.result);
    req.onerror = () => reject(req.error);
  });
}

async function _getEncryptedBlob() {
  const db = await _openDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(DB_STORE, 'readonly');
    const req = tx.objectStore(DB_STORE).get('blob');
    req.onsuccess = () => resolve(req.result ? new Uint8Array(req.result) : null);
    req.onerror = () => reject(req.error);
  });
}

async function _storeEncryptedBlob(blob) {
  const db = await _openDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(DB_STORE, 'readwrite');
    const req = tx.objectStore(DB_STORE).put(blob.buffer, 'blob');
    req.onsuccess = () => resolve();
    req.onerror = () => reject(req.error);
  });
}
