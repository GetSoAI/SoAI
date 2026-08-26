"""SoAI - Durable database operation status repository [backend/database/repositories/system/database_operations.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

import aiosqlite

from core.database.operation_status import (
    DatabaseOperationStatus,
    DatabaseOperationStatusValue,
)
from core.errors.exceptions import ValidationError
from core.mutations.identifiers import extract_timestamped_operation_id_ms
from core.timing.durations import MILLISECONDS_PER_MINUTE
from core.timing.epoch import epoch_ms
from database.operation_receipts import (
    DATABASE_OPERATION_RETENTION_MS,
)

if TYPE_CHECKING:
    from core.database.protocols import DatabaseCoreProtocol

__all__ = ("DatabaseOperationStatusRepository",)

DATABASE_OPERATION_FUTURE_TOLERANCE_MS = 5 * MILLISECONDS_PER_MINUTE


async def _read_receipt(
    connection: aiosqlite.Connection,
    operation_id: str,
) -> int | None:
    cursor = await connection.execute(
        """
        SELECT committed_at_ms
        FROM database_write_receipts
        WHERE operation_id = ?
        """,
        (operation_id,),
    )
    row = await cursor.fetchone()
    await cursor.close()
    if row is None:
        return None
    committed_at_ms = row[0]
    if not isinstance(committed_at_ms, int) or isinstance(committed_at_ms, bool):
        raise ValidationError("Database operation receipt is invalid.")
    return committed_at_ms


class DatabaseOperationStatusRepository:
    def __init__(self, core: DatabaseCoreProtocol) -> None:
        self._core = core

    async def resolve(
        self,
        operation_id: str,
        *,
        now_ms: int | None = None,
    ) -> DatabaseOperationStatus:
        operation_timestamp_ms = extract_timestamped_operation_id_ms(operation_id, "dbop")
        resolved_now_ms = epoch_ms() if now_ms is None else now_ms
        if operation_timestamp_ms > resolved_now_ms + DATABASE_OPERATION_FUTURE_TOLERANCE_MS:
            raise ValidationError(
                "Database operation ID timestamp is implausibly far in the future."
            )
        expires_at_ms = operation_timestamp_ms + DATABASE_OPERATION_RETENTION_MS
        if resolved_now_ms > expires_at_ms:
            return self._build_status(
                operation_id,
                DatabaseOperationStatusValue.EXPIRED,
                expires_at_ms=expires_at_ms,
                committed_at_ms=None,
            )
        committed_at_ms = await self._core.reader.execute_read(
            _read_receipt,
            operation_id,
        )
        if committed_at_ms is not None:
            return self._build_status(
                operation_id,
                DatabaseOperationStatusValue.COMMITTED,
                expires_at_ms=expires_at_ms,
                committed_at_ms=committed_at_ms,
            )
        live_status = self._core.writer.get_operation_status(operation_id)
        status: DatabaseOperationStatusValue
        match live_status:
            case "pending":
                status = DatabaseOperationStatusValue.PENDING
            case "executing":
                status = DatabaseOperationStatusValue.EXECUTING
            case "failed":
                status = DatabaseOperationStatusValue.FAILED
            case "skipped":
                status = DatabaseOperationStatusValue.SKIPPED
            case "outcome_unknown":
                status = DatabaseOperationStatusValue.OUTCOME_UNKNOWN
            case _:
                status = DatabaseOperationStatusValue.NOT_COMMITTED
        return self._build_status(
            operation_id,
            status,
            expires_at_ms=expires_at_ms,
            committed_at_ms=None,
        )

    @staticmethod
    def _build_status(
        operation_id: str,
        status: DatabaseOperationStatusValue,
        *,
        expires_at_ms: int,
        committed_at_ms: int | None,
    ) -> DatabaseOperationStatus:
        terminal = status not in {
            DatabaseOperationStatusValue.PENDING,
            DatabaseOperationStatusValue.EXECUTING,
        }
        retry_safe = status in {
            DatabaseOperationStatusValue.FAILED,
            DatabaseOperationStatusValue.SKIPPED,
            DatabaseOperationStatusValue.NOT_COMMITTED,
        }
        return DatabaseOperationStatus(
            operation_id=operation_id,
            status=status,
            terminal=terminal,
            retry_safe=retry_safe,
            committed_at_ms=committed_at_ms,
            expires_at_ms=expires_at_ms,
        )
