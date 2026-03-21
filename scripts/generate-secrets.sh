#!/usr/bin/env bash
# Generates all required secrets for .env
# Run once: ./scripts/generate-secrets.sh >> .env

set -euo pipefail

python3 - << 'PYEOF'
import base64, secrets, nacl.signing

def b64(b): return base64.b64encode(b).decode()

jwt_secret      = b64(secrets.token_bytes(32))
server_hmac_key = b64(secrets.token_bytes(32))
postgres_pw     = secrets.token_urlsafe(32)
redis_pw        = secrets.token_urlsafe(32)

signing_key = nacl.signing.SigningKey.generate()
server_sign_key_seed = b64(bytes(signing_key))

print(f"JWT_SECRET={jwt_secret}")
print(f"SERVER_SIGN_KEY_SEED={server_sign_key_seed}")
print(f"SERVER_HMAC_KEY={server_hmac_key}")
print(f"POSTGRES_PASSWORD={postgres_pw}")
print(f"REDIS_PASSWORD={redis_pw}")
print()
print("# Server Ed25519 public key (pin this in the Android app):")
print(f"# SERVER_VERIFY_KEY={b64(bytes(signing_key.verify_key))}")
PYEOF
