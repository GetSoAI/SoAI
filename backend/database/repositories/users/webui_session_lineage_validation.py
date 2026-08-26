"""SoAI - Validated traversal of WebUI session rotation lineage [backend/database/repositories/users/webui_session_lineage_validation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3

from core.errors.exceptions import StateError


def _require_session_edge_consistency(
    conn: sqlite3.Connection,
    row: sqlite3.Row,
    user_id: int,
) -> None:
    source_password_revision = int(row["source_password_revision"])
    source_expires_at_ms = int(row["source_expires_at_ms"])
    replacement_password_revision = int(row["replacement_password_revision"])
    replacement_issued_at_ms = int(row["replacement_issued_at_ms"])
    replacement_expires_at_ms = int(row["replacement_expires_at_ms"])
    source_jti = str(row["source_jti"])
    replacement_jti = str(row["replacement_jti"])
    operation_type = str(row["operation_type"])
    if operation_type not in ("password_change", "username_rename"):
        raise StateError("WebUI session lineage operation type is invalid.")
    expected_replacement_revision = (
        source_password_revision + 1
        if operation_type == "password_change"
        else source_password_revision
    )
    if (
        replacement_jti == source_jti
        or replacement_password_revision != expected_replacement_revision
        or replacement_issued_at_ms > int(row["rotated_at_ms"])
    ):
        raise StateError("WebUI session lineage edge is invalid.")
    source_session = conn.execute(
        """
        SELECT user_id, password_revision, expires_at_ms
        FROM webui_device_sessions WHERE jti = ?
        """,
        (source_jti,),
    ).fetchone()
    if source_session is not None and (
        int(source_session["user_id"]) != user_id
        or int(source_session["password_revision"]) != source_password_revision
        or int(source_session["expires_at_ms"]) != source_expires_at_ms
    ):
        raise StateError("WebUI session lineage source state is inconsistent.")
    replacement_session = conn.execute(
        """
        SELECT user_id, password_revision, created_at_ms, expires_at_ms
        FROM webui_device_sessions WHERE jti = ?
        """,
        (replacement_jti,),
    ).fetchone()
    if replacement_session is not None and (
        int(replacement_session["user_id"]) != user_id
        or int(replacement_session["password_revision"]) != replacement_password_revision
        or int(replacement_session["created_at_ms"]) != replacement_issued_at_ms
        or int(replacement_session["expires_at_ms"]) != replacement_expires_at_ms
    ):
        raise StateError("WebUI session lineage replacement state is inconsistent.")


def sync_resolve_terminal_session_jti(
    conn: sqlite3.Connection,
    user_id: int,
    source_jti: str,
) -> str:
    current_jti = source_jti
    previous_rotated_at_ms = -1
    expected_source_password_revision: int | None = None
    expected_source_expires_at_ms: int | None = None
    visited: set[str] = set()
    edges: list[sqlite3.Row] = []
    while True:
        if current_jti in visited:
            raise StateError("WebUI session lineage contains a cycle.")
        visited.add(current_jti)
        rows = conn.execute(
            "SELECT * FROM webui_session_rotations WHERE source_jti = ?",
            (current_jti,),
        ).fetchall()
        if not rows:
            for edge in edges:
                _require_session_edge_consistency(conn, edge, user_id)
            return current_jti
        if len(rows) != 1:
            raise StateError("WebUI session lineage contains fan-out.")
        row = rows[0]
        if int(row["user_id"]) != user_id:
            raise StateError("WebUI session lineage changes account ownership.")
        predecessor_count = int(
            conn.execute(
                "SELECT count(*) FROM webui_session_rotations WHERE replacement_jti = ?",
                (current_jti,),
            ).fetchone()[0]
        )
        if predecessor_count > 1:
            raise StateError("WebUI session lineage contains fan-in.")
        rotated_at_ms = int(row["rotated_at_ms"])
        if rotated_at_ms <= previous_rotated_at_ms:
            raise StateError("WebUI session lineage chronology is invalid.")
        source_password_revision = int(row["source_password_revision"])
        source_expires_at_ms = int(row["source_expires_at_ms"])
        if expected_source_password_revision is not None and (
            source_password_revision != expected_source_password_revision
            or source_expires_at_ms != expected_source_expires_at_ms
        ):
            raise StateError("WebUI session lineage continuity is invalid.")
        edges.append(row)
        previous_rotated_at_ms = rotated_at_ms
        expected_source_password_revision = int(row["replacement_password_revision"])
        expected_source_expires_at_ms = int(row["replacement_expires_at_ms"])
        current_jti = str(row["replacement_jti"])


def sync_validate_rotation_lineages(
    conn: sqlite3.Connection,
    observed_at_ms: int,
) -> None:
    rows = conn.execute(
        "SELECT * FROM webui_session_rotations ORDER BY rotated_at_ms, source_jti"
    ).fetchall()
    for row in rows:
        user_id = int(row["user_id"])
        sync_resolve_terminal_session_jti(conn, user_id, str(row["source_jti"]))
        source_exists = conn.execute(
            "SELECT 1 FROM webui_device_sessions WHERE jti = ?",
            (str(row["source_jti"]),),
        ).fetchone()
        replacement_exists = conn.execute(
            "SELECT 1 FROM webui_device_sessions WHERE jti = ?",
            (str(row["replacement_jti"]),),
        ).fetchone()
        if int(row["source_expires_at_ms"]) > observed_at_ms and source_exists is None:
            raise StateError("Active WebUI rotation source session is missing.")
        if int(row["replacement_expires_at_ms"]) > observed_at_ms and replacement_exists is None:
            raise StateError("Active WebUI rotation replacement session is missing.")


__all__ = (
    "sync_resolve_terminal_session_jti",
    "sync_validate_rotation_lineages",
)
