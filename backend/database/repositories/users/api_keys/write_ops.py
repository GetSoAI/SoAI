"""SoAI - OpenAI API key repository write operations [backend/database/repositories/users/api_keys/write_ops.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
from collections.abc import Callable
from typing import TYPE_CHECKING

from core.database.requests import InsertAPIKeyRequest
from core.errors.exceptions import StateError
from core.serialization.json import serialize_json_compact_stable_strict
from core.timing.epoch import epoch_ms
from database.core.flags import OPENAI_API_KEY_LIMIT
from database.core.query_execution import sync_fetch_one_as_dict
from database.core.sqlite_numbers import coerce_required_int_from_sqlite_row
from database.repositories.users.api_key_row_normalization import normalize_api_key_row

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "sync_delete_all_keys",
    "sync_delete_key",
    "sync_get_key_by_id",
    "sync_insert_key",
    "sync_record_rate_limited",
    "sync_record_usage",
    "sync_revoke_key",
)


def sync_get_key_by_id(
    conn: sqlite3.Connection,
    key_id: str,
    *,
    now_ts: int,
    decrypt_hash: Callable[[str | None], str | None],
) -> JSONDict | None:
    cursor = conn.execute("SELECT * FROM openai_api_keys WHERE key_id = ?", (key_id,))
    row = sync_fetch_one_as_dict(cursor)
    return normalize_api_key_row(row, now_ts=int(now_ts), decrypt_hash=decrypt_hash)


def sync_insert_key(
    conn: sqlite3.Connection,
    request: InsertAPIKeyRequest,
    now_ms: int,
    encrypt_hash: Callable[[str], str],
    decrypt_hash: Callable[[str | None], str | None],
) -> tuple[JSONDict, int]:
    created_at_ms = epoch_ms() if request.created_at_ms is None else int(request.created_at_ms)
    count_row = sync_fetch_one_as_dict(
        conn.execute("SELECT COUNT(*) AS count FROM openai_api_keys"),
    )
    count = coerce_required_int_from_sqlite_row(count_row, "count") if count_row else 0
    if count >= OPENAI_API_KEY_LIMIT:
        raise StateError(f"OpenAI API key limit reached ({OPENAI_API_KEY_LIMIT}).")
    conn.execute(
        """
        INSERT INTO openai_api_keys (key_id, hashed_key_ciphertext, salt, fingerprint, label, prefix, scopes, created_at_ms, created_by, expires_at_ms, rotation_reminder_at_ms, revoked, encryption_version)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?)
        """,
        (
            request.key_id,
            encrypt_hash(request.hashed_key),
            request.salt,
            request.fingerprint,
            request.label,
            request.prefix,
            serialize_json_compact_stable_strict(list(request.scopes)),
            created_at_ms,
            request.created_by,
            request.expires_at_ms,
            request.rotation_reminder_at_ms,
            request.encryption_version,
        ),
    )
    result = sync_get_key_by_id(conn, request.key_id, now_ts=int(now_ms), decrypt_hash=decrypt_hash)
    if result is None:
        raise StateError("Key not found after INSERT")
    return (result, _count_configured_keys(conn))


def sync_record_usage(
    conn: sqlite3.Connection,
    key_id: str,
    timestamp_ms: int,
    client_ip: str | None,
) -> None:
    conn.execute(
        """
        UPDATE openai_api_keys
        SET last_used_at_ms = ?, last_used_ip = ?, request_count = COALESCE(request_count, 0) + 1
        WHERE key_id = ?
        """,
        (int(timestamp_ms), client_ip, key_id),
    )


def sync_record_rate_limited(conn: sqlite3.Connection, key_id: str) -> None:
    conn.execute(
        """
        UPDATE openai_api_keys
        SET rate_limited_count = COALESCE(rate_limited_count, 0) + 1
        WHERE key_id = ?
        """,
        (key_id,),
    )


def sync_revoke_key(
    conn: sqlite3.Connection,
    key_id: str,
    revoked_by: int | None,
    now_ms: int,
    decrypt_hash: Callable[[str | None], str | None],
) -> JSONDict | None:
    updated = conn.execute(
        """
        UPDATE openai_api_keys
        SET revoked = 1, revoked_at_ms = ?, revoked_by = ?
        WHERE key_id = ?
        """,
        (epoch_ms(), revoked_by, key_id),
    ).rowcount
    if not updated:
        return None
    return sync_get_key_by_id(conn, key_id, now_ts=int(now_ms), decrypt_hash=decrypt_hash)


def sync_delete_key(conn: sqlite3.Connection, key_id: str) -> tuple[int, int]:
    deleted = int(conn.execute("DELETE FROM openai_api_keys WHERE key_id = ?", (key_id,)).rowcount)
    return (deleted, _count_configured_keys(conn))


def sync_delete_all_keys(conn: sqlite3.Connection) -> tuple[int, int]:
    count_value = _count_configured_keys(conn)
    conn.execute("DELETE FROM openai_api_keys")
    return (count_value, _count_configured_keys(conn))


def _count_configured_keys(conn: sqlite3.Connection) -> int:
    cursor = conn.execute("SELECT COUNT(*) AS count FROM openai_api_keys")
    row = sync_fetch_one_as_dict(cursor)
    return coerce_required_int_from_sqlite_row(row, "count") if row else 0
