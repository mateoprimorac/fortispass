-- biokey — PostgreSQL Schema (passwordless, device-key auth)

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- An account is just an identity anchor — no email, no password.
-- Authentication is purely by device Ed25519 key signature.
CREATE TABLE IF NOT EXISTS accounts (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    label       TEXT,           -- optional human-readable name, set by the device
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS devices (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id      UUID NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    device_name     TEXT NOT NULL,
    device_type     TEXT NOT NULL CHECK (device_type IN ('android', 'extension')),
    dh_public_key   BYTEA NOT NULL,
    signing_pub_key BYTEA NOT NULL,
    is_revoked      BOOLEAN NOT NULL DEFAULT FALSE,
    revoked_at      TIMESTAMPTZ,
    revoked_by      UUID REFERENCES devices(id),
    last_seen       TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_devices_account        ON devices(account_id);
CREATE INDEX IF NOT EXISTS idx_devices_account_active ON devices(account_id) WHERE is_revoked = FALSE;

CREATE TABLE IF NOT EXISTS vault_blobs (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id     UUID NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    encrypted_blob BYTEA NOT NULL,
    version        BIGINT NOT NULL DEFAULT 1,
    blob_hash      BYTEA NOT NULL,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(account_id)
);

CREATE TABLE IF NOT EXISTS audit_log (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id  UUID REFERENCES accounts(id) ON DELETE SET NULL,
    device_id   UUID REFERENCES devices(id) ON DELETE SET NULL,
    event_type  TEXT NOT NULL,
    ip_address  INET,
    user_agent  TEXT,
    metadata    JSONB,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_audit_account ON audit_log(account_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_event   ON audit_log(event_type,  created_at DESC);

-- Recovery phrase confirmation flag
-- Set to TRUE once the device owner has verified they wrote the mnemonic down correctly.
-- Persists across device reinstalls — tied to the account, not the device.
ALTER TABLE accounts ADD COLUMN IF NOT EXISTS mnemonic_confirmed BOOLEAN NOT NULL DEFAULT FALSE;

-- vault_lookup_hash: HMAC-SHA256(vaultKey, "fortispass-vault-lookup-v1"), base64url
-- Allows recovery-phrase login without knowing a device_id.
-- Safe to store: an attacker with the hash cannot derive the vault key (HMAC is one-way).
ALTER TABLE accounts ADD COLUMN IF NOT EXISTS vault_lookup_hash TEXT;
CREATE UNIQUE INDEX IF NOT EXISTS idx_accounts_vault_lookup ON accounts(vault_lookup_hash)
    WHERE vault_lookup_hash IS NOT NULL;

-- Device invite tokens — used for "Add Device" pairing flow.
-- Expires after 5 minutes. Consumed after delivery.
CREATE TABLE IF NOT EXISTS device_invites (
    token           TEXT PRIMARY KEY,            -- 32-byte random, base64url
    account_id      UUID NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    inviting_device UUID NOT NULL REFERENCES devices(id),
    inviting_dh_pub BYTEA NOT NULL,              -- Device A's X25519 pub (for ECDH)
    joiner_dh_pub   BYTEA,                       -- Device B's X25519 pub (set on accept)
    joiner_sign_pub BYTEA,                       -- Device B's Ed25519 pub
    joiner_name     TEXT,
    encrypted_vault_key BYTEA,                   -- AES-GCM(sharedKey, vaultKey) — set by Device A
    state           TEXT NOT NULL DEFAULT 'pending'
                        CHECK (state IN ('pending','accepted','delivered','consumed')),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at      TIMESTAMPTZ NOT NULL DEFAULT now() + INTERVAL '5 minutes'
);
CREATE INDEX IF NOT EXISTS idx_device_invites_account ON device_invites(account_id);
