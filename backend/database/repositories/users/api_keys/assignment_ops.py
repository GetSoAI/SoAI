"""SoAI - OpenAI API key user assignment operations [backend/database/repositories/users/api_keys/assignment_ops.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3

import aiosqlite

from core.auth.api_key_assignment import APIKeyAssignmentOutcome
from core.database.protocols import DatabaseCoreProtocol
from core.errors.exceptions import StateError
from core.timing.epoch import epoch_ms
from database.core.query_execution import query_to_dicts

__all__ = (
    "get_active_key_id_for_user",
    "sync_assign_user_to_key",
    "sync_revoke_assigned_keys_for_user",
    "sync_unassign_user_from_key",
)


async def get_active_key_id_for_user(
    core: DatabaseCoreProtocol,
    user_id: int,
    now_ms: int,
) -> str | None:
    async def _query(database: aiosqlite.Connection) -> str | None:
        rows = await query_to_dicts(
            database,
            """
            SELECT key_id FROM openai_api_keys
            WHERE assigned_user_id = ?
              AND revoked = 0
              AND (expires_at_ms IS NULL OR expires_at_ms > ?)
            LIMIT 1
            """,
            (int(user_id), int(now_ms)),
        )
        if not rows:
            return None
        key_id_value = rows[0].get("key_id")
        return str(key_id_value) if key_id_value is not None else None

    return await core.reader.execute_read(_query)


def sync_assign_user_to_key(
    conn: sqlite3.Connection,
    key_id: str,
    user_id: int,
) -> APIKeyAssignmentOutcome:
    key_row = conn.execute(
        "SELECT revoked, expires_at_ms FROM openai_api_keys WHERE key_id = ?",
        (key_id,),
    ).fetchone()
    if key_row is None:
        return APIKeyAssignmentOutcome.API_KEY_NOT_FOUND
    now_ms = epoch_ms()
    revoked = bool(key_row[0])
    expires_at_value = key_row[1]
    expires_at_ms = int(expires_at_value) if expires_at_value is not None else None
    if revoked or (expires_at_ms is not None and expires_at_ms <= now_ms):
        return APIKeyAssignmentOutcome.API_KEY_INACTIVE
    user_exists = conn.execute(
        "SELECT 1 FROM webui_users WHERE id = ? AND account_type = 'human'",
        (int(user_id),),
    ).fetchone()
    if user_exists is None:
        return APIKeyAssignmentOutcome.USER_NOT_FOUND
    conn.execute(
        """
        UPDATE openai_api_keys SET assigned_user_id = NULL
        WHERE assigned_user_id = ? AND key_id != ?
        """,
        (int(user_id), key_id),
    )
    updated = conn.execute(
        """
        UPDATE openai_api_keys SET assigned_user_id = ?
        WHERE key_id = ?
          AND revoked = 0
          AND (expires_at_ms IS NULL OR expires_at_ms > ?)
          AND EXISTS (
              SELECT 1 FROM webui_users
              WHERE id = ? AND account_type = 'human'
          )
        """,
        (int(user_id), key_id, now_ms, int(user_id)),
    ).rowcount
    if updated != 1:
        raise StateError("API key assignment preconditions changed during the transaction.")
    return APIKeyAssignmentOutcome.ASSIGNED


def sync_revoke_assigned_keys_for_user(
    conn: sqlite3.Connection,
    user_id: int,
    revoked_at_ms: int,
) -> int:
    updated = conn.execute(
        """
        UPDATE openai_api_keys
        SET assigned_user_id = NULL,
            revoked = 1,
            revoked_at_ms = CASE WHEN revoked = 0 THEN ? ELSE revoked_at_ms END,
            revoked_by = CASE WHEN revoked = 0 THEN NULL ELSE revoked_by END
        WHERE assigned_user_id = ?
        """,
        (int(revoked_at_ms), int(user_id)),
    ).rowcount
    return int(updated)


def sync_unassign_user_from_key(
    conn: sqlite3.Connection,
    key_id: str,
) -> bool:
    updated = conn.execute(
        "UPDATE openai_api_keys SET assigned_user_id = NULL WHERE key_id = ?",
        (key_id,),
    ).rowcount
    return bool(updated)
