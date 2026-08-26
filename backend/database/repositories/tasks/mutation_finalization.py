"""SoAI - Durable mutation terminalization [backend/database/repositories/tasks/mutation_finalization.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3

from core.errors.exceptions import ValidationError
from core.serialization.json_parsing import parse_json_value
from core.tasks.status_policy import TERMINAL_TASK_STATUS_VALUES
from core.validation.strict_numbers import require_non_negative_int_strict
from core.validation.strings import require_canonical_trimmed_json_text

__all__ = ("sync_finalize_mutation_for_task",)


def _clone_retains_recovery_ownership(
    connection: sqlite3.Connection,
    task_id: str,
) -> bool:
    row = connection.execute(
        "SELECT phase, committed FROM plugin_clone_transactions WHERE task_id = ?",
        (task_id,),
    ).fetchone()
    return row is not None and not bool(row["committed"]) and row["phase"] != "rolled_back"


def _release_mutation_ownership(
    connection: sqlite3.Connection,
    request_id: str,
    task_id: str,
) -> None:
    connection.execute(
        "DELETE FROM mutation_conflict_keys WHERE request_id = ?",
        (request_id,),
    )
    connection.execute(
        "DELETE FROM plugin_clone_target_reservations WHERE task_id = ?",
        (task_id,),
    )


def sync_finalize_mutation_for_task(
    connection: sqlite3.Connection,
    task_id: str,
    terminal_status: str,
    terminal_result: str | None,
    *,
    completed_at_ms: int,
) -> bool:
    require_canonical_trimmed_json_text(
        task_id,
        error_message="Mutation lifecycle requires a valid task identity.",
    )
    require_non_negative_int_strict(
        completed_at_ms,
        error_message="Mutation lifecycle requires a valid completion time.",
    )
    if not isinstance(terminal_status, str) or terminal_status not in TERMINAL_TASK_STATUS_VALUES:
        raise ValidationError("Mutation task finalization requires a terminal status.")
    if terminal_result is not None:
        parse_json_value(terminal_result, field="terminal_result")
    admission = connection.execute(
        """SELECT request_id FROM mutation_admissions
        WHERE accepted_task_id = ?
            AND lifecycle_status IN ('accepted', 'running', 'recovery_required')""",
        (task_id,),
    ).fetchone()
    if admission is None:
        return False
    recovery_required = _clone_retains_recovery_ownership(connection, task_id)
    lifecycle_status = "recovery_required" if recovery_required else terminal_status
    row = connection.execute(
        """UPDATE mutation_admissions
        SET lifecycle_status = ?, terminal_result = ?, completed_at_ms = ?,
            claim_owner = NULL, lease_expires_at_ms = NULL,
            recovery_payload_encrypted = CASE WHEN ? THEN recovery_payload_encrypted ELSE NULL END
        WHERE accepted_task_id = ? AND (
            lifecycle_status IN ('accepted', 'running')
            OR (
                lifecycle_status = 'recovery_required'
                AND EXISTS (
                    SELECT 1 FROM plugin_clone_transactions
                    WHERE task_id = mutation_admissions.accepted_task_id
                        AND phase = 'rolled_back' AND committed = 0
                )
            )
        )
        RETURNING request_id""",
        (
            lifecycle_status,
            terminal_result,
            completed_at_ms,
            int(recovery_required),
            task_id,
        ),
    ).fetchone()
    if row is None:
        return False
    if not recovery_required:
        _release_mutation_ownership(connection, row["request_id"], task_id)
    return True
