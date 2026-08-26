"""SoAI - Durable mutation execution lifecycle [backend/database/repositories/tasks/mutation_lifecycle.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3

from core.database.mutation_requests import MutationClaim
from core.errors.exceptions import ValidationError
from core.tasks.constants import MUTATION_MAX_ATTEMPTS
from core.validation.strict_numbers import (
    coerce_optional_positive_int_strict,
    require_non_negative_int_strict,
    require_positive_int_strict,
)
from core.validation.strings import (
    coerce_optional_trimmed_str,
    require_canonical_trimmed_json_text,
)

__all__ = (
    "sync_claim_mutation",
    "sync_claim_next_mutation",
    "sync_advance_mutation_execution",
    "sync_cleanup_expired_mutation_admissions",
    "sync_mutation_requires_fenced_finalization",
    "sync_renew_mutation_claim",
    "sync_validate_mutation_claim",
)


def _require_lifecycle_identity(value: str, field: str) -> None:
    require_canonical_trimmed_json_text(
        value,
        error_message=f"Mutation lifecycle requires a valid {field} identity.",
    )


def sync_cleanup_expired_mutation_admissions(
    connection: sqlite3.Connection,
    now_ms: int,
) -> int:
    require_non_negative_int_strict(
        now_ms,
        error_message="Mutation lifecycle requires a valid server time.",
    )
    return connection.execute(
        """DELETE FROM mutation_admissions
        WHERE lifecycle_status IN ('completed', 'failed', 'cancelled')
            AND expires_at_ms < ?""",
        (now_ms,),
    ).rowcount


def _validate_claim(worker_id: str, now_ms: int, lease_duration_ms: int) -> None:
    _require_lifecycle_identity(worker_id, "worker")
    require_non_negative_int_strict(
        now_ms,
        error_message="Mutation lifecycle requires a valid server time.",
    )
    require_positive_int_strict(
        lease_duration_ms,
        error_message="Mutation lifecycle requires a positive lease duration.",
    )


def _claim_row(
    connection: sqlite3.Connection,
    row: sqlite3.Row,
    worker_id: str,
    *,
    now_ms: int,
    lease_duration_ms: int,
) -> MutationClaim | None:
    new_fencing_token = row["fencing_token"] + 1
    updated = connection.execute(
        """UPDATE mutation_admissions
        SET lifecycle_status = 'running', claim_owner = ?, lease_expires_at_ms = ?,
            fencing_token = ?, attempt_count = attempt_count + 1
        WHERE request_id = ? AND fencing_token = ? AND (
            lifecycle_status = 'accepted'
            OR (lifecycle_status = 'running' AND lease_expires_at_ms <= ?)
        ) AND attempt_count < ?""",
        (
            worker_id,
            now_ms + lease_duration_ms,
            new_fencing_token,
            row["request_id"],
            row["fencing_token"],
            now_ms,
            MUTATION_MAX_ATTEMPTS,
        ),
    ).rowcount
    if updated != 1:
        return None
    return MutationClaim(
        request_id=row["request_id"],
        task_id=row["accepted_task_id"],
        operation_type=row["operation_type"],
        target_identity=row["target_identity"],
        owner_id=row["owner_id"],
        authorization_scope=row["authorization_scope"],
        conflict_keys=tuple(
            claim_row["conflict_key"]
            for claim_row in connection.execute(
                """SELECT conflict_key FROM mutation_conflict_keys
                WHERE request_id = ? ORDER BY conflict_key""",
                (row["request_id"],),
            ).fetchall()
        ),
        command_payload=row["command_payload"],
        schema_discriminator=row["schema_discriminator"],
        recovery_payload_encrypted=row["recovery_payload_encrypted"],
        fencing_token=new_fencing_token,
        attempt_count=row["attempt_count"] + 1,
        execution_phase=row["execution_phase"],
        execution_state=row["execution_state"],
    )


def sync_advance_mutation_execution(
    connection: sqlite3.Connection,
    task_id: str,
    fencing_token: int,
    expected_phase: str,
    next_phase: str,
    execution_state: str,
    now_ms: int,
) -> bool:
    _require_lifecycle_identity(task_id, "task")
    _require_lifecycle_identity(expected_phase, "expected phase")
    _require_lifecycle_identity(next_phase, "next phase")
    require_canonical_trimmed_json_text(
        execution_state,
        error_message="Mutation execution state must be canonical JSON.",
    )
    require_positive_int_strict(
        fencing_token,
        error_message="Mutation execution checkpoint requires a positive fencing token.",
    )
    require_non_negative_int_strict(
        now_ms,
        error_message="Mutation execution checkpoint requires a valid server time.",
    )
    return (
        connection.execute(
            """UPDATE mutation_admissions
            SET execution_phase = ?, execution_state = ?
            WHERE accepted_task_id = ? AND lifecycle_status = 'running'
                AND fencing_token = ? AND lease_expires_at_ms > ?
                AND execution_phase = ?""",
            (
                next_phase,
                execution_state,
                task_id,
                fencing_token,
                now_ms,
                expected_phase,
            ),
        ).rowcount
        == 1
    )


def sync_claim_mutation(
    connection: sqlite3.Connection,
    request_id: str,
    worker_id: str,
    now_ms: int,
    lease_duration_ms: int,
) -> MutationClaim | None:
    _require_lifecycle_identity(request_id, "request")
    _validate_claim(worker_id, now_ms, lease_duration_ms)
    row = connection.execute(
        """SELECT * FROM mutation_admissions
        WHERE request_id = ? AND (
            lifecycle_status = 'accepted'
            OR (lifecycle_status = 'running' AND lease_expires_at_ms <= ?)
        ) AND attempt_count < ?""",
        (request_id, now_ms, MUTATION_MAX_ATTEMPTS),
    ).fetchone()
    if row is None:
        return None
    return _claim_row(
        connection,
        row,
        worker_id,
        now_ms=now_ms,
        lease_duration_ms=lease_duration_ms,
    )


def sync_claim_next_mutation(
    connection: sqlite3.Connection,
    worker_id: str,
    now_ms: int,
    lease_duration_ms: int,
) -> MutationClaim | None:
    _validate_claim(worker_id, now_ms, lease_duration_ms)
    row = connection.execute(
        """SELECT * FROM mutation_admissions
        WHERE lifecycle_status = 'accepted' AND attempt_count < ?
        ORDER BY accepted_at_ms, request_id LIMIT 1""",
        (MUTATION_MAX_ATTEMPTS,),
    ).fetchone()
    if row is None:
        return None
    return _claim_row(
        connection,
        row,
        worker_id,
        now_ms=now_ms,
        lease_duration_ms=lease_duration_ms,
    )


def sync_renew_mutation_claim(
    connection: sqlite3.Connection,
    request_id: str,
    fencing_token: int,
    worker_id: str,
    now_ms: int,
    lease_duration_ms: int,
) -> bool:
    _require_lifecycle_identity(request_id, "request")
    require_positive_int_strict(
        fencing_token,
        error_message="Mutation lifecycle requires a positive fencing token.",
    )
    _validate_claim(worker_id, now_ms, lease_duration_ms)
    return (
        connection.execute(
            """UPDATE mutation_admissions SET lease_expires_at_ms = ?
            WHERE request_id = ? AND lifecycle_status = 'running'
                AND fencing_token = ? AND claim_owner = ?
                AND lease_expires_at_ms > ?""",
            (
                now_ms + lease_duration_ms,
                request_id,
                fencing_token,
                worker_id,
                now_ms,
            ),
        ).rowcount
        == 1
    )


def sync_mutation_requires_fenced_finalization(
    connection: sqlite3.Connection,
    task_id: str,
) -> bool:
    _require_lifecycle_identity(task_id, "task")
    row = connection.execute(
        """SELECT 1 FROM mutation_admissions
        WHERE accepted_task_id = ?
            AND lifecycle_status IN ('accepted', 'running', 'recovery_required')""",
        (task_id,),
    ).fetchone()
    return row is not None


def sync_validate_mutation_claim(
    connection: sqlite3.Connection,
    task_id: str,
    fencing_token: int,
    now_ms: int,
) -> bool:
    if (
        coerce_optional_trimmed_str(task_id) is None
        or coerce_optional_positive_int_strict(fencing_token) is None
    ):
        return False
    try:
        require_non_negative_int_strict(
            now_ms,
            error_message="Mutation lifecycle requires a valid server time.",
        )
    except ValidationError:
        return False
    row = connection.execute(
        """SELECT 1 FROM mutation_admissions
        WHERE accepted_task_id = ? AND lifecycle_status = 'running'
            AND fencing_token = ? AND claim_owner IS NOT NULL
            AND lease_expires_at_ms > ?""",
        (task_id, fencing_token, now_ms),
    ).fetchone()
    return row is not None
