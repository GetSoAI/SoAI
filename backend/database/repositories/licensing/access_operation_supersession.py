"""SoAI - Licensing access operation supersession [backend/database/repositories/licensing/access_operation_supersession.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3

from core.errors.exceptions import ConcurrencyError, ValidationError
from database.repositories.licensing.operations import sync_transition_licensing_operation


def sync_cancel_access_operation(
    connection: sqlite3.Connection,
    changed_at_ms: int,
) -> None:
    operation = _blocking_operation(connection)
    if operation is not None:
        _retire_operation(connection, operation, changed_at_ms)


def sync_supersede_access_operation(
    connection: sqlite3.Connection,
    target_operation_type: str,
    changed_at_ms: int,
) -> None:
    if target_operation_type not in {
        "activation",
        "evaluation",
        "offline_export",
        "offline_import",
    }:
        raise ValidationError("Licensing access operation type is invalid.")
    operation = _blocking_operation(connection)
    if operation is None or operation[1] == target_operation_type:
        return
    _retire_operation(connection, operation, changed_at_ms)


def _blocking_operation(connection: sqlite3.Connection) -> tuple[str, str, str] | None:
    row = connection.execute("""SELECT operation_id, operation_type, state FROM licensing_operations
        WHERE state IN ('prepared', 'sending', 'outcome_unknown', 'reconciling',
        'retry_wait') LIMIT 1""").fetchone()
    if row is None:
        return None
    return (str(row[0]), str(row[1]), str(row[2]))


def _retire_operation(
    connection: sqlite3.Connection,
    operation: tuple[str, str, str],
    changed_at_ms: int,
) -> None:
    operation_id, operation_type, state = operation
    if operation_type not in {"activation", "evaluation"}:
        raise ConcurrencyError("A licensing operation is still in progress.")
    if state != "prepared":
        raise ConcurrencyError("A licensing operation is still in progress.")
    transitioned = sync_transition_licensing_operation(
        connection,
        operation_id,
        expected_state=state,
        target_state="cancelled",
        updated_at_ms=changed_at_ms,
    )
    if not transitioned:
        raise ConcurrencyError("Licensing operation changed before supersession.")


__all__ = (
    "sync_cancel_access_operation",
    "sync_supersede_access_operation",
)
