"""SoAI - Completed database write acceptance evidence [backend/core/database/write_acceptance.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from core.database.operation_status import DatabaseOperationStatusValue
from core.errors.exceptions import SoAIError
from core.state.errors import DatabaseWriteAcceptanceUnresolvedError

if TYPE_CHECKING:
    from core.database.protocols import DatabaseOperationStatusProtocol

__all__ = ("completed_write_outcome",)


async def completed_write_outcome[Result](
    task: asyncio.Task[Result], status_owner: DatabaseOperationStatusProtocol
) -> DatabaseOperationStatusValue:
    if not task.done() or task.cancelled():
        raise DatabaseWriteAcceptanceUnresolvedError(
            "Database acceptance has no completed writer evidence."
        )
    exception = task.exception()
    if exception is None:
        return DatabaseOperationStatusValue.COMMITTED
    if isinstance(exception, SoAIError):
        operation_id = (exception.headers or {}).get("X-SoAI-Operation-Id")
        if isinstance(operation_id, str) and operation_id:
            outcome = (await status_owner.resolve(operation_id)).status
            if outcome in {
                DatabaseOperationStatusValue.COMMITTED,
                DatabaseOperationStatusValue.FAILED,
                DatabaseOperationStatusValue.SKIPPED,
                DatabaseOperationStatusValue.NOT_COMMITTED,
            }:
                return outcome
            raise DatabaseWriteAcceptanceUnresolvedError(
                "Database acceptance is not resolved.",
                details={
                    "operation_id": operation_id,
                    "status": outcome.value,
                    "status_url": f"/api/v1/system/database/operations/{operation_id}",
                    "retry_guidance": "check_status_before_retry",
                },
            )
    raise DatabaseWriteAcceptanceUnresolvedError(
        "Database acceptance has no operation correlation.", cause=exception
    )
