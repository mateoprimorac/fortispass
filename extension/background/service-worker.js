/**
 * service-worker.js — Classic (non-module) service worker.
 *
 * "type": "module" has been removed from manifest.json because module service
 * workers do not support importScripts(), which is required to load libsodium.
 *
 * All dependencies are either inlined here or loaded via importScripts().
 * libsodium is loaded lazily — only when the user actually clicks "Show QR Code" —
 * so the SW starts up and responds to GET_STATUS even if the lib file is missing.
 */

'use strict';

// ── Crypto helpers (inlined from crypto.js — no import available in classic SW) ──

function generateSessionID() {
  return crypto.getRandomValues(new Uint8Array(32));
}

async function generateEphemeralKeyPair() {
  const keyPair = await crypto.subtle.generateKey({ name: 'X25519' }, true, ['deriveKey', 'deriveBits']);
  const publicKeyRaw = await crypto.subtle.exportKey('raw', keyPair.publicKey);
  return { privateKey: keyPair.privateKey, publicKeyRaw: new Uint8Array(publicKeyRaw), publicKey: keyPair.publicKey };
}

async function deriveSessionKey(privateKey, peerPublicKeyBytes, sessionIDBytes) {
  const peerPublicKey = await crypto.subtle.importKey('raw', peerPublicKeyBytes, { name: 'X25519' }, false, []);
  const sharedSecretBits = await crypto.subtle.deriveBits({ name: 'X25519', public: peerPublicKey }, privateKey, 256);
  const hkdfKey = await crypto.subtle.importKey('raw', sharedSecretBits, 'HKDF', false, ['deriveBits']);
  const sessionKeyBits = await crypto.subtle.deriveBits(
    { name: 'HKDF', hash: 'SHA-256', salt: sessionIDBytes, info: new TextEncoder().encode('fortispass-session-v1') },
    hkdfKey, 256
  );
  return { sessionKeyBits: new Uint8Array(sessionKeyBits) };
}

async function verifyDeviceSignature(message, signature, devicePubKeyBytes) {
  const pubKey = await crypto.subtle.importKey('raw', devicePubKeyBytes, { name: 'Ed25519' }, false, ['verify']);
  return crypto.subtle.verify({ name: 'Ed25519' }, pubKey, signature, message);
}

function zeroBytes(arr) { if (arr instanceof Uint8Array) arr.fill(0); }

function base64Encode(bytes) {
  let binary = '';
  for (let i = 0; i < bytes.length; i++) binary += String.fromCharCode(bytes[i]);
  return btoa(binary);
}

function base64Decode(str) {
  return new Uint8Array(atob(str).split('').map(c => c.charCodeAt(0)));
}

// Handles URL-safe base64 (- and _ instead of + and /) with or without padding.
// Android always encodes with Base64.URL_SAFE — use this for all server-returned fields.
function base64UrlDecode(str) {
  const standard = str.replace(/-/g, '+').replace(/_/g, '/');
  const padded = standard + '=='.slice(0, (4 - standard.length % 4) % 4);
  return base64Decode(padded);
}

