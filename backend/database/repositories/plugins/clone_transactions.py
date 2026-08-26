"""SoAI - Plugin clone transaction operations [backend/database/repositories/plugins/clone_transactions.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3

from core.database.clone_requests import (
    CloneArtifactRecord,
    CloneTransactionRecord,
)
from core.errors.exceptions import StateError, ValidationError
from database.repositories.tasks.mutation_finalization import sync_finalize_mutation_for_task

__all__ = (
    "sync_get_clone_transaction",
    "sync_list_clone_artifacts",
    "sync_list_recoverable_clone_transactions",
    "sync_mark_clone_rollback_recovery_required",
    "sync_record_clone_artifact",
    "sync_transition_clone_artifact",
    "sync_transition_clone_transaction",
)

_PHASE_TRANSITIONS = frozenset(
    {
        ("admitted", "staging"),
        ("staging", "staged"),
        ("staged", "publishing"),
        ("publishing", "registering"),
        ("admitted", "rollback_pending"),
        ("staging", "rollback_pending"),
        ("staged", "rollback_pending"),
        ("publishing", "rollback_pending"),
        ("registering", "rollback_pending"),
        ("rollback_pending", "rolled_back"),
        ("recovery_required", "rollback_pending"),
    }
)
_ARTIFACT_TRANSITIONS = frozenset(
    {
        ("intended", "materialized"),
        ("materialized", "published"),
        ("intended", "removed"),
        ("materialized", "removed"),
        ("published", "removed"),
    }
)
_ARTIFACT_TYPES = frozenset(
    {
        "configuration",
        "database_record",
        "environment",
        "models",
        "package_cache",
        "plugin_package",
        "runtime",
    }
)


def sync_get_clone_transaction(
    connection: sqlite3.Connection,
    task_id: str,
) -> CloneTransactionRecord | None:
    row = connection.execute(
        """SELECT task_id, source_plugin_name, target_plugin_name, clone_models, phase, committed
        FROM plugin_clone_transactions WHERE task_id = ?""",
        (task_id,),
    ).fetchone()
    if row is None:
        return None
    return CloneTransactionRecord(
        task_id=row["task_id"],
        source_plugin_name=row["source_plugin_name"],
        target_plugin_name=row["target_plugin_name"],
        clone_models=bool(row["clone_models"]),
        phase=row["phase"],
        committed=bool(row["committed"]),
    )


def sync_list_clone_artifacts(
    connection: sqlite3.Connection,
    task_id: str,
) -> tuple[CloneArtifactRecord, ...]:
    rows = connection.execute(
        """SELECT artifact_id, artifact_type, staging_path, final_path, state
        FROM plugin_clone_artifacts WHERE task_id = ? ORDER BY artifact_id DESC""",
        (task_id,),
    ).fetchall()
    return tuple(
        CloneArtifactRecord(
            artifact_id=row["artifact_id"],
            artifact_type=row["artifact_type"],
            staging_path=row["staging_path"],
            final_path=row["final_path"],
            state=row["state"],
        )
        for row in rows
    )


def sync_list_recoverable_clone_transactions(
    connection: sqlite3.Connection,
) -> tuple[CloneTransactionRecord, ...]:
    rows = connection.execute("""SELECT task_id, source_plugin_name, target_plugin_name,
        clone_models, phase, committed
        FROM plugin_clone_transactions
        WHERE committed = 0 AND (
            phase NOT IN ('committed', 'rolled_back')
            OR (
                phase = 'rolled_back'
                AND EXISTS (
                    SELECT 1 FROM mutation_admissions
                    WHERE accepted_task_id = plugin_clone_transactions.task_id
                        AND lifecycle_status = 'recovery_required'
                )
            )
        )
        ORDER BY created_at_ms, task_id""").fetchall()
    return tuple(
        CloneTransactionRecord(
            task_id=row["task_id"],
            source_plugin_name=row["source_plugin_name"],
            target_plugin_name=row["target_plugin_name"],
            clone_models=bool(row["clone_models"]),
            phase=row["phase"],
            committed=bool(row["committed"]),
        )
        for row in rows
    )


def sync_record_clone_artifact(
    connection: sqlite3.Connection,
    task_id: str,
    artifact_type: str,
    staging_path: str,
    final_path: str,
) -> int:
    if artifact_type not in _ARTIFACT_TYPES:
        raise ValidationError("Unsupported clone artifact type.")
    if not staging_path or not final_path or staging_path == final_path:
        raise ValidationError("Clone artifact paths must be distinct and non-empty.")
    transaction = connection.execute(
        "SELECT phase FROM plugin_clone_transactions WHERE task_id = ?",
        (task_id,),
    ).fetchone()
    if transaction is None or transaction["phase"] not in {"admitted", "staging"}:
        raise StateError("Clone artifacts can only be recorded during staging.")
    cursor = connection.execute(
        """INSERT INTO plugin_clone_artifacts (
            task_id, artifact_type, staging_path, final_path
        ) VALUES (?, ?, ?, ?)""",
        (task_id, artifact_type, staging_path, final_path),
    )
    if cursor.lastrowid is None:
        raise StateError("Clone artifact journal did not return an identifier.")
    return cursor.lastrowid


def sync_transition_clone_artifact(
    connection: sqlite3.Connection,
    task_id: str,
    artifact_id: int,
    current_state: str,
    following_state: str,
) -> bool:
    if (current_state, following_state) not in _ARTIFACT_TRANSITIONS:
        return False
    transaction = connection.execute(
        "SELECT phase, committed FROM plugin_clone_transactions WHERE task_id = ?",
        (task_id,),
    ).fetchone()
    if transaction is None or transaction["committed"] == 1:
        return False
    if following_state == "removed" and transaction["phase"] != "rollback_pending":
        return False
    return (
        connection.execute(
            """UPDATE plugin_clone_artifacts SET state = ?
            WHERE artifact_id = ? AND task_id = ? AND state = ?""",
            (following_state, artifact_id, task_id, current_state),
        ).rowcount
        == 1
    )


def sync_mark_clone_rollback_recovery_required(
    connection: sqlite3.Connection,
    task_id: str,
    recovery_error: str,
) -> bool:
    if not recovery_error.strip():
        raise ValidationError("Clone rollback recovery diagnostic is required.")
    return (
        connection.execute(
            """UPDATE plugin_clone_transactions
            SET phase = 'recovery_required', recovery_error = ?
            WHERE task_id = ? AND phase = 'rollback_pending' AND committed = 0""",
            (recovery_error, task_id),
        ).rowcount
        == 1
    )


def sync_transition_clone_transaction(
    connection: sqlite3.Connection,
    task_id: str,
    current_phase: str,
    following_phase: str,
) -> bool:
    if (current_phase, following_phase) not in _PHASE_TRANSITIONS:
        return False
    if following_phase == "rolled_back":
        remaining = connection.execute(
            "SELECT COUNT(*) FROM plugin_clone_artifacts WHERE task_id = ? AND state != 'removed'",
            (task_id,),
        ).fetchone()[0]
        if remaining:
            raise StateError("Clone rollback cannot complete while owned artifacts remain.")
    updated = connection.execute(
        """UPDATE plugin_clone_transactions SET phase = ?, committed = 0
        WHERE task_id = ? AND phase = ? AND committed = 0""",
        (following_phase, task_id, current_phase),
    ).rowcount
    if updated != 1:
        return False
    if current_phase == "recovery_required" and following_phase == "rollback_pending":
        connection.execute(
            "UPDATE plugin_clone_transactions SET recovery_error = NULL WHERE task_id = ?",
            (task_id,),
        )
    if following_phase == "rolled_back":
        connection.execute(
            "DELETE FROM plugin_clone_artifacts WHERE task_id = ?",
            (task_id,),
        )
        connection.execute(
            "UPDATE plugin_clone_transactions SET recovery_error = NULL WHERE task_id = ?",
            (task_id,),
        )
        connection.execute(
            """UPDATE mutation_admissions
            SET lifecycle_status = 'recovery_required', claim_owner = NULL,
                lease_expires_at_ms = NULL
            WHERE accepted_task_id = ? AND lifecycle_status IN ('accepted', 'running')""",
            (task_id,),
        )
        terminal_task = connection.execute(
            """SELECT status, result, completed_at_ms FROM unified_tasks
            WHERE task_id = ? AND status IN ('completed', 'failed', 'cancelled')""",
            (task_id,),
        ).fetchone()
        if terminal_task is not None:
            sync_finalize_mutation_for_task(
                connection,
                task_id,
                terminal_task["status"],
                terminal_task["result"],
                completed_at_ms=terminal_task["completed_at_ms"],
            )
    return True
