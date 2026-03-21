/**
 * memory.js — In-memory VaultKey management.
 *
 * VaultKey is stored as a non-extractable AES-GCM CryptoKey via SubtleCrypto.
 * The raw key material can never be read back by JavaScript — only used for
 * encrypt/decrypt operations. This prevents key extraction even if an attacker
 * achieves JS execution inside the extension context.
 *
 * VaultKey is NEVER written to chrome.storage, localStorage, or IndexedDB.
 * Lives only in service worker heap. Cleared on lock/timeout/SW termination.
 *
 * KNOWN LIMITATION: Chrome MV3 service workers are ephemeral and may be
 * terminated by the browser at any time, automatically locking the vault.
 * This is a security feature, not a bug.
 */

'use strict';

class VaultMemory {
  #cryptoKey = null;   // non-extractable CryptoKey — raw bytes never accessible
  #lockedCallbacks = [];

  /**
   * Import raw key bytes as a non-extractable AES-GCM CryptoKey and store it.
   * The source bytes are zeroed immediately after import.
   * Returns a Promise that resolves when the key is ready.
   */
  async setVaultKey(keyBytes) {
    // Clear any existing key first
    this.#cryptoKey = null;

    this.#cryptoKey = await crypto.subtle.importKey(
      'raw',
      keyBytes,
      { name: 'AES-GCM' },
      false,          // extractable = false — key material cannot be read back
      ['encrypt', 'decrypt']
    );

    // Zero the source bytes — key material now lives only inside SubtleCrypto
    if (keyBytes instanceof Uint8Array) keyBytes.fill(0);
    else if (keyBytes instanceof ArrayBuffer) new Uint8Array(keyBytes).fill(0);
  }

  /**
   * Returns the stored non-extractable CryptoKey directly.
   * Callers use it for crypto.subtle.encrypt/decrypt — they never see raw bytes.
   */
  getCryptoKey() {
    if (!this.#cryptoKey) throw new Error('Vault is locked');
    return this.#cryptoKey;
  }

  isUnlocked() {
    return this.#cryptoKey !== null;
  }

  onLocked(cb) {
    this.#lockedCallbacks.push(cb);
  }

  lock() {
    // Dropping the reference is sufficient — GC will collect the CryptoKey.
    // There are no raw bytes to zero since we never held them.
    this.#cryptoKey = null;
    chrome.alarms.clear('auto-lock');
    this.#lockedCallbacks.forEach(cb => { try { cb(); } catch {} });
  }
}

export const memory = new VaultMemory();

chrome.alarms.onAlarm.addListener((alarm) => {
  if (alarm.name === 'auto-lock') {
    memory.lock();
  }
});