function base64UrlEncode(bytes) {
  return base64Encode(bytes).replace(/\+/g, '-').replace(/\//g, '_').replace(/=/g, '');
}

// ── libsodium loader ──────────────────────────────────────────────────────────

let _sodium = null;
let _sodiumError = null;

function loadSodium() {
  if (_sodium) return _sodium;
  if (_sodiumError) throw _sodiumError;
  try {
    importScripts(chrome.runtime.getURL('lib/libsodium-wrappers.js'));
    if (!self.sodium) throw new Error('sodium global not set after importScripts');
    _sodium = self.sodium;
    return _sodium;
  } catch (e) {
    _sodiumError = new Error('libsodium not loaded — place libsodium-wrappers.js in extension/lib/. ' + e.message);
    throw _sodiumError;
  }
}

// AES-256-GCM decrypt — matches Android CryptoEngine.aesGcmDecrypt()
async function decryptAesGcm(blob, keyBytes) {
  const nonce      = blob.slice(0, 12);
  const ciphertext = blob.slice(12);
  const cryptoKey  = await crypto.subtle.importKey(
    'raw', keyBytes, { name: 'AES-GCM' }, false, ['decrypt']
  );
  const plaintext = await crypto.subtle.decrypt(
    { name: 'AES-GCM', iv: nonce, tagLength: 128 },
    cryptoKey,
    ciphertext
  );
  return new Uint8Array(plaintext);
}

function decryptXChaCha20_UNUSED(blob, key) {
  const sodium = loadSodium();
  const nonce = blob.slice(0, 24);
  const ct = blob.slice(24);
  return sodium.crypto_aead_xchacha20poly1305_ietf_decrypt(null, ct, null, nonce, key);
}

// ── In-memory vault key + cached blob ────────────────────────────────────────

let _vaultKey   = null;   // non-extractable AES-GCM CryptoKey — raw bytes never held
let _vaultCache  = null;   // { vault: Object, version: number } — cleared on lock
let _vaultToken  = null;   // Short-lived JWT for extension vault PUT

function isUnlocked() { return _vaultKey !== null; }

async function setVaultKey(keyBytes) {
  // Import as non-extractable — key material lives inside SubtleCrypto only
  _vaultKey = await crypto.subtle.importKey(
    'raw',
    keyBytes,
    { name: 'AES-GCM' },
    false,          // extractable = false
    ['encrypt', 'decrypt']
  );
  // Zero source bytes immediately — we no longer hold raw key material
  zeroBytes(keyBytes);
}

function lockVault() {
  const wasUnlocked = _vaultKey !== null;
  _vaultKey   = null;   // drop CryptoKey reference — no raw bytes to zero
  _vaultCache = null;
  _vaultToken = null;
  chrome.alarms.clear('auto-lock');
  // Only notify popup if vault was actually unlocked — prevents spurious
  // VAULT_LOCKED messages when the alarm fires after an SW restart (where
  // _vaultKey is already null because SW memory was cleared).
  if (wasUnlocked) {
    chrome.runtime.sendMessage({ type: 'VAULT_LOCKED' }).catch(() => {});
  }
}

chrome.alarms.onAlarm.addListener(alarm => {
  if (alarm.name === 'auto-lock') lockVault();
});



// ── Session management ────────────────────────────────────────────────────────

let _activeWS = null;

async function getRelayURL() {
  const { relayURL } = await chrome.storage.local.get('relayURL');
  if (!relayURL) throw new Error('Relay URL not configured. Open fortispass settings first.');
  return relayURL.replace(/\/$/, '');
}

async function createUnlockSession() {
  const RELAY = await getRelayURL();
  const sessionIDBytes = generateSessionID();
  const { privateKey: ephPrivKey, publicKeyRaw: ephPubBytes } = await generateEphemeralKeyPair();
  const { qrExpirySecs } = await chrome.storage.local.get('qrExpirySecs');
  const expirySecs = Math.min(50, Math.max(20, parseInt(qrExpirySecs) || 45));
  const expiry = Math.floor(Date.now() / 1000) + expirySecs;

  // Use URL-safe base64 everywhere so session ID is safe in URL paths
  const sidB64  = base64UrlEncode(sessionIDBytes);
  const epkB64  = base64UrlEncode(ephPubBytes);

  const resp = await fetch(`${RELAY}/api/v1/session/create`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id: sidB64, ext_pub_key: epkB64, expiry }),
  });
  if (!resp.ok) throw new Error(`Session create failed: ${resp.status}`);
  const { server_sig, relay_url } = await resp.json();
  const resolvedRelay = relay_url || RELAY;

  const qrPayload = JSON.stringify({
    v: 1,
    sid: sidB64,
    epk: epkB64,
    url: resolvedRelay,
    exp: expiry,
    sig: base64UrlEncode(base64Decode(server_sig)),
  });

  // Wait for Android response in background
  _waitForResponse(resolvedRelay, sidB64, sessionIDBytes, ephPrivKey, expirySecs);

  return { qrPayload, expirySecs };
}

function cancelUnlockSession() {
  if (_activeWS) {
    _activeWS._suppressClose = true; // user-initiated close — suppress onclose/onerror noise
    _activeWS.close();
    _activeWS = null;
  }
}

