"""SoAI - Identity mutation record storage primitives [backend/database/repositories/users/identity_mutation_record_storage.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3

from core.errors.exceptions import ConflictError, StateError, ValidationError
from core.mutations.identifiers import extract_mutation_request_timestamp_ms
from core.mutations.identity_window import IDENTITY_RETENTION_MS
from core.timing.epoch import epoch_ms
from core.users.identity_mutation_contract import (
    IDENTITY_MUTATION_FAILURE_CODES,
    IDENTITY_MUTATION_SERVER_HORIZON_MS,
    SESSION_LINEAGE_PRUNE_GRACE_MS,
    USER_MUTATION_RESULT_MIN_RETENTION_MS,
    require_identity_mutation_status,
    require_identity_mutation_type,
)
from core.users.identity_mutation_records import (
    IdentityMutationBinding,
    IdentityMutationRecord,
)
from database.core.sqlite_numbers import (
    coerce_optional_int_from_sqlite_row,
    coerce_required_int_from_sqlite_row,
)
from database.core.sqlite_values import SQLiteRowDict


def identity_mutation_record_from_row(row: SQLiteRowDict) -> IdentityMutationRecord:
    operation_type_value = row.get("operation_type")
    status_value = row.get("status")
    if not isinstance(operation_type_value, str):
        raise StateError("Identity mutation record has an invalid operation type.")
    if not isinstance(status_value, str):
        raise StateError("Identity mutation record has an invalid status.")
    try:
        operation_type = require_identity_mutation_type(operation_type_value)
        mutation_status = require_identity_mutation_status(status_value)
    except ValidationError as exception:
        raise StateError("Identity mutation record has invalid persisted values.") from exception
    requested_username = row.get("requested_username")
    error_code = row.get("error_code")
    trace_id = row.get("trace_id")
    previous_username = row.get("previous_username")
    new_username = row.get("new_username")
    return IdentityMutationRecord(
        binding=IdentityMutationBinding(
            actor_user_id=coerce_required_int_from_sqlite_row(row, "actor_user_id"),
            operation_id=str(row["operation_id"]),
            operation_type=operation_type,
            target_user_id=coerce_required_int_from_sqlite_row(row, "target_user_id"),
            requested_username=str(requested_username) if requested_username is not None else None,
        ),
        status=mutation_status,
        completed_at_ms=coerce_required_int_from_sqlite_row(row, "completed_at_ms"),
        retain_until_ms=coerce_required_int_from_sqlite_row(row, "retain_until_ms"),
        error_code=str(error_code) if error_code is not None else None,
        trace_id=str(trace_id) if trace_id is not None else None,
        previous_username=str(previous_username) if previous_username is not None else None,
        new_username=str(new_username) if new_username is not None else None,
        new_identity_revision=(coerce_optional_int_from_sqlite_row(row, "new_identity_revision")),
        previous_password_revision=(
            coerce_optional_int_from_sqlite_row(row, "previous_password_revision")
        ),
        new_password_revision=(coerce_optional_int_from_sqlite_row(row, "new_password_revision")),
    )


def identity_mutation_binding_matches(
    record: IdentityMutationRecord,
    binding: IdentityMutationBinding,
) -> bool:
    return record.binding == binding


def sync_read_identity_mutation(
    conn: sqlite3.Connection,
    binding: IdentityMutationBinding,
) -> IdentityMutationRecord | None:
    row = conn.execute(
        """
        SELECT * FROM webui_user_mutations
        WHERE actor_user_id = ? AND operation_id = ?
        """,
        (binding.actor_user_id, binding.operation_id),
    ).fetchone()
    if row is None:
        return None
    record = identity_mutation_record_from_row(dict(row))
    if not identity_mutation_binding_matches(record, binding):
        raise ConflictError("Mutation operation ID is bound to different input.")
    return record


def calculate_identity_mutation_retention(
    binding: IdentityMutationBinding,
    completed_at_ms: int,
    rotation_cleanup_at_ms: int | None = None,
) -> int:
    identity_time = extract_mutation_request_timestamp_ms(binding.operation_id)
    return max(
        completed_at_ms + USER_MUTATION_RESULT_MIN_RETENTION_MS,
        identity_time + IDENTITY_RETENTION_MS + IDENTITY_MUTATION_SERVER_HORIZON_MS,
        rotation_cleanup_at_ms or 0,
    )


def sync_prune_expired_identity_mutations(
    conn: sqlite3.Connection,
    observed_at_ms: int,
) -> None:
    conn.execute(
        """
        DELETE FROM webui_user_mutations
        WHERE retain_until_ms < ?
          AND NOT EXISTS (
              SELECT 1 FROM webui_session_rotations rotation
              WHERE rotation.user_id = webui_user_mutations.actor_user_id
                AND rotation.operation_id = webui_user_mutations.operation_id
                AND max(rotation.source_expires_at_ms,
                        rotation.replacement_expires_at_ms,
                        rotation.recoverable_until_ms) + ? >= ?
          )
        """,
        (observed_at_ms, SESSION_LINEAGE_PRUNE_GRACE_MS, observed_at_ms),
    )


def sync_insert_failed_identity_mutation(
    conn: sqlite3.Connection,
    binding: IdentityMutationBinding,
    error_code: str,
    trace_id: str | None,
) -> IdentityMutationRecord:
    existing = sync_read_identity_mutation(conn, binding)
    if existing is not None:
        return existing
    if error_code not in IDENTITY_MUTATION_FAILURE_CODES:
        raise StateError("Identity mutation failure code cannot be persisted.")
    if (error_code == "identity_mutation_failed") != (trace_id is not None):
        raise StateError("Identity mutation trace ID does not match its failure type.")
    completed_at_ms = epoch_ms()
    sync_prune_expired_identity_mutations(conn, completed_at_ms)
    conn.execute(
        """
        INSERT INTO webui_user_mutations (
            actor_user_id, operation_id, operation_type, target_user_id,
            requested_username, completed_at_ms, retain_until_ms,
            status, error_code, trace_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, 'failed', ?, ?)
        """,
        (
            binding.actor_user_id,
            binding.operation_id,
            binding.operation_type,
            binding.target_user_id,
            binding.requested_username,
            completed_at_ms,
            calculate_identity_mutation_retention(binding, completed_at_ms),
            error_code,
            trace_id,
        ),
    )
    record = sync_read_identity_mutation(conn, binding)
    if record is None:
        raise StateError("Failed identity mutation record was not persisted.")
    return record


def sync_finalize_identity_mutation_absence(
    conn: sqlite3.Connection,
    binding: IdentityMutationBinding,
) -> IdentityMutationRecord | None:
    actor = conn.execute(
        "SELECT is_admin FROM webui_users WHERE id = ? AND account_type = 'human'",
        (binding.actor_user_id,),
    ).fetchone()
    if actor is None:
        return None
    if binding.target_user_id != binding.actor_user_id and not bool(actor["is_admin"]):
        return None
    return sync_insert_failed_identity_mutation(
        conn,
        binding,
        "identity_mutation_not_committed",
        None,
    )


def sync_insert_committed_password_mutation(
    conn: sqlite3.Connection,
    binding: IdentityMutationBinding,
    *,
    completed_at_ms: int,
    previous_password_revision: int,
    new_password_revision: int,
    rotation_cleanup_at_ms: int | None,
) -> IdentityMutationRecord:
    sync_prune_expired_identity_mutations(conn, completed_at_ms)
    conn.execute(
        """
        INSERT INTO webui_user_mutations (
            actor_user_id, operation_id, operation_type, target_user_id,
            requested_username, completed_at_ms, retain_until_ms, status,
            previous_password_revision, new_password_revision
        ) VALUES (?, ?, 'password_change', ?, NULL, ?, ?, 'committed', ?, ?)
        """,
        (
            binding.actor_user_id,
            binding.operation_id,
            binding.target_user_id,
            completed_at_ms,
            calculate_identity_mutation_retention(
                binding,
                completed_at_ms,
                rotation_cleanup_at_ms,
            ),
            previous_password_revision,
            new_password_revision,
        ),
    )
    record = sync_read_identity_mutation(conn, binding)
    if record is None:
        raise StateError("Committed password mutation record was not persisted.")
    return record


def sync_insert_committed_username_mutation(
    conn: sqlite3.Connection,
    binding: IdentityMutationBinding,
    *,
    previous_username: str,
    new_identity_revision: int,
    completed_at_ms: int,
    rotation_cleanup_at_ms: int | None,
) -> IdentityMutationRecord:
    sync_prune_expired_identity_mutations(conn, completed_at_ms)
    conn.execute(
        """
        INSERT INTO webui_user_mutations (
            actor_user_id, operation_id, operation_type, target_user_id,
            requested_username, completed_at_ms, retain_until_ms, status,
            previous_username, new_username, new_identity_revision
        ) VALUES (?, ?, 'username_rename', ?, ?, ?, ?, 'committed', ?, ?, ?)
        """,
        (
            binding.actor_user_id,
            binding.operation_id,
            binding.target_user_id,
            binding.requested_username,
            completed_at_ms,
            calculate_identity_mutation_retention(
                binding,
                completed_at_ms,
                rotation_cleanup_at_ms,
            ),
            previous_username,
            binding.requested_username,
            new_identity_revision,
        ),
    )
    record = sync_read_identity_mutation(conn, binding)
    if record is None:
        raise StateError("Committed username mutation record was not persisted.")
    return record


__all__ = (
    "calculate_identity_mutation_retention",
    "identity_mutation_binding_matches",
    "identity_mutation_record_from_row",
    "sync_finalize_identity_mutation_absence",
    "sync_insert_failed_identity_mutation",
    "sync_insert_committed_password_mutation",
    "sync_insert_committed_username_mutation",
    "sync_read_identity_mutation",
    "sync_prune_expired_identity_mutations",
)
