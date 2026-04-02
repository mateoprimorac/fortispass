<div align="center">
<h1 align="center">fortispass</h1>

<a href="https://fortispass.com/"><img style="display: block; margin: auto;" width="500" height="250" alt="Fortispass logo" src="https://github.com/user-attachments/assets/a675cf0c-0418-4968-9ddf-dbaa902ec647"/></a>

<h4 align="center">
    <a href="https://github.com/mateoprimorac/fortispass/releases/tag/v1.0.1-kyubey" target="_blank">
        <img src="https://img.shields.io/badge/version-1.0.0-blue" alt="Version">
    </a>
    <a href="https://github.com/mateoprimorac/fortispass/commits/main/">
        <img src="https://img.shields.io/github/commit-activity/w/mateoprimorac/fortispass" alt="Commit activity">
    </a>
    <a href="https://github.com/mateoprimorac/fortispass/blob/main/LICENSE">
        <img src="https://img.shields.io/github/license/mateoprimorac/fortispass" alt="License">
    </a>
</h4>
</div>

A **self-hosted, zero-knowledge password manager** with biometric QR unlock.<br>Your vault is AES-256-GCM encrypted on your device at all times.<br>The relay server stores only ciphertext it cannot decrypt. 

The **ONLY** official website for this project: [fortispass.com](https://fortispass.com)

## Components

**Server**: Python 3.11, FastAPI, PostgreSQL, Redis, Docker

**Android app**: Kotlin, CameraX, ML Kit, lazysodium-android

**Chromium extension**: JavaScript, WebCrypto API, Manifest V3

---

## Prerequisites

- **Server:** Docker 24+ and Docker Compose v2, Python 3.11+
- **Android:** Android 9.0+ (API 28), biometric hardware, hardware-backed Android Keystore
- **Extension:** Chrome 113+ or any Chromium-based browser with Manifest V3 support

## Server setup

Everything is managed through `server.py`. You do not need to edit Docker or config files directly.
You do need to be running a Docker instance before running `server.py`.

```bash
git clone https://github.com/mateoprimorac/fortispass.git
cd fortispass
python server.py
```

On first run the script installs missing Python dependencies, generates all secrets (JWT key, Ed25519 signing key, HMAC key, database and Redis passwords), writes them to `.env`, builds the Docker stack, applies the database schema, and shows a live dashboard with your local IP, port, CPU, RAM, and uptime.

The default port is 8080. To change it:

```bash
python server.py --port 9000
```

To set the maximum number of devices per vault (default 3):

```bash
python server.py --max-devices 5
```

### Firewall

If connecting from another device on your network, allow the port through your firewall.

**Windows (PowerShell, admin):**
```powershell
New-NetFirewallRule -DisplayName "fortispass" -Direction Inbound -Protocol TCP -LocalPort 8080 -Action Allow
```

**Linux:**
```bash
sudo ufw allow 8080/tcp
```

**macOS:** System Settings, Network, Firewall, Options, then add the port.

### Other commands

```bash
python server.py --stop                # stop containers, preserve data
python server.py --wipe                # stop and delete all data (irreversible)
python server.py --restore             # restore from a Google Drive backup
python server.py --backup              # configure automated Google Drive backups
python server.py --interval 2          # set backup interval to 2 hours (1-48)
python server.py --max-devices 5       # set maximum devices per vault (default 3)
python server.py --port 9000           # start on a different port
```

Pressing Ctrl+C detaches the dashboard. The server keeps running in Docker.

---

## How the unlock works

The extension cannot ask for your biometrics directly, so it delegates to your phone. When you click the extension icon, it generates a random session ID and a one-time X25519 keypair, registers the session with your server, and renders a QR code.

You scan the QR with the Android app. The app verifies the server's Ed25519 signature on the QR payload to confirm it came from a trusted server, then triggers a biometric prompt. On success, the Keystore releases the wrapped vault key.

The app generates its own one-time X25519 keypair and performs an ECDH key exchange with the extension's public key. Both sides independently derive the same 256-bit session key using HKDF-SHA256 with the session ID as salt. The server sees both public keys in transit but cannot compute the shared secret because that requires a private key, which never leaves either device.

The app encrypts the vault key with AES-256-GCM using the session key and posts the ciphertext to the server. The server forwards a notification to the extension over WebSocket. The extension fetches the ciphertext, derives the same session key independently, and decrypts the vault key. The vault key lives in service worker memory until the auto-lock timer fires or the browser closes.

---

## Authorization flow

When a user opens the extension popup, the extension creates a session on the relay server by posting a randomly generated session ID and its ephemeral X25519 public key. The server signs the payload with its Ed25519 key and returns the signature. The extension displays all of this as a QR code and opens a WebSocket connection to wait for the result.

On the Android side, the user taps Scan QR. The app reads the QR, verifies the server signature against a pinned server public key (set during first registration), and confirms the session has not expired. It then prompts biometric authentication. On success, the Keystore releases the wrapped vault key into memory.

The app generates a fresh ephemeral X25519 keypair, computes the ECDH shared secret with the extension's public key, and derives a session key with HKDF-SHA256 using the session ID as the salt and `fortispass-session-v1` as the info string. It encrypts the vault key with AES-256-GCM under this session key and posts the result to the server along with its ephemeral public key and an Ed25519 signature.

The server notifies the waiting extension via WebSocket. The extension fetches the encrypted payload, repeats the same HKDF derivation using the app's ephemeral public key and the session ID, decrypts the vault key, and stores it as a non-extractable `CryptoKey` in service worker memory. The vault is now unlocked.

---

## Security properties

**Zero knowledge.** The server stores only ciphertext. Even with full access to the database, the ciphertext cannot be decrypted without the vault key, which is never transmitted to the server in any form.

**Perfect forward secrecy.** Fresh X25519 keypairs are generated for every unlock session. Compromising one session's ephemeral keys does not reveal any past or future sessions.

**Hardware-bound vault key.** On Android, the vault key is wrapped by an AES-256-GCM key that lives in the Trusted Execution Environment (TEE) or StrongBox chip and requires biometric authentication to use. The raw key bytes never appear in application memory without biometric approval.

**Non-extractable extension key.** Once decrypted on the extension side, the vault key is stored as a `CryptoKey` with `extractable: false`. JavaScript code running in the extension context can use the key for encrypt and decrypt operations but cannot read the raw bytes.

**No trust in the relay.** The relay server is treated as untrusted by design. It never sees a session key, a plaintext vault key, or any plaintext vault contents. The ECDH secret is computed independently on each device and never transmitted.

**Recovery phrase.** The vault key is deterministically derived from a 24-word BIP39-style mnemonic phrase generated at registration. The phrase has approximately 262 bits of entropy, which exceeds a raw 256-bit AES key. If you lose your device you can restore the vault on a new device using only the phrase and your relay URL, with no server-side recovery blob required.

---

## Encryption

The vault is encrypted with AES-256-GCM, which provides both confidentiality and authentication. Any modification to the ciphertext causes decryption to fail, so the server cannot tamper with vault contents without the client detecting it.

On Android, the vault key itself is wrapped by a second AES-256-GCM key that lives inside the Trusted Execution Environment or StrongBox chip and requires biometric authentication to use. The raw vault key bytes never appear in application memory without an authenticated biometric operation.

When unlocking through the extension, the vault key is transferred using an ephemeral X25519 Diffie-Hellman exchange. Both sides generate a one-time keypair per session, derive the same shared secret independently, and then use HKDF-SHA256 (info string `fortispass-session-v1`) to produce the session encryption key. The relay server sees both public keys in transit but cannot compute the shared secret without one of the private keys.

Device identity (used for signing QR payloads and verifying session responses) is based on Ed25519, which offers fast signing, compact 64-byte signatures, and no weak-parameter edge cases.

JWTs that gate authenticated API calls are signed with HMAC-SHA256. In a single-server deployment this is sufficient because the server is both the signer and the verifier.

The 24-word recovery phrase is the canonical source of the vault key. The vault key is derived from the phrase with HKDF-SHA256 (info string `fortispass-recovery-v1`), so the same phrase always produces the same vault key. In the extension, the vault key is held as a `SubtleCrypto CryptoKey` with `extractable: false`, meaning JavaScript running in the extension context can use the key for operations but cannot read the raw bytes.

---

## Android app setup

The following is how to build your own android application of this project. There should be an already built .apk in the releases section of this GitHub repository.

### Building

```bash
cd android
./gradlew assembleDebug
# Output: app/build/outputs/apk/debug/app-debug.apk
```

### First run

Open the app and tap **Create Vault**. Enter your relay server URL using your machine's LAN IP, for example `http://192.168.1.10:8080`. Give the device a name and complete biometric enrollment when prompted.

The vault key is generated on-device from a 24-word recovery phrase, wrapped in hardware, and biometric-gated from this point on. The recovery phrase is available in Settings. Write it down and store it somewhere safe. After you confirm it, the button disappears permanently.

### Adding more devices

Open the app on the existing device, go to Settings, and tap **Add Device**. A QR code appears. On the new device, open the app, tap **Log In Vault**, then **Scan Invite QR**, and scan the code. The vault key is transferred directly between the devices over ECDH, encrypted, through the relay. The server never sees the plaintext key.

By default a vault can have up to 3 devices. The server operator can change this with `--max-devices`.

---

## Extension setup
The following is how to setup the unpacked Chromium extension of this project. There should be an already packed extension in the releases section of this GitHub repository.

1. Go to `chrome://extensions`
2. Enable **Developer mode** in the top right
3. Click **Load unpacked** and select the `extension/` folder
4. Pin the extension to your toolbar
5. Open it and enter your relay server URL

---

## Unlocking

1. Click the extension icon to show the QR code
2. Open the fortispass app and tap **Scan QR**
3. Scan the code and authenticate with biometrics
4. The extension unlocks automatically

The vault stays unlocked until the auto-lock timer fires or you close the browser.

---

## Donate

BTC: ```bc1qy72r725p0g26d2qvqcdnpplrcswlh04eea8h64```<br>ETH: ```0xfEB014A24A0ef5CC66d09E4516B0D940a110Ae9C```<br>XMR: ```44B3TqWQYv2Vqye34EZKcU7xHSaYANYEYAx7h5P42T5vLfC7Gg87Fk39zXGCMkGFxDc6m51oTtmnMbb7QcTucmf6SZahi7r```

This project was made for the [SUMIT Code Challenge 2026 hackathon](https://skole.hackathon.sum.ba/) with the theme being cybersecurity.<br> I didn't put any "donate" buttons inside the project, and I never will, I want it to look clean and professional.<br>If you cannot afford to donate but like the project, spread the word, star the project on GitHub! It helps a lot!

---

## License

Fortispass is licensed under the [MIT License](https://opensource.org/license/MIT).<br>
See [LICENSE](LICENSE).

