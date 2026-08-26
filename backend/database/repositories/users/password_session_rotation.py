"""SoAI - Transactional self-password session rotation insertion [backend/database/repositories/users/password_session_rotation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3

from core.errors.exceptions import StateError
from core.users.identity_mutation_contract import SESSION_LINEAGE_PRUNE_GRACE_MS
from core.users.password_change import PasswordChangeTransaction


def sync_insert_password_session_successor(
    conn: sqlite3.Connection,
    transaction: PasswordChangeTransaction,
    source_row: sqlite3.Row,
    observed_at_ms: int,
) -> int:
    successor = transaction.successor
    descriptor = transaction.source_descriptor
    if successor is None or descriptor is None:
        raise StateError("Self password change session preparation is incomplete.")
    new_revision = transaction.target.password_revision + 1
    conn.execute(
        """
        INSERT INTO webui_device_sessions (
            jti, user_id, device_id, device_label, client_type, user_agent,
            password_revision, created_at_ms, last_seen_at_ms, expires_at_ms
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            successor.jti,
            transaction.actor.user_id,
            descriptor.device_id,
            descriptor.device_label,
            descriptor.client_type,
            descriptor.user_agent,
            new_revision,
            successor.issued_at_ms,
            successor.issued_at_ms,
            successor.expires_at_ms,
        ),
    )
    conn.execute(
        """
        INSERT INTO webui_session_rotations (
            source_jti, replacement_jti, operation_id, operation_type, user_id,
            source_password_revision, source_expires_at_ms,
            replacement_password_revision, replacement_issued_at_ms,
            replacement_expires_at_ms, rotated_at_ms, recoverable_until_ms
        ) VALUES (?, ?, ?, 'password_change', ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            transaction.source_jti,
            successor.jti,
            transaction.binding.operation_id,
            transaction.actor.user_id,
            transaction.actor.password_revision,
            int(source_row["expires_at_ms"]),
            new_revision,
            successor.issued_at_ms,
            successor.expires_at_ms,
            observed_at_ms,
            transaction.recovery_horizon_at_ms,
        ),
    )
    return (
        max(
            int(source_row["expires_at_ms"]),
            successor.expires_at_ms,
            transaction.recovery_horizon_at_ms,
        )
        + SESSION_LINEAGE_PRUNE_GRACE_MS
    )


__all__ = ("sync_insert_password_session_successor",)
