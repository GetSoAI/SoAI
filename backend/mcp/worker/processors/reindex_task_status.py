"""SoAI - RAG reindex task status updates [backend/mcp/worker/processors/reindex_task_status.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exception_logging import log_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger
from core.tasks.enums import TaskStatus
from core.tasks.status_transitions import update_status

if TYPE_CHECKING:
    from mcp.worker.internal_protocols import MCPWorkerProtocol

__all__ = ("update_reindex_initial_status",)

LOGGER_NAME = "SoAI.mcp.worker.reindex_task_status"
OPERATION = "mcp.worker.process_reindex.update_status"


async def update_reindex_initial_status(worker: MCPWorkerProtocol, task_id: str) -> None:
    logger = get_logger(LOGGER_NAME)
    try:
        await update_status(
            worker.task_registry,
            task_id,
            TaskStatus.WORKING,
            status_message="Reindexing conversation...",
        )
    except RECOVERABLE_EXCEPTIONS as status_error:
        log_exception(
            logger,
            status_error,
            message="Failed to update task status for reindex.",
            operation=OPERATION,
            details={"task_id": task_id},
            level="warning",
        )
