"""SoAI - Power operation record mapping and admission [backend/database/repositories/system/power_operation_records.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

from core.errors.exceptions import ConflictError, StateError
from core.system.power_operations import (
    PowerOperation,
    PowerOperationAction,
    PowerOperationStatus,
)

if TYPE_CHECKING:
    import aiosqlite

__all__ = (
    "read_active_power_operation",
    "read_power_operation",
    "read_power_operation_next_wake",
    "sync_accept_power_operation",
    "sync_read_power_operation",
)

_SELECT_FIELDS = """
operation_id, owner_id, action, force, delay_ms, accepted_at_ms, execute_at_ms,
status, claim_owner, lease_expires_at_ms, attempt_count, dispatch_started_at_ms,
completed_at_ms, result_code, error_code, active_slot
"""


def _power_record_integer(value: str | int | None, field: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise StateError(f"Power operation record field {field} is not an integer.")
    return value


def _power_record_text(value: str | int | None, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise StateError(f"Power operation record field {field} is not text.")
    return value


def _nullable_power_record_integer(value: str | int | None, field: str) -> int | None:
    if value is None:
        return None
    return _power_record_integer(value, field)


def _nullable_power_record_text(value: str | int | None, field: str) -> str | None:
    if value is None:
        return None
    return _power_record_text(value, field)


def _row_to_operation(
    row: sqlite3.Row | tuple[str | int | None, ...] | None,
) -> PowerOperation | None:
    if row is None:
        return None
    force_value = _power_record_integer(row[3], "force")
    if force_value not in {0, 1}:
        raise StateError("Power operation record field force must be zero or one.")
    return PowerOperation(
        operation_id=_power_record_text(row[0], "operation_id"),
        owner_id=_power_record_integer(row[1], "owner_id"),
        action=PowerOperationAction(_power_record_text(row[2], "action")),
        force=bool(force_value),
        delay_ms=_power_record_integer(row[4], "delay_ms"),
        accepted_at_ms=_power_record_integer(row[5], "accepted_at_ms"),
        execute_at_ms=_power_record_integer(row[6], "execute_at_ms"),
        status=PowerOperationStatus(_power_record_text(row[7], "status")),
        claim_owner=_nullable_power_record_text(row[8], "claim_owner"),
        lease_expires_at_ms=_nullable_power_record_integer(row[9], "lease_expires_at_ms"),
        attempt_count=_power_record_integer(row[10], "attempt_count"),
        dispatch_started_at_ms=_nullable_power_record_integer(
            row[11],
            "dispatch_started_at_ms",
        ),
        completed_at_ms=_nullable_power_record_integer(row[12], "completed_at_ms"),
        result_code=_nullable_power_record_text(row[13], "result_code"),
        error_code=_nullable_power_record_text(row[14], "error_code"),
        active_slot=_nullable_power_record_integer(row[15], "active_slot"),
    )


def sync_read_power_operation(
    conn: sqlite3.Connection,
    operation_id: str,
) -> PowerOperation | None:
    row = conn.execute(
        f"SELECT {_SELECT_FIELDS} FROM power_operations WHERE operation_id = ?",
        (operation_id,),
    ).fetchone()
    return _row_to_operation(row)


def sync_accept_power_operation(
    conn: sqlite3.Connection,
    operation_id: str,
    owner_id: int,
    action: PowerOperationAction,
    force: bool,
    delay_ms: int,
    accepted_at_ms: int,
    retention_cutoff_ms: int,
) -> PowerOperation:
    existing = sync_read_power_operation(conn, operation_id)
    if existing is not None:
        if (
            existing.owner_id == owner_id
            and existing.action is action
            and existing.force is force
            and existing.delay_ms == delay_ms
        ):
            return existing
        raise ConflictError("Power operation identity was reused with different input.")
    conn.execute(
        "DELETE FROM power_operations WHERE completed_at_ms < ?",
        (retention_cutoff_ms,),
    )
    try:
        conn.execute(
            """
            INSERT INTO power_operations (
                operation_id, owner_id, action, force, delay_ms, accepted_at_ms,
                execute_at_ms, status, attempt_count, active_slot
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, 'scheduled', 0, 1)
            """,
            (
                operation_id,
                owner_id,
                action.value,
                int(force),
                delay_ms,
                accepted_at_ms,
                accepted_at_ms + delay_ms,
            ),
        )
    except sqlite3.IntegrityError as exception:
        raise ConflictError("Another power operation is already active.") from exception
    operation = sync_read_power_operation(conn, operation_id)
    if operation is None:
        raise StateError("Accepted power operation could not be reloaded.")
    return operation


async def read_power_operation(
    conn: aiosqlite.Connection,
    operation_id: str,
) -> PowerOperation | None:
    cursor = await conn.execute(
        f"SELECT {_SELECT_FIELDS} FROM power_operations WHERE operation_id = ?",
        (operation_id,),
    )
    row = await cursor.fetchone()
    await cursor.close()
    return _row_to_operation(row)


async def read_active_power_operation(
    conn: aiosqlite.Connection,
) -> PowerOperation | None:
    cursor = await conn.execute(
        f"SELECT {_SELECT_FIELDS} FROM power_operations WHERE active_slot = 1"
    )
    row = await cursor.fetchone()
    await cursor.close()
    return _row_to_operation(row)


async def read_power_operation_next_wake(
    conn: aiosqlite.Connection,
) -> int | None:
    cursor = await conn.execute("""
        SELECT CASE
            WHEN status = 'scheduled' THEN execute_at_ms
            WHEN status = 'executing' THEN lease_expires_at_ms
        END
        FROM power_operations
        WHERE active_slot = 1
        """)
    row = await cursor.fetchone()
    await cursor.close()
    return int(row[0]) if row is not None and row[0] is not None else None
