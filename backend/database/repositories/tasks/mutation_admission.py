"""SoAI - Durable mutation admission operations [backend/database/repositories/tasks/mutation_admission.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3

from core.database.mutation_requests import (
    MutationAdmissionOutcome,
    MutationAdmissionRequest,
)
from core.database.task_requests import CreateUnifiedTaskRequest
from core.errors.exceptions import StateError, ValidationError
from core.mutations.identifiers import (
    extract_mutation_request_timestamp_ms,
    require_mutation_request_id,
)
from core.mutations.identity_window import (
    IDENTITY_RETENTION_MS,
    MutationIdentityExpiredError,
    MutationIdentityTimeSkewError,
    validate_mutation_identity_window,
)
from core.mutations.protocols import MutationAdmissionHookProtocol
from core.serialization.json_parsing import parse_json_dict
from database.core.savepoints import SQLiteSavepoint
from database.repositories.tasks import crud
from database.repositories.tasks.clone_mutation_admission import (
    reserve_clone_target_for_admission,
    validate_clone_admission_request,
)
from database.repositories.tasks.mutation_conflict_claims import (
    find_mutation_conflict_owner,
    insert_mutation_conflict_claims,
    insert_reserved_target_conflict_claim,
    serialize_mutation_conflict_keys,
    validate_mutation_conflict_keys,
)
from database.repositories.tasks.mutation_lifecycle import (
    sync_cleanup_expired_mutation_admissions,
)

__all__ = (
    "MutationIdentityExpiredError",
    "MutationIdentityTimeSkewError",
    "sync_admit_mutation",
    "sync_accept_mutation_task",
)


def sync_accept_mutation_task(
    connection: sqlite3.Connection,
    task_request: CreateUnifiedTaskRequest,
    admission_request: MutationAdmissionRequest,
    server_time_ms: int,
    admission_hook: MutationAdmissionHookProtocol | None = None,
) -> MutationAdmissionOutcome:
    if (
        task_request.task_id != admission_request.accepted_task_id
        or admission_request.request_id != admission_request.accepted_task_id
    ):
        raise ValidationError("Mutation admission task identities do not match.")
    existing = connection.execute(
        "SELECT 1 FROM mutation_admissions WHERE request_id = ?",
        (admission_request.request_id,),
    ).fetchone()
    if existing is not None:
        return sync_admit_mutation(
            connection,
            admission_request,
            server_time_ms=server_time_ms,
            admission_hook=admission_hook,
        )
    with SQLiteSavepoint(connection, "mutation_task_acceptance") as savepoint:
        if not crud.sync_create_unified_task(connection, task_request):
            raise StateError("Mutation task identity already exists without an admission.")
        outcome = sync_admit_mutation(
            connection,
            admission_request,
            server_time_ms=server_time_ms,
            admission_hook=admission_hook,
        )
        if outcome.outcome == "conflict":
            savepoint.rollback()
        return outcome


def _validate_request(request: MutationAdmissionRequest) -> None:
    require_mutation_request_id(request.request_id)
    validate_mutation_conflict_keys(request)
    parse_json_dict(request.command_payload, field="command_payload")
    if request.operation_type == "plugin_clone":
        validate_clone_admission_request(request)
    if request.supersedes_request_id is not None:
        require_mutation_request_id(request.supersedes_request_id)


def _matches_existing(row: sqlite3.Row, request: MutationAdmissionRequest) -> bool:
    fields = (
        ("accepted_task_id", request.accepted_task_id),
        ("conflict_keys", serialize_mutation_conflict_keys(request.conflict_keys)),
        (
            "shared_conflict_keys",
            serialize_mutation_conflict_keys(request.shared_conflict_keys),
        ),
        ("operation_type", request.operation_type),
        ("authorization_scope", request.authorization_scope),
        ("command_payload", request.command_payload),
        ("schema_discriminator", request.schema_discriminator),
    )
    if not all(row[field_name] == expected for field_name, expected in fields):
        return False
    return (
        request.operation_type == "plugin_clone"
        or row["target_identity"] == request.target_identity
    )


def _replay_outcome(
    row: sqlite3.Row,
    request: MutationAdmissionRequest,
) -> MutationAdmissionOutcome:
    if row["owner_id"] != request.owner_id:
        raise PermissionError("Mutation request identity belongs to another owner.")
    if not _matches_existing(row, request):
        raise StateError("Mutation request identity was reused with different input.")
    return MutationAdmissionOutcome(outcome="replay", task_id=row["accepted_task_id"])


def sync_admit_mutation(
    connection: sqlite3.Connection,
    request: MutationAdmissionRequest,
    *,
    server_time_ms: int,
    admission_hook: MutationAdmissionHookProtocol | None = None,
) -> MutationAdmissionOutcome:
    _validate_request(request)
    if (
        isinstance(server_time_ms, bool)
        or not isinstance(server_time_ms, int)
        or server_time_ms < 0
    ):
        raise ValidationError("Mutation admission requires a valid server time.")
    connection.execute(
        """INSERT INTO mutation_admission_clock (singleton, server_time_watermark_ms)
        VALUES (1, ?) ON CONFLICT(singleton) DO UPDATE SET
        server_time_watermark_ms = MAX(server_time_watermark_ms, excluded.server_time_watermark_ms)""",
        (server_time_ms,),
    )
    server_time_watermark_ms = connection.execute(
        "SELECT server_time_watermark_ms FROM mutation_admission_clock WHERE singleton = 1"
    ).fetchone()[0]
    sync_cleanup_expired_mutation_admissions(connection, server_time_watermark_ms)
    existing = connection.execute(
        "SELECT * FROM mutation_admissions WHERE request_id = ?",
        (request.request_id,),
    ).fetchone()
    if existing is not None:
        return _replay_outcome(existing, request)
    validate_mutation_identity_window(request.request_id, server_time_watermark_ms)
    try:
        with SQLiteSavepoint(connection, "mutation_admission_insert") as savepoint:
            if admission_hook is not None:
                admission_hook(
                    connection,
                    request,
                    completed_at_ms=server_time_watermark_ms,
                )
            conflict = find_mutation_conflict_owner(connection, request)
            if conflict is not None:
                savepoint.rollback()
                task_id = conflict[0] if conflict[1] == request.owner_id else ""
                return MutationAdmissionOutcome(outcome="conflict", task_id=task_id)
            target_identity = request.target_identity
            connection.execute(
                """INSERT INTO mutation_admissions (
                request_id, accepted_task_id, conflict_keys, shared_conflict_keys,
                operation_type, target_identity, owner_id,
                authorization_scope, command_payload, schema_discriminator,
                recovery_payload_encrypted, accepted_at_ms, expires_at_ms
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    request.request_id,
                    request.accepted_task_id,
                    serialize_mutation_conflict_keys(request.conflict_keys),
                    serialize_mutation_conflict_keys(request.shared_conflict_keys),
                    request.operation_type,
                    target_identity,
                    request.owner_id,
                    request.authorization_scope,
                    request.command_payload,
                    request.schema_discriminator,
                    request.recovery_payload_encrypted,
                    server_time_watermark_ms,
                    extract_mutation_request_timestamp_ms(request.request_id)
                    + IDENTITY_RETENTION_MS,
                ),
            )
            insert_mutation_conflict_claims(connection, request)
            if request.operation_type == "plugin_clone":
                allocated_target = reserve_clone_target_for_admission(
                    connection,
                    request,
                    created_at_ms=server_time_watermark_ms,
                )
                if allocated_target is None:
                    savepoint.rollback()
                    return MutationAdmissionOutcome(outcome="conflict", task_id="")
                connection.execute(
                    "UPDATE mutation_admissions SET target_identity = ? WHERE request_id = ?",
                    (allocated_target, request.request_id),
                )
                insert_reserved_target_conflict_claim(
                    connection,
                    request.request_id,
                    allocated_target,
                )
    except sqlite3.IntegrityError:
        conflict = find_mutation_conflict_owner(connection, request)
        if conflict is None:
            raise
        task_id = conflict[0] if conflict[1] == request.owner_id else ""
        return MutationAdmissionOutcome(outcome="conflict", task_id=task_id)
    return MutationAdmissionOutcome(outcome="accepted", task_id=request.accepted_task_id)
