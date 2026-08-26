"""SoAI - Expired mutation recovery discovery [backend/database/repositories/tasks/mutation_recovery.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3

from core.database.mutation_requests import (
    MutationRecoveryCandidate,
    MutationRecoveryRequiredAdmission,
)
from core.tasks.constants import MUTATION_MAX_ATTEMPTS
from core.validation.requirements import require_nonempty_str
from core.validation.strict_numbers import (
    require_non_negative_int_strict,
    require_positive_int_strict,
)
from database.core.savepoints import SQLiteSavepoint

__all__ = (
    "sync_quarantine_exhausted_mutations",
    "sync_query_expired_mutation_recovery_candidates",
    "sync_query_recovery_required_admissions",
)


def sync_quarantine_exhausted_mutations(
    connection: sqlite3.Connection,
    now_ms: int,
) -> tuple[str, ...]:
    require_non_negative_int_strict(
        now_ms,
        error_message="Mutation recovery requires a valid server time.",
    )
    with SQLiteSavepoint(connection, "mutation_recovery_quarantine"):
        task_rows = connection.execute(
            """UPDATE unified_tasks
            SET status = 'failed', updated_at_ms = ?, completed_at_ms = ?,
                error_message = 'Mutation recovery attempts were exhausted.',
                status_message = 'Mutation requires operator recovery.',
                orchestration_state = NULL,
                progress_current = CASE
                    WHEN progress_total IS NOT NULL THEN progress_total
                    ELSE progress_current
                END
            WHERE task_id IN (
                SELECT accepted_task_id FROM mutation_admissions
                WHERE attempt_count >= ? AND (
                    lifecycle_status = 'accepted'
                    OR (lifecycle_status = 'running' AND lease_expires_at_ms <= ?)
                )
            ) AND status NOT IN ('completed', 'failed', 'cancelled')
            RETURNING task_id""",
            (now_ms, now_ms, MUTATION_MAX_ATTEMPTS, now_ms),
        ).fetchall()
        connection.execute(
            """UPDATE mutation_admissions
            SET lifecycle_status = 'recovery_required', claim_owner = NULL,
                lease_expires_at_ms = NULL, completed_at_ms = ?
            WHERE attempt_count >= ? AND (
                lifecycle_status = 'accepted'
                OR (lifecycle_status = 'running' AND lease_expires_at_ms <= ?)
            )""",
            (now_ms, MUTATION_MAX_ATTEMPTS, now_ms),
        )
        return tuple(sorted(row["task_id"] for row in task_rows))


def sync_query_recovery_required_admissions(
    connection: sqlite3.Connection,
    operation_type: str | None = None,
) -> tuple[MutationRecoveryRequiredAdmission, ...]:
    operation = (
        require_nonempty_str(operation_type, field="operation_type")
        if operation_type is not None
        else None
    )
    rows = connection.execute(
        """SELECT admissions.request_id, admissions.accepted_task_id,
            admissions.operation_type, admissions.target_identity,
            admissions.command_payload, admissions.execution_phase,
            admissions.attempt_count, claims.conflict_key
        FROM mutation_admissions AS admissions
        JOIN mutation_conflict_keys AS claims
            ON claims.request_id = admissions.request_id
        WHERE admissions.lifecycle_status = 'recovery_required'
            AND (? IS NULL OR admissions.operation_type = ?)
        ORDER BY admissions.accepted_at_ms, admissions.request_id, claims.conflict_key""",
        (operation, operation),
    ).fetchall()
    row_by_request: dict[str, sqlite3.Row] = {}
    conflict_keys_by_request: dict[str, list[str]] = {}
    for row in rows:
        request_id = row["request_id"]
        row_by_request[request_id] = row
        if request_id not in conflict_keys_by_request:
            conflict_keys_by_request[request_id] = []
        conflict_keys_by_request[request_id].append(row["conflict_key"])
    records: list[MutationRecoveryRequiredAdmission] = []
    for request_id, conflict_keys in conflict_keys_by_request.items():
        row = row_by_request[request_id]
        records.append(
            MutationRecoveryRequiredAdmission(
                request_id=request_id,
                task_id=row["accepted_task_id"],
                operation_type=row["operation_type"],
                target_identity=row["target_identity"],
                conflict_keys=tuple(conflict_keys),
                command_payload=row["command_payload"],
                execution_phase=row["execution_phase"],
                attempt_count=row["attempt_count"],
            )
        )
    return tuple(records)


def sync_query_expired_mutation_recovery_candidates(
    connection: sqlite3.Connection,
    now_ms: int,
    limit: int,
) -> tuple[MutationRecoveryCandidate, ...]:
    require_non_negative_int_strict(
        now_ms,
        error_message="Mutation recovery requires a valid server time.",
    )
    validated_limit = require_positive_int_strict(
        limit,
        error_message="Mutation recovery requires a positive candidate limit.",
    )
    rows = connection.execute(
        """WITH expired AS (
            SELECT request_id FROM mutation_admissions
            WHERE lifecycle_status = 'running' AND lease_expires_at_ms <= ?
            ORDER BY accepted_at_ms, request_id LIMIT ?
        )
        SELECT expired.request_id, admissions.operation_type, claims.conflict_key
        FROM expired
        JOIN mutation_admissions AS admissions
            ON admissions.request_id = expired.request_id
        JOIN mutation_conflict_keys AS claims ON claims.request_id = expired.request_id
        ORDER BY expired.request_id, claims.conflict_key""",
        (now_ms, validated_limit),
    ).fetchall()
    operation_by_request: dict[str, str] = {}
    conflict_keys_by_request: dict[str, list[str]] = {}
    for row in rows:
        request_id = row["request_id"]
        operation_by_request[request_id] = row["operation_type"]
        if request_id not in conflict_keys_by_request:
            conflict_keys_by_request[request_id] = []
        conflict_keys_by_request[request_id].append(row["conflict_key"])
    candidates: list[MutationRecoveryCandidate] = []
    for request_id, conflict_keys in conflict_keys_by_request.items():
        candidates.append(
            MutationRecoveryCandidate(
                request_id=request_id,
                operation_type=operation_by_request[request_id],
                conflict_keys=tuple(conflict_keys),
            )
        )
    return tuple(candidates)
