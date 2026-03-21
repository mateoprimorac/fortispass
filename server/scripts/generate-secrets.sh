#!/usr/bin/env bash
set -e
python3 - << 'PYEOF'
import base64, os
def b64(n): return base64.b64encode(os.urandom(n)).decode()
try:
    import nacl.signing
    sk = nacl.signing.SigningKey.generate()
    seed = base64.b64encode(bytes(sk)).decode()
except ImportError:
    seed = "INSTALL_PYNACL: pip install PyNaCl"
print(f"JWT_SECRET={b64(32)}")
print(f"SERVER_SIGN_KEY_SEED={seed}")
print(f"SERVER_HMAC_KEY={b64(32)}")
print(f"POSTGRES_PASSWORD={b64(24)}")
print(f"REDIS_PASSWORD={b64(24)}")
PYEOF
