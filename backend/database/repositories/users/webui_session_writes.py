"""SoAI - Transactional WebUI session writes [backend/database/repositories/users/webui_session_writes.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3

from core.auth.webui_sessions import (
    WebuiSessionDescriptor,
    WebuiSessionReplacement,
)
from core.errors.exceptions import StateError

__all__ = (
    "sync_replace_user_webui_sessions",
    "sync_revoke_session_rows",
    "sync_revoke_active_user_sessions",
    "sync_webui_session_is_active",
)


def _sync_get_active_webui_session_descriptor(
    conn: sqlite3.Connection,
    *,
    user_id: int,
    jti: str,
    observed_at_ms: int,
) -> WebuiSessionDescriptor | None:
    row = conn.execute(
        """
        SELECT device_id, device_label, client_type, user_agent
        FROM webui_device_sessions
        WHERE user_id = ? AND jti = ? AND revoked_at_ms IS NULL AND expires_at_ms > ?
        """,
        (user_id, jti, observed_at_ms),
    ).fetchone()
    if row is None:
        return None
    client_type = row["client_type"]
    device_id = row["device_id"]
    device_label = row["device_label"]
    user_agent = row["user_agent"]
    if client_type not in {"web", "android"}:
        raise StateError("WebUI session has invalid client type.")
    if device_id is not None and not isinstance(device_id, str):
        raise StateError("WebUI session has invalid device id.")
    if not isinstance(device_label, str) or not isinstance(user_agent, str):
        raise StateError("WebUI session has invalid metadata.")
    return WebuiSessionDescriptor(
        client_type=client_type,
        device_id=device_id,
        device_label=device_label,
        user_agent=user_agent,
    )


def sync_webui_session_is_active(
    conn: sqlite3.Connection,
    *,
    user_id: int,
    jti: str,
    observed_at_ms: int,
) -> bool:
    return (
        _sync_get_active_webui_session_descriptor(
            conn,
            user_id=user_id,
            jti=jti,
            observed_at_ms=observed_at_ms,
        )
        is not None
    )


def sync_revoke_session_rows(
    conn: sqlite3.Connection,
    rows: tuple[sqlite3.Row, ...],
    revoked_at_ms: int,
) -> tuple[str, ...]:
    revoked_jtis: list[str] = []
    for row in rows:
        jti = str(row["jti"])
        row_revoked_at_ms = max(revoked_at_ms, int(row["created_at_ms"]))
        updated = conn.execute(
            """
            UPDATE webui_device_sessions
            SET revoked_at_ms = ?
            WHERE jti = ? AND revoked_at_ms IS NULL
            """,
            (row_revoked_at_ms, jti),
        ).rowcount
        if updated == 1:
            revoked_jtis.append(jti)
    return tuple(revoked_jtis)


def sync_revoke_active_user_sessions(
    conn: sqlite3.Connection,
    *,
    user_id: int,
    revoked_at_ms: int,
) -> tuple[str, ...]:
    rows = tuple(
        conn.execute(
            """
            SELECT jti, created_at_ms
            FROM webui_device_sessions
            WHERE user_id = ? AND revoked_at_ms IS NULL
            ORDER BY jti
            """,
            (user_id,),
        ).fetchall()
    )
    return sync_revoke_session_rows(conn, rows, revoked_at_ms)


def sync_replace_user_webui_sessions(
    conn: sqlite3.Connection,
    *,
    user_id: int,
    password_revision: int,
    revoked_at_ms: int,
    replacement: WebuiSessionReplacement | None,
) -> tuple[str, ...]:
    replacement_descriptor: WebuiSessionDescriptor | None = None
    if replacement is not None:
        replacement_descriptor = _sync_get_active_webui_session_descriptor(
            conn,
            user_id=user_id,
            jti=replacement.source_jti,
            observed_at_ms=revoked_at_ms,
        )
        if replacement_descriptor is None:
            raise StateError("Password replacement requires an active source session.")
    revoked_jtis = sync_revoke_active_user_sessions(
        conn,
        user_id=user_id,
        revoked_at_ms=revoked_at_ms,
    )
    if replacement is not None:
        if replacement_descriptor is None:
            raise StateError("Password replacement source session was not resolved.")
        conn.execute(
            """
            INSERT INTO webui_device_sessions (
                jti, user_id, device_id, device_label, client_type, user_agent,
                password_revision, created_at_ms, last_seen_at_ms, expires_at_ms, revoked_at_ms
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL)
            """,
            (
                replacement.jti,
                user_id,
                replacement_descriptor.device_id,
                replacement_descriptor.device_label,
                replacement_descriptor.client_type,
                replacement_descriptor.user_agent,
                password_revision,
                replacement.issued_at_ms,
                replacement.issued_at_ms,
                replacement.expires_at_ms,
            ),
        )
    return revoked_jtis