function _waitForResponse(RELAY, sidB64, sessionIDBytes, ephPrivKey, expirySecs) {
  const wsURL = RELAY.replace('https://', 'wss://').replace('http://', 'ws://') + `/api/v1/session/ws/${sidB64}`;
  _activeWS = new WebSocket(wsURL);

  const timeout = setTimeout(() => {
    if (_activeWS) {
      _activeWS._suppressClose = true; // expiry-initiated — handled here, not by onclose
      _activeWS.close();
      _activeWS = null;
    }
    // QR_EXPIRED: popup goes silently back to locked view, no error shown
    chrome.runtime.sendMessage({ type: 'QR_EXPIRED' }).catch(() => {});
  }, expirySecs * 1000 + 2000); // extra 2 s buffer for network

  _activeWS.onmessage = async (event) => {
    const msg = JSON.parse(event.data);
    if (msg.event === 'biometric_started') {
      chrome.runtime.sendMessage({ type: 'BIOMETRIC_STARTED' }).catch(() => {});
      return;
    }
    if (msg.event === 'biometric_failed') {
      clearTimeout(timeout);
      _activeWS = null;
      chrome.runtime.sendMessage({ type: 'BIOMETRIC_FAILED' }).catch(() => {});
      return;
    }
    if (msg.event !== 'session_responded') return;
    clearTimeout(timeout);
    _activeWS.close(); _activeWS = null;
    try {
      await _retrieveAndDecrypt(RELAY, sidB64, sessionIDBytes, ephPrivKey);
      const { autoLockMinutes = 15 } = await chrome.storage.local.get('autoLockMinutes');
      const lockDelay = Math.max(1, parseInt(autoLockMinutes) || 15);
      await chrome.alarms.clear('auto-lock');
      chrome.alarms.create('auto-lock', { delayInMinutes: lockDelay });
      chrome.runtime.sendMessage({ type: 'UNLOCK_COMPLETE' }).catch(() => {});
    } catch (e) {
      chrome.runtime.sendMessage({ type: 'UNLOCK_FAILED', error: e.message }).catch(() => {});
    }
  };

  _activeWS.onerror = (ev) => {
    if (ev.target?._suppressClose) return;
    clearTimeout(timeout); _activeWS = null;
    chrome.runtime.sendMessage({ type: 'UNLOCK_FAILED', error: 'WebSocket connection failed' }).catch(() => {});
  };

  _activeWS.onclose = (ev) => {
    if (ev.target?._suppressClose) { clearTimeout(timeout); return; }
    clearTimeout(timeout); _activeWS = null;
    if (ev.code !== 1000) {
      chrome.runtime.sendMessage({ type: 'UNLOCK_FAILED', error: `Relay closed connection (${ev.code})` }).catch(() => {});
    }
  };
}

async function _retrieveAndDecrypt(RELAY, sidB64, sessionIDBytes, ephPrivKey) {
  const resp = await fetch(`${RELAY}/api/v1/session/retrieve/${sidB64}`);
  if (!resp.ok) throw new Error(`Session retrieve failed: ${resp.status}`);
  const { dev_eph_pub, enc_vault_key, sig, enc_vault_blob, vault_version, vault_token } = await resp.json();

  const devEphPubBytes   = base64UrlDecode(dev_eph_pub);
  const encVaultKeyBytes = base64UrlDecode(enc_vault_key);
  const sigBytes         = base64UrlDecode(sig);

  const { deviceSigningPubKey } = await chrome.storage.local.get('deviceSigningPubKey');
  if (deviceSigningPubKey) {
    const pubKeyBytes = base64Decode(deviceSigningPubKey);
    const msg = new Uint8Array(32 + 32 + encVaultKeyBytes.length);
    msg.set(sessionIDBytes, 0);
    msg.set(devEphPubBytes, 32);
    msg.set(encVaultKeyBytes, 64);
    const valid = await verifyDeviceSignature(msg, sigBytes, pubKeyBytes);
    if (!valid) throw new Error('SECURITY: Device signature invalid');
  }

  let sessionKeyBits;
  try {
    ({ sessionKeyBits } = await deriveSessionKey(ephPrivKey, devEphPubBytes, sessionIDBytes));
    const vaultKey = await decryptAesGcm(encVaultKeyBytes, sessionKeyBits);
    await setVaultKey(vaultKey);
  } finally {
    if (sessionKeyBits) zeroBytes(sessionKeyBits);
  }

  // Store vault write token (issued by server at unlock, 1h lifetime)
  if (vault_token) _vaultToken = vault_token;

  // Decode and cache the vault blob using the now-set vault key
  if (enc_vault_blob) {
    try {
      const blobBytes = base64Decode(enc_vault_blob);
      let vault;
      if (blobBytes.length <= 28) {
        vault = { v: 1, credentials: [], totps: [] };
      } else {
        const pt = await decryptVaultBlob(blobBytes);
        vault = JSON.parse(new TextDecoder().decode(pt));
        if (!vault.credentials) vault.credentials = [];
        if (!vault.totps) vault.totps = [];
      }
      _vaultCache = { vault, version: vault_version ?? 1 };
    } catch (e) {
      // Non-fatal — vault will be fetched fresh on first access
      _vaultCache = { vault: { v: 1, credentials: [], totps: [] }, version: vault_version ?? 1 };
    }
  } else {
    _vaultCache = { vault: { v: 1, credentials: [], totps: [] }, version: 1 };
  }
}

