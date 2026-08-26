"""SoAI - Writer-owned WebUI identity lineage validation and retention [backend/database/repositories/users/webui_identity_maintenance.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3

from core.errors.exceptions import StateError
from core.timing.epoch import epoch_ms
from core.users.identity_mutation_contract import SESSION_LINEAGE_PRUNE_GRACE_MS
from database.repositories.users.identity_mutation_record_storage import (
    calculate_identity_mutation_retention,
    identity_mutation_record_from_row,
    sync_prune_expired_identity_mutations,
)
from database.repositories.users.webui_session_lineage_validation import (
    sync_validate_rotation_lineages,
)


def _validate_mutation_rows(conn: sqlite3.Connection) -> None:
    rows = conn.execute("SELECT * FROM webui_user_mutations").fetchall()
    for row in rows:
        record = identity_mutation_record_from_row(dict(row))
        rotation = conn.execute(
            """
            SELECT max(source_expires_at_ms, replacement_expires_at_ms,
                       recoverable_until_ms) + ? AS cleanup_at_ms
            FROM webui_session_rotations
            WHERE user_id = ? AND operation_id = ?
            """,
            (
                SESSION_LINEAGE_PRUNE_GRACE_MS,
                record.binding.actor_user_id,
                record.binding.operation_id,
            ),
        ).fetchone()
        cleanup_value = rotation["cleanup_at_ms"] if rotation is not None else None
        cleanup_at_ms = int(cleanup_value) if cleanup_value is not None else None
        minimum_retention = calculate_identity_mutation_retention(
            record.binding,
            record.completed_at_ms,
            cleanup_at_ms,
        )
        if record.retain_until_ms < minimum_retention:
            raise StateError("WebUI identity mutation retention is invalid.")


def sync_maintain_webui_identity_state(conn: sqlite3.Connection) -> None:
    observed_at_ms = epoch_ms()
    sync_validate_rotation_lineages(conn, observed_at_ms)
    _validate_mutation_rows(conn)
    sync_prune_expired_identity_mutations(conn, observed_at_ms)
    sync_prune_expired_session_lineage_state(conn, observed_at_ms)


def sync_prune_expired_session_lineage_state(
    conn: sqlite3.Connection,
    observed_at_ms: int,
) -> None:
    conn.execute(
        """
        DELETE FROM webui_device_sessions
        WHERE expires_at_ms <= ?
          AND NOT EXISTS (
              SELECT 1 FROM webui_session_rotations rotation
              WHERE (rotation.source_jti = webui_device_sessions.jti
                     OR rotation.replacement_jti = webui_device_sessions.jti)
                AND max(rotation.source_expires_at_ms,
                        rotation.replacement_expires_at_ms,
                        rotation.recoverable_until_ms) + ? >= ?
          )
        """,
        (observed_at_ms, SESSION_LINEAGE_PRUNE_GRACE_MS, observed_at_ms),
    )
    conn.execute(
        """
        DELETE FROM webui_session_rotations
        WHERE source_expires_at_ms + ? < ?
          AND replacement_expires_at_ms + ? < ?
          AND recoverable_until_ms + ? < ?
        """,
        (
            SESSION_LINEAGE_PRUNE_GRACE_MS,
            observed_at_ms,
            SESSION_LINEAGE_PRUNE_GRACE_MS,
            observed_at_ms,
            SESSION_LINEAGE_PRUNE_GRACE_MS,
            observed_at_ms,
        ),
    )


__all__ = (
    "sync_maintain_webui_identity_state",
    "sync_prune_expired_session_lineage_state",
)
