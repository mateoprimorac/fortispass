"""
PostgreSQL helpers — passwordless edition.
All queries use parameterised statements. Never interpolate user input.
"""
from __future__ import annotations

import hashlib
from typing import Any
from uuid import UUID

import asyncpg


async def create_pool(dsn: str) -> asyncpg.Pool:
    return await asyncpg.create_pool(dsn, min_size=2, max_size=10)


# ── Accounts ──────────────────────────────────────────────────────────────────

async def create_account(conn, label: str | None = None) -> UUID:
    row = await conn.fetchrow(
        "INSERT INTO accounts (label) VALUES ($1) RETURNING id", label
    )
    return row["id"]


async def get_account(conn_or_pool, account_id: UUID):
    return await conn_or_pool.fetchrow(
        "SELECT * FROM accounts WHERE id = $1", account_id
    )


# ── Devices ───────────────────────────────────────────────────────────────────

async def create_device(
    conn,
    account_id: UUID,
    name: str,
    device_type: str,
    dh_public_key: bytes,
    signing_pub_key: bytes,
) -> UUID:
    row = await conn.fetchrow(
        """
        INSERT INTO devices (account_id, device_name, device_type, dh_public_key, signing_pub_key)
        VALUES ($1, $2, $3, $4, $5) RETURNING id
        """,
        account_id, name, device_type, dh_public_key, signing_pub_key,
    )
    return row["id"]


async def get_device(conn_or_pool, device_id: UUID):
    return await conn_or_pool.fetchrow(
        "SELECT * FROM devices WHERE id = $1", device_id
    )


async def get_active_devices_for_account(conn_or_pool, account_id: UUID):
    return await conn_or_pool.fetch(
        "SELECT * FROM devices WHERE account_id = $1 AND is_revoked = FALSE ORDER BY created_at",
        account_id,
    )


async def update_device_last_seen(conn_or_pool, device_id: UUID) -> None:
    await conn_or_pool.execute(
        "UPDATE devices SET last_seen = now() WHERE id = $1", device_id
    )


# ── Vault blobs ───────────────────────────────────────────────────────────────

async def upsert_vault(
    conn, account_id: UUID, encrypted_blob: bytes, blob_hash: bytes, version: int
) -> None:
    await conn.execute(
        """
        INSERT INTO vault_blobs (account_id, encrypted_blob, blob_hash, version)
        VALUES ($1, $2, $3, $4)
        ON CONFLICT (account_id) DO UPDATE
          SET encrypted_blob = EXCLUDED.encrypted_blob,
              blob_hash      = EXCLUDED.blob_hash,
              version        = EXCLUDED.version,
              updated_at     = now()
        """,
        account_id, encrypted_blob, blob_hash, version,
    )


async def update_vault(
    pool, account_id: UUID, encrypted_blob: bytes, blob_hash: bytes, expected_version: int
) -> "int | None":
    """
    Optimistic-locking update. Returns new version on success, None on version conflict.
    expected_version is the version the client is sending (current+1).
    We only commit if DB version == expected_version - 1.
    """
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            UPDATE vault_blobs
               SET encrypted_blob = $1,
                   blob_hash      = $2,
                   version        = $4,
                   updated_at     = now()
             WHERE account_id = $3
               AND version    = $4 - 1
            RETURNING version
            """,
            encrypted_blob, blob_hash, account_id, expected_version,
        )
    return row["version"] if row else None


async def get_vault(conn_or_pool, account_id: UUID):
    return await conn_or_pool.fetchrow(
        "SELECT * FROM vault_blobs WHERE account_id = $1", account_id
    )


# ── Audit log ─────────────────────────────────────────────────────────────────

async def write_audit_event(
    conn_or_pool,
    *,
    event_type: str,
    account_id: UUID | None = None,
    device_id: UUID | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    import json
    await conn_or_pool.execute(
        """
        INSERT INTO audit_log (account_id, device_id, event_type, ip_address, user_agent, metadata)
        VALUES ($1, $2, $3, $4::inet, $5, $6::jsonb)
        """,
        account_id, device_id, event_type, ip_address, user_agent,
        json.dumps(metadata) if metadata else None,
    )


async def get_mnemonic_confirmed(conn_or_pool, account_id) -> bool:
    """Returns True if the account owner has confirmed their mnemonic phrase."""
    row = await conn_or_pool.fetchrow(
        "SELECT mnemonic_confirmed FROM accounts WHERE id = $1", account_id
    )
    return bool(row["mnemonic_confirmed"]) if row else False


async def set_mnemonic_confirmed(conn_or_pool, account_id) -> None:
    """Marks the mnemonic as confirmed for this account. Idempotent."""
    await conn_or_pool.execute(
        "UPDATE accounts SET mnemonic_confirmed = TRUE WHERE id = $1", account_id
    )


async def get_vault_by_device_id(conn_or_pool, device_id) -> dict | None:
    """Fetch vault blob for a device's account — used for recovery phrase login."""
    row = await conn_or_pool.fetchrow(
        """SELECT vb.encrypted_blob, vb.version, vb.blob_hash,
                  d.account_id, d.signing_pub_key, d.dh_public_key,
                  a.mnemonic_confirmed
           FROM devices d
           JOIN vault_blobs vb ON vb.account_id = d.account_id
           JOIN accounts a ON a.id = d.account_id
           WHERE d.id = $1 AND d.is_revoked = FALSE""",
        device_id,
    )
    return dict(row) if row else None


