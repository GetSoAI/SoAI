"""SoAI - SQLite power operation state transitions [backend/database/repositories/system/power_operation_persistence.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3

from core.errors.exceptions import StateError
from core.system.power_operations import (
    PowerOperation,
    PowerOperationStatus,
)
from database.repositories.system.power_operation_records import (
    sync_read_power_operation,
)

__all__ = (
    "sync_cancel_power_operation",
    "sync_claim_due_power_operation",
    "sync_complete_power_operation",
    "sync_fail_power_operation",
    "sync_mark_power_dispatch_started",
    "sync_reconcile_power_operations",
)


def sync_cancel_power_operation(
    conn: sqlite3.Connection,
    operation_id: str,
    cancelled_at_ms: int,
) -> PowerOperation:
    cursor = conn.execute(
        """
        UPDATE power_operations
        SET status = 'cancelled', completed_at_ms = ?, active_slot = NULL,
            result_code = NULL, error_code = NULL
        WHERE operation_id = ? AND status = 'scheduled'
        """,
        (cancelled_at_ms, operation_id),
    )
    if cursor.rowcount != 1:
        raise StateError("Power operation can only be cancelled while scheduled.")
    operation = sync_read_power_operation(conn, operation_id)
    if operation is None:
        raise StateError("Cancelled power operation could not be reloaded.")
    return operation


def sync_claim_due_power_operation(
    conn: sqlite3.Connection,
    now_ms: int,
    claim_owner: str,
    lease_duration_ms: int,
    max_attempts: int,
) -> PowerOperation | None:
    row = conn.execute(
        """
        SELECT operation_id
        FROM power_operations
        WHERE status = 'scheduled' AND execute_at_ms <= ? AND attempt_count < ?
        ORDER BY execute_at_ms, accepted_at_ms
        LIMIT 1
        """,
        (now_ms, max_attempts),
    ).fetchone()
    if row is None:
        return None
    operation_id = str(row[0])
    cursor = conn.execute(
        """
        UPDATE power_operations
        SET status = 'executing', claim_owner = ?, lease_expires_at_ms = ?,
            attempt_count = attempt_count + 1
        WHERE operation_id = ? AND status = 'scheduled'
        """,
        (claim_owner, now_ms + lease_duration_ms, operation_id),
    )
    if cursor.rowcount != 1:
        return None
    return sync_read_power_operation(conn, operation_id)


def sync_mark_power_dispatch_started(
    conn: sqlite3.Connection,
    operation_id: str,
    claim_owner: str,
    dispatch_started_at_ms: int,
) -> PowerOperation:
    cursor = conn.execute(
        """
        UPDATE power_operations
        SET dispatch_started_at_ms = ?
        WHERE operation_id = ? AND status = 'executing' AND claim_owner = ?
            AND dispatch_started_at_ms IS NULL
        """,
        (dispatch_started_at_ms, operation_id, claim_owner),
    )
    if cursor.rowcount != 1:
        raise StateError("Power operation dispatch checkpoint could not be claimed.")
    operation = sync_read_power_operation(conn, operation_id)
    if operation is None:
        raise StateError("Dispatched power operation could not be reloaded.")
    return operation


def _sync_finish_power_operation(
    conn: sqlite3.Connection,
    operation_id: str,
    claim_owner: str,
    completed_at_ms: int,
    status: PowerOperationStatus,
    result_code: str | None,
    error_code: str | None,
) -> PowerOperation:
    cursor = conn.execute(
        """
        UPDATE power_operations
        SET status = ?, completed_at_ms = ?, result_code = ?, error_code = ?,
            active_slot = NULL, lease_expires_at_ms = NULL
        WHERE operation_id = ? AND status = 'executing' AND claim_owner = ?
        """,
        (
            status.value,
            completed_at_ms,
            result_code,
            error_code,
            operation_id,
            claim_owner,
        ),
    )
    if cursor.rowcount != 1:
        raise StateError("Power operation terminal transition was rejected.")
    operation = sync_read_power_operation(conn, operation_id)
    if operation is None:
        raise StateError("Terminal power operation could not be reloaded.")
    return operation


def sync_complete_power_operation(
    conn: sqlite3.Connection,
    operation_id: str,
    claim_owner: str,
    completed_at_ms: int,
    result_code: str,
) -> PowerOperation:
    return _sync_finish_power_operation(
        conn,
        operation_id,
        claim_owner,
        completed_at_ms,
        PowerOperationStatus.COMPLETED,
        result_code,
        None,
    )


def sync_fail_power_operation(
    conn: sqlite3.Connection,
    operation_id: str,
    claim_owner: str,
    completed_at_ms: int,
    error_code: str,
) -> PowerOperation:
    return _sync_finish_power_operation(
        conn,
        operation_id,
        claim_owner,
        completed_at_ms,
        PowerOperationStatus.FAILED,
        None,
        error_code,
    )


def sync_reconcile_power_operations(
    conn: sqlite3.Connection,
    now_ms: int,
    max_attempts: int,
    retention_cutoff_ms: int,
) -> tuple[PowerOperation, ...]:
    changed_ids = [
        str(row[0])
        for row in conn.execute(
            """
            SELECT operation_id
            FROM power_operations
            WHERE status = 'executing' AND (
                dispatch_started_at_ms IS NOT NULL OR lease_expires_at_ms <= ?
            )
            """,
            (now_ms,),
        ).fetchall()
    ]
    conn.execute(
        """
        UPDATE power_operations
        SET status = 'failed', completed_at_ms = ?, error_code = 'power_outcome_unknown',
            active_slot = NULL, lease_expires_at_ms = NULL
        WHERE status = 'executing' AND dispatch_started_at_ms IS NOT NULL
        """,
        (now_ms,),
    )
    conn.execute(
        """
        UPDATE power_operations
        SET status = 'failed', completed_at_ms = ?, error_code = 'power_attempts_exhausted',
            active_slot = NULL, claim_owner = NULL, lease_expires_at_ms = NULL
        WHERE status = 'executing' AND dispatch_started_at_ms IS NULL
            AND lease_expires_at_ms <= ? AND attempt_count >= ?
        """,
        (now_ms, now_ms, max_attempts),
    )
    conn.execute(
        """
        UPDATE power_operations
        SET status = 'scheduled', claim_owner = NULL, lease_expires_at_ms = NULL
        WHERE status = 'executing' AND dispatch_started_at_ms IS NULL
            AND lease_expires_at_ms <= ? AND attempt_count < ?
        """,
        (now_ms, max_attempts),
    )
    changed = tuple(
        operation
        for operation_id in changed_ids
        if (operation := sync_read_power_operation(conn, operation_id)) is not None
    )
    conn.execute(
        "DELETE FROM power_operations WHERE completed_at_ms < ?",
        (retention_cutoff_ms,),
    )
    return changed
