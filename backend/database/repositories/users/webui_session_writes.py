"""SoAI - Transactional WebUI session writes [backend/database/repositories/users/webui_session_writes.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3

__all__ = (
    "sync_revoke_session_rows",
    "sync_revoke_active_user_sessions",
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