// ── Message handler ───────────────────────────────────────────────────────────

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  (sender.tab ? handleContent(msg, sender, sendResponse)
              : handlePopup(msg, sendResponse));
  return true;
});

// ── Vault crypto ─────────────────────────────────────────────────────────────
// Vault format: AES-256-GCM, 12-byte nonce prepended — identical to Android CryptoEngine.

async function encryptVaultBlob(plaintext) {
  const nonce = crypto.getRandomValues(new Uint8Array(12));
  // _vaultKey is already a non-extractable CryptoKey — use it directly
  const ct = await crypto.subtle.encrypt({ name: 'AES-GCM', iv: nonce, tagLength: 128 }, _vaultKey, plaintext);
  const out = new Uint8Array(12 + ct.byteLength);
  out.set(nonce, 0);
  out.set(new Uint8Array(ct), 12);
  return out;
}

async function decryptVaultBlob(blob) {
  const nonce = blob.slice(0, 12);
  const ct    = blob.slice(12);
  // _vaultKey is already a non-extractable CryptoKey — use it directly
  const pt    = await crypto.subtle.decrypt({ name: 'AES-GCM', iv: nonce, tagLength: 128 }, _vaultKey, ct);
  return new Uint8Array(pt);
}

// ── Vault fetch/save against relay ───────────────────────────────────────────


function getVaultCache() {
  return _vaultCache;
}

async function fetchAndDecryptVault() {
  if (_vaultCache) return _vaultCache;
  throw new Error('Vault not available — please unlock again');
}

