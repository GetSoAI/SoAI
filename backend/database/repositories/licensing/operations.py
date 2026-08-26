"""SoAI - Durable licensing operation state machine [backend/database/repositories/licensing/operations.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3

from core.errors.exceptions import ConcurrencyError, ConflictError, StateError, ValidationError
from core.licensing.storage_records import LicensingOperationInsert
from core.types.json import JSONDict
from database.core.query_execution import sync_fetch_one_as_dict
from database.core.row_materialization import sqlite_row_dict_to_json_dict
from database.repositories.licensing.operation_queries import LICENSING_OPERATION_PUBLIC_COLUMNS

__all__ = (
    "sync_claim_licensing_operation",
    "sync_create_licensing_operation",
    "sync_complete_licensing_operation",
    "sync_blocking_licensing_operation_exists",
    "sync_transition_licensing_operation",
)

_TRANSITIONS = frozenset(
    (
        ("prepared", "sending"),
        ("prepared", "succeeded"),
        ("prepared", "cancelled"),
        ("prepared", "failed"),
        ("sending", "outcome_unknown"),
        ("sending", "retry_wait"),
        ("sending", "succeeded"),
        ("sending", "failed"),
        ("outcome_unknown", "reconciling"),
        ("outcome_unknown", "retry_wait"),
        ("outcome_unknown", "failed"),
        ("reconciling", "outcome_unknown"),
        ("reconciling", "retry_wait"),
        ("reconciling", "succeeded"),
        ("reconciling", "failed"),
        ("retry_wait", "sending"),
        ("retry_wait", "reconciling"),
        ("retry_wait", "outcome_unknown"),
        ("retry_wait", "cancelled"),
        ("retry_wait", "failed"),
    )
)
_BLOCKING_OPERATION_QUERY = """SELECT operation_id FROM licensing_operations
WHERE state IN ('prepared', 'sending', 'outcome_unknown', 'reconciling',
'retry_wait') LIMIT 1"""


def sync_blocking_licensing_operation_exists(connection: sqlite3.Connection) -> bool:
    return connection.execute(_BLOCKING_OPERATION_QUERY).fetchone() is not None


def sync_create_licensing_operation(
    connection: sqlite3.Connection,
    operation: LicensingOperationInsert,
) -> JSONDict:
    existing = _read_operation(connection, operation.operation_id)
    if existing is not None:
        expected = {
            "operation_type": operation.operation_type,
            "idempotency_key": operation.idempotency_key,
            "parent_operation_id": operation.parent_operation_id,
            "request_digest": operation.request_digest,
            "edition": operation.edition,
            "licensed_product_scope": operation.licensed_product_scope,
            "instance_id": operation.instance_id,
            "activation_id": operation.activation_id,
            "deployment_id": operation.deployment_id,
            "deactivation_reason": operation.deactivation_reason,
            "created_at_ms": operation.created_at_ms,
        }
        if any(
            existing[field] != value for field, value in expected.items()
        ) or _read_private_request_fields(connection, operation.operation_id) != (
            operation.request_nonce,
            operation.canonical_request,
        ):
            raise StateError("Licensing operation identity was reused with different input.")
        return existing
    if sync_blocking_licensing_operation_exists(connection):
        raise ConflictError("A licensing operation is already in progress.")
    connection.execute(
        """INSERT INTO licensing_operations (
        operation_id, operation_type, state, idempotency_key, parent_operation_id,
        request_digest, request_nonce, canonical_request, edition, licensed_product_scope, instance_id,
        activation_id, deployment_id, deactivation_reason,
        attempt_count, last_attempt_at_ms, next_retry_at_ms, terminal_code,
        created_at_ms, updated_at_ms
        ) VALUES (?, ?, 'prepared', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, NULL, NULL, NULL, ?, ?)""",
        (
            operation.operation_id,
            operation.operation_type,
            operation.idempotency_key,
            operation.parent_operation_id,
            operation.request_digest,
            operation.request_nonce,
            operation.canonical_request,
            operation.edition,
            operation.licensed_product_scope,
            operation.instance_id,
            operation.activation_id,
            operation.deployment_id,
            operation.deactivation_reason,
            operation.created_at_ms,
            operation.created_at_ms,
        ),
    )
    created = _read_operation(connection, operation.operation_id)
    if created is None:
        raise StateError("Licensing operation was not persisted.")
    return created


def sync_claim_licensing_operation(
    connection: sqlite3.Connection,
    operation_id: str,
    claimed_at_ms: int,
) -> bool:
    return (
        connection.execute(
            """UPDATE licensing_operations SET
        state = 'sending', attempt_count = attempt_count + 1,
        last_attempt_at_ms = ?, next_retry_at_ms = NULL, updated_at_ms = ?
        WHERE operation_id = ? AND state IN ('prepared', 'retry_wait')""",
            (claimed_at_ms, claimed_at_ms, operation_id),
        ).rowcount
        == 1
    )


def sync_transition_licensing_operation(
    connection: sqlite3.Connection,
    operation_id: str,
    expected_state: str,
    target_state: str,
    updated_at_ms: int,
    next_retry_at_ms: int | None = None,
    terminal_code: str | None = None,
) -> bool:
    if (expected_state, target_state) not in _TRANSITIONS:
        raise ConcurrencyError("Licensing operation transition is not permitted.")
    if (target_state in {"retry_wait", "outcome_unknown"}) != (next_retry_at_ms is not None):
        raise StateError("Licensing retry transition requires exactly one retry time.")
    updated = connection.execute(
        """UPDATE licensing_operations SET state = ?, next_retry_at_ms = ?,
        terminal_code = ?, updated_at_ms = ?,
        attempt_count = attempt_count + CASE WHEN ? = 'reconciling' THEN 1 ELSE 0 END,
        last_attempt_at_ms = CASE WHEN ? = 'reconciling' THEN ? ELSE last_attempt_at_ms END
        WHERE operation_id = ? AND state = ?""",
        (
            target_state,
            next_retry_at_ms,
            terminal_code,
            updated_at_ms,
            target_state,
            target_state,
            updated_at_ms,
            operation_id,
            expected_state,
        ),
    ).rowcount
    return updated == 1


def sync_complete_licensing_operation(
    connection: sqlite3.Connection,
    operation_id: str,
    expected_state: str,
    response_content: bytes,
    completed_at_ms: int,
) -> None:
    if not 2 <= len(response_content) <= 65_536:
        raise ValidationError("Licensing operation response size is invalid.")
    if (expected_state, "succeeded") not in _TRANSITIONS:
        raise ConcurrencyError("Licensing operation completion is not permitted.")
    updated = connection.execute(
        """UPDATE licensing_operations SET state='succeeded', response_content=?,
        next_retry_at_ms=NULL, terminal_code=NULL, updated_at_ms=?
        WHERE operation_id=? AND state=?""",
        (response_content, completed_at_ms, operation_id, expected_state),
    ).rowcount
    if updated != 1:
        raise ConcurrencyError("Licensing operation changed before completion.")


def _read_operation(connection: sqlite3.Connection, operation_id: str) -> JSONDict | None:
    raw_row = sync_fetch_one_as_dict(
        connection.execute(
            f"SELECT {LICENSING_OPERATION_PUBLIC_COLUMNS} FROM licensing_operations WHERE operation_id = ?",
            (operation_id,),
        )
    )
    return sqlite_row_dict_to_json_dict(raw_row) if raw_row is not None else None


def _read_private_request_fields(
    connection: sqlite3.Connection,
    operation_id: str,
) -> tuple[bytes | None, bytes | None]:
    row = connection.execute(
        "SELECT request_nonce, canonical_request FROM licensing_operations WHERE operation_id = ?",
        (operation_id,),
    ).fetchone()
    if row is None:
        return (None, None)
    if any(value is not None and not isinstance(value, bytes) for value in row):
        raise StateError("Stored licensing request content is invalid.")
    return (row[0], row[1])