async def set_vault_lookup_hash(conn_or_pool, account_id, lookup_hash: str) -> None:
    await conn_or_pool.execute(
        "UPDATE accounts SET vault_lookup_hash = $1 WHERE id = $2",
        lookup_hash, account_id,
    )


async def get_vault_by_lookup_hash(conn_or_pool, lookup_hash: str) -> dict | None:
    row = await conn_or_pool.fetchrow(
        """SELECT vb.encrypted_blob, vb.version, vb.blob_hash,
                  a.id AS account_id, a.mnemonic_confirmed
           FROM accounts a
           JOIN vault_blobs vb ON vb.account_id = a.id
           WHERE a.vault_lookup_hash = $1""",
        lookup_hash,
    )
    return dict(row) if row else None


async def revoke_device(conn_or_pool, device_id: UUID, revoked_by: UUID) -> None:
    await conn_or_pool.execute(
        """UPDATE devices SET is_revoked = TRUE, revoked_at = now(), revoked_by = $2
           WHERE id = $1""",
        device_id, revoked_by,
    )


async def count_active_devices(conn_or_pool, account_id: UUID) -> int:
    row = await conn_or_pool.fetchrow(
        "SELECT COUNT(*) AS n FROM devices WHERE account_id = $1 AND is_revoked = FALSE",
        account_id,
    )
    return int(row["n"])


# ── Device invite helpers ─────────────────────────────────────────────────────

async def create_invite(conn_or_pool, token: str, account_id: UUID,
                        inviting_device: UUID, inviting_dh_pub: bytes) -> None:
    await conn_or_pool.execute(
        """INSERT INTO device_invites
               (token, account_id, inviting_device, inviting_dh_pub)
           VALUES ($1, $2, $3, $4)""",
        token, account_id, inviting_device, inviting_dh_pub,
    )


async def get_invite(conn_or_pool, token: str) -> dict | None:
    row = await conn_or_pool.fetchrow(
        "SELECT * FROM device_invites WHERE token = $1", token
    )
    return dict(row) if row else None


async def set_invite_accepted(conn_or_pool, token: str, joiner_dh_pub: bytes,
                               joiner_sign_pub: bytes, joiner_name: str) -> None:
    await conn_or_pool.execute(
        """UPDATE device_invites
           SET state = 'accepted', joiner_dh_pub = $2,
               joiner_sign_pub = $3, joiner_name = $4
           WHERE token = $1""",
        token, joiner_dh_pub, joiner_sign_pub, joiner_name,
    )


async def set_invite_delivered(conn_or_pool, token: str,
                                encrypted_vault_key: bytes) -> None:
    await conn_or_pool.execute(
        """UPDATE device_invites
           SET state = 'delivered', encrypted_vault_key = $2
           WHERE token = $1""",
        token, encrypted_vault_key,
    )


async def set_invite_consumed(conn_or_pool, token: str) -> None:
    await conn_or_pool.execute(
        "UPDATE device_invites SET state = 'consumed' WHERE token = $1", token
    )


async def get_devices_for_account(conn_or_pool, account_id: UUID):
    """Returns all devices (including revoked) for an account, ordered by creation date."""
    return await conn_or_pool.fetch(
        "SELECT * FROM devices WHERE account_id = $1 ORDER BY created_at",
        account_id,
    )