async function encryptAndSaveVault(vault, currentVersion) {
  if (!_vaultToken) throw new Error('No vault write token — please re-unlock');
  const RELAY = await getRelayURL();
  const pt      = new TextEncoder().encode(JSON.stringify(vault));
  const blob    = await encryptVaultBlob(pt);
  const blobB64 = base64Encode(blob);
  const hashBuf = await crypto.subtle.digest('SHA-256', blob);
  const hashB64 = base64Encode(new Uint8Array(hashBuf));
  const resp = await fetch(`${RELAY}/api/v1/vault`, {
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${_vaultToken}`,
    },
    body: JSON.stringify({
      encrypted_blob: blobB64,
      blob_hash: hashB64,
      version: currentVersion + 1,
    }),
  });
  if (resp.status === 409) throw new Error('VERSION_CONFLICT');
  if (!resp.ok) throw new Error(`Vault save failed: ${resp.status}`);
  const newVersion = (await resp.json()).version;
  _vaultCache = { vault, version: newVersion };
  return newVersion;
}

// ── TOTP ──────────────────────────────────────────────────────────────────────

function base32Decode(s) {
  const ALPHA = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ234567';
  s = s.replace(/=+$/, '').toUpperCase().replace(/\s/g, '');
  let bits = 0, val = 0;
  const out = [];
  for (const c of s) {
    val = (val << 5) | ALPHA.indexOf(c);
    bits += 5;
    if (bits >= 8) { out.push((val >>> (bits - 8)) & 0xff); bits -= 8; }
  }
  return new Uint8Array(out);
}

async function computeTotp(secret, { digits = 6, period = 30, algorithm = 'SHA-1' } = {}) {
  const key = base32Decode(secret);
  const counter = Math.floor(Date.now() / 1000 / period);
  const msg = new Uint8Array(8);
  let c = counter;
  for (let i = 7; i >= 0; i--) { msg[i] = c & 0xff; c = Math.floor(c / 256); }
  const cryptoKey = await crypto.subtle.importKey(
    'raw', key,
    { name: 'HMAC', hash: algorithm === 'SHA-256' ? 'SHA-256' : algorithm === 'SHA-512' ? 'SHA-512' : 'SHA-1' },
    false, ['sign']
  );
  const sig = new Uint8Array(await crypto.subtle.sign('HMAC', cryptoKey, msg));
  const offset = sig[sig.length - 1] & 0x0f;
  const code = ((sig[offset] & 0x7f) << 24 | sig[offset+1] << 16 | sig[offset+2] << 8 | sig[offset+3]) % Math.pow(10, digits);
  return String(code).padStart(digits, '0');
}

function totpTimeRemaining(period = 30) {
  return period - (Math.floor(Date.now() / 1000) % period);
}

// ── Message handler ───────────────────────────────────────────────────────────

async function handlePopup(msg, sendResponse) {
  try {
    switch (msg.type) {
      case 'GET_STATUS':
        sendResponse({ locked: !isUnlocked() });
        break;

      case 'START_UNLOCK': {
        const { qrPayload, expirySecs } = await createUnlockSession();
        sendResponse({ qrPayload, expirySecs });
        break;
      }

      case 'CANCEL_UNLOCK':
        cancelUnlockSession();
        sendResponse({});
        break;

      case 'LOCK':
        lockVault();
        sendResponse({});
        break;

      case 'GET_VAULT': {
        if (!isUnlocked()) { sendResponse({ locked: true }); break; }
        const { vault, version } = await fetchAndDecryptVault();
        sendResponse({ vault, version });
        break;
      }

      case 'SAVE_VAULT': {
        if (!isUnlocked()) { sendResponse({ locked: true }); break; }
        const newVersion = await encryptAndSaveVault(msg.vault, msg.version);
        sendResponse({ version: newVersion });
        break;
      }

      case 'GET_TOTP': {
        if (!isUnlocked()) { sendResponse({ locked: true }); break; }
        const code = await computeTotp(msg.secret, { digits: msg.digits, period: msg.period, algorithm: msg.algorithm });
        sendResponse({ code, remaining: totpTimeRemaining(msg.period || 30) });
        break;
      }

      default:
        sendResponse({ error: 'Unknown message type' });
    }
  } catch (e) {
    sendResponse({ error: e.message });
  }
}

async function handleContent(msg, sender, sendResponse) {
  if (!sender.tab?.url?.startsWith('https://')) { sendResponse({ error: 'HTTPS required' }); return; }
  const tabDomain = new URL(sender.tab.url).hostname;
  try {
    switch (msg.type) {
      case 'GET_CREDENTIALS': {
        if (!isUnlocked()) { sendResponse({ locked: true }); return; }
        const { vault } = await fetchAndDecryptVault();
        const matches = (vault.credentials || []).filter(c => {
          if (!c.url) return false;
          try { return new URL(c.url).hostname === tabDomain; } catch { return false; }
        });
        // Never send passwords to the content script — only metadata needed to show the UI
        sendResponse({ credentials: matches.map(c => ({ id: c.id, name: c.name, username: c.username, url: c.url })) });
        break;
      }
      case 'FILL_CREDENTIAL': {
        if (!isUnlocked()) { sendResponse({ locked: true }); return; }
        const { vault } = await fetchAndDecryptVault();
        const cred = (vault.credentials || []).find(c => c.id === msg.credentialID);
        if (!cred) { sendResponse({ error: 'Not found' }); return; }
        // Double-check the credential's domain still matches the tab — sender.tab.url
        // comes from Chrome's verified tab state, not from the page itself.
        const credDomain = cred.url ? (() => { try { return new URL(cred.url).hostname; } catch { return null; } })() : null;
        if (!credDomain || credDomain !== tabDomain) { sendResponse({ error: 'Domain mismatch' }); return; }
        // Inject the fill function directly into the page via chrome.scripting.
        // Credentials are passed as args and land in the DOM without ever travelling
        // through content script message callbacks — an XSS on the page cannot
        // intercept executeScript calls originating from the service worker.
        await chrome.scripting.executeScript({
          target: { tabId: sender.tab.id },
          func: (username, password) => {
            const usernameField = document.querySelector(
              'input[autocomplete="username"], input[type="email"], input[name*="user"], input[name*="email"]'
            );
            const passwordField = document.querySelector('input[type="password"]');
            if (usernameField && username) {
              usernameField.value = username;
              usernameField.dispatchEvent(new Event('input', { bubbles: true }));
              usernameField.dispatchEvent(new Event('change', { bubbles: true }));
            }
            if (passwordField && password) {
              passwordField.value = password;
              passwordField.dispatchEvent(new Event('input', { bubbles: true }));
              passwordField.dispatchEvent(new Event('change', { bubbles: true }));
            }
          },
          args: [cred.username, cred.password],
        });
        sendResponse({ filled: true });
        break;
      }
      default:
        sendResponse({ error: 'Unknown message' });
    }
  } catch (e) {
    sendResponse({ error: 'Internal error' });
  }
}
