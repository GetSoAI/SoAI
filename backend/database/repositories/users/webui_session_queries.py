"""SoAI - Read queries for WebUI device sessions and rotation state [backend/database/repositories/users/webui_session_queries.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import aiosqlite

from core.auth.protocols_database_tokens import TokenAuthReadState
from core.auth.webui_sessions import (
    WebuiSessionDescriptor,
    require_webui_session_client_type,
)
from core.types.json import JSONDict
from database.core.query_execution import query_one_to_dict, query_to_dicts
from database.core.sqlite_numbers import (
    coerce_non_negative_int_from_sqlite,
    coerce_required_int_from_sqlite_row,
)
from database.repositories.row_formatting import format_row
from database.repositories.users.user_row_normalization import normalize_user_row


async def query_active_admin_session_device_count(
    database: aiosqlite.Connection,
    observed_at_ms: int,
) -> int:
    rows = await query_to_dicts(
        database,
        """
        SELECT COUNT(DISTINCT CASE
            WHEN sessions.device_id IS NOT NULL THEN 'android:' || sessions.device_id
            ELSE 'web:' || sessions.jti END) AS count
        FROM webui_device_sessions AS sessions
        JOIN webui_users AS users ON users.id = sessions.user_id
        WHERE users.account_type = 'human' AND users.is_admin = 1
          AND sessions.revoked_at_ms IS NULL AND sessions.expires_at_ms > ?
          AND sessions.password_revision = users.password_revision
        """,
        (observed_at_ms,),
    )
    return coerce_non_negative_int_from_sqlite(rows[0].get("count")) if rows else 0


async def query_session_jti_exists(database: aiosqlite.Connection, jti: str) -> bool:
    row = await query_one_to_dict(
        database,
        "SELECT 1 AS found FROM webui_device_sessions WHERE jti = ?",
        (jti,),
    )
    return row is not None


async def query_token_auth_state(
    database: aiosqlite.Connection,
    *,
    jti: str | None,
    user_id: int | None,
    username: str | None,
    observed_at_ms: int,
) -> TokenAuthReadState:
    if not jti or user_id is None or not username:
        return TokenAuthReadState(status="session_revoked", user=None)
    user_row = await query_one_to_dict(
        database,
        """
        SELECT webui_users.*
        FROM webui_device_sessions
        JOIN webui_users ON webui_users.id = webui_device_sessions.user_id
        WHERE webui_device_sessions.jti = ? AND webui_users.id = ?
          AND webui_users.username = ? AND webui_users.account_type = 'human'
          AND webui_device_sessions.revoked_at_ms IS NULL
          AND webui_device_sessions.expires_at_ms > ?
          AND webui_device_sessions.password_revision = webui_users.password_revision
        """,
        (jti, user_id, username, observed_at_ms),
    )
    user = normalize_user_row(user_row)
    if user is not None:
        return TokenAuthReadState(status="active", user=user)
    rotation_row = await query_one_to_dict(
        database,
        """
        SELECT users.*, rotations.replacement_jti,
               rotations.replacement_issued_at_ms,
               rotations.replacement_expires_at_ms,
               rotations.replacement_password_revision,
               rotations.recoverable_until_ms, rotations.operation_id
        FROM webui_session_rotations rotations
        JOIN webui_users users ON users.id = rotations.user_id
        JOIN webui_device_sessions source
          ON source.jti = rotations.source_jti
         AND source.user_id = rotations.user_id
        JOIN webui_device_sessions replacement
          ON replacement.jti = rotations.replacement_jti
         AND replacement.user_id = rotations.user_id
        WHERE rotations.source_jti = ? AND rotations.user_id = ?
          AND users.account_type = 'human'
          AND rotations.recoverable_until_ms >= ?
          AND source.revoked_at_ms IS NOT NULL
          AND source.password_revision = rotations.source_password_revision
          AND source.expires_at_ms = rotations.source_expires_at_ms
          AND replacement.revoked_at_ms IS NULL AND replacement.expires_at_ms > ?
          AND replacement.created_at_ms = rotations.replacement_issued_at_ms
          AND replacement.expires_at_ms = rotations.replacement_expires_at_ms
          AND replacement.password_revision = rotations.replacement_password_revision
          AND replacement.password_revision = users.password_revision
          AND NOT EXISTS (
              SELECT 1 FROM webui_session_rotations next_rotation
              WHERE next_rotation.source_jti = rotations.replacement_jti
          )
        """,
        (jti, user_id, observed_at_ms, observed_at_ms),
    )
    rotation_user = normalize_user_row(rotation_row)
    if rotation_row is None or rotation_user is None:
        return TokenAuthReadState(status="session_revoked", user=None)
    return TokenAuthReadState(
        status="session_rotated",
        user=rotation_user,
        replacement_jti=str(rotation_row["replacement_jti"]),
        replacement_issued_at_ms=coerce_required_int_from_sqlite_row(
            rotation_row, "replacement_issued_at_ms"
        ),
        replacement_expires_at_ms=coerce_required_int_from_sqlite_row(
            rotation_row, "replacement_expires_at_ms"
        ),
        replacement_password_revision=coerce_required_int_from_sqlite_row(
            rotation_row, "replacement_password_revision"
        ),
        recoverable_until_ms=coerce_required_int_from_sqlite_row(
            rotation_row, "recoverable_until_ms"
        ),
        operation_id=str(rotation_row["operation_id"]),
    )


async def query_active_sessions(
    database: aiosqlite.Connection,
    user_id: int,
    current_jti: str,
    observed_at_ms: int,
) -> list[JSONDict]:
    rows = await query_to_dicts(
        database,
        """
        SELECT jti, device_id, device_label, client_type, user_agent,
               created_at_ms, last_seen_at_ms, expires_at_ms
        FROM webui_device_sessions
        WHERE user_id = ? AND revoked_at_ms IS NULL AND expires_at_ms > ?
        ORDER BY last_seen_at_ms DESC, created_at_ms DESC, jti DESC
        """,
        (user_id, observed_at_ms),
    )
    sessions: list[JSONDict] = []
    for row in rows:
        session = format_row(row)
        if session is not None:
            session["current"] = session.get("jti") == current_jti
            sessions.append(session)
    return sessions


async def query_active_session_descriptor(
    database: aiosqlite.Connection,
    user_id: int,
    jti: str,
    observed_at_ms: int,
) -> WebuiSessionDescriptor | None:
    row = await query_one_to_dict(
        database,
        """
        SELECT device_id, device_label, client_type, user_agent
        FROM webui_device_sessions
        WHERE user_id = ? AND jti = ? AND revoked_at_ms IS NULL AND expires_at_ms > ?
        """,
        (user_id, jti, observed_at_ms),
    )
    if row is None:
        return None
    client_type_value = row.get("client_type")
    if client_type_value not in ("web", "android"):
        return None
    client_type = require_webui_session_client_type(client_type_value)
    device_id = row.get("device_id")
    device_label = row.get("device_label")
    user_agent = row.get("user_agent")
    if (
        (device_id is not None and not isinstance(device_id, str))
        or not isinstance(device_label, str)
        or not isinstance(user_agent, str)
    ):
        return None
    return WebuiSessionDescriptor(
        client_type=client_type,
        device_id=device_id,
        device_label=device_label,
        user_agent=user_agent,
    )


__all__ = (
    "query_active_admin_session_device_count",
    "query_active_session_descriptor",
    "query_active_sessions",
    "query_token_auth_state",
)
