# Threat Model (STRIDE)

See full threat model in the main architecture document.
This file summarises the key mitigations per component.

## Server Compromise
- Server stores only ciphertext — VaultKey never present
- Recovery blob requires 256-bit RecoveryKey to decrypt
- Session relay: server sees enc_vault_key but cannot derive SessionKey

## Network Attacker
- TLS 1.3 only, HSTS preload
- VaultKey additionally E2E-encrypted between Android and extension
- Server signature on QR payload prevents MITM QR injection

## Compromised Extension
- VaultKey zeroed on lock/timeout
- Content scripts never receive VaultKey
- Auto-lock limits exposure window

## Lost/Stolen Android Device
- VaultKey requires biometric (hardware-bound)
- Remote device revocation via API
- Recovery via 24-word phrase on new device
