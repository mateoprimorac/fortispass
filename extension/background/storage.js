'use strict';

/**
 * Persistent storage for the extension.
 * Only encrypted data is persisted. VaultKey is NEVER stored here.
 */

const DB_NAME = 'fortispass';
const DB_VERSION = 1;

function openDB() {
    return new Promise((resolve, reject) => {
        const req = indexedDB.open(DB_NAME, DB_VERSION);
        req.onupgradeneeded = (e) => {
            const db = e.target.result;
            if (!db.objectStoreNames.contains('vault')) {
                db.createObjectStore('vault');
            }
            if (!db.objectStoreNames.contains('device')) {
                db.createObjectStore('device');
            }
            if (!db.objectStoreNames.contains('settings')) {
                db.createObjectStore('settings');
            }
        };
        req.onsuccess = (e) => resolve(e.target.result);
        req.onerror = (e) => reject(e.target.error);
    });
}

async function dbGet(store, key) {
    const db = await openDB();
    return new Promise((resolve, reject) => {
        const tx = db.transaction(store, 'readonly');
        const req = tx.objectStore(store).get(key);
        req.onsuccess = () => resolve(req.result ?? null);
        req.onerror = () => reject(req.error);
    });
}

async function dbSet(store, key, value) {
    const db = await openDB();
    return new Promise((resolve, reject) => {
        const tx = db.transaction(store, 'readwrite');
        tx.objectStore(store).put(value, key);
        tx.oncomplete = () => resolve();
        tx.onerror = () => reject(tx.error);
    });
}

// ─── Encrypted vault blob ─────────────────────────────────────────────────────

export async function getEncryptedVaultBlob() {
    const raw = await dbGet('vault', 'blob');
    return raw ? new Uint8Array(raw) : null;
}

export async function setEncryptedVaultBlob(blobBytes) {
    await dbSet('vault', 'blob', blobBytes.buffer);
}

export async function getVaultVersion() {
    return (await dbGet('vault', 'version')) ?? 0;
}

export async function setVaultVersion(v) {
    await dbSet('vault', 'version', v);
}

// ─── Device public keys (for signature verification) ─────────────────────────

export async function getDeviceSigningPubKey() {
    const raw = await dbGet('device', 'signing_pub_key');
    return raw ? new Uint8Array(raw) : null;
}

export async function setDeviceSigningPubKey(keyBytes) {
    await dbSet('device', 'signing_pub_key', keyBytes.buffer);
}

// ─── Settings ─────────────────────────────────────────────────────────────────

export async function getAutoLockMinutes() {
    return (await dbGet('settings', 'auto_lock_minutes')) ?? 15;
}

export async function setAutoLockMinutes(minutes) {
    await dbSet('settings', 'auto_lock_minutes', minutes);
}
