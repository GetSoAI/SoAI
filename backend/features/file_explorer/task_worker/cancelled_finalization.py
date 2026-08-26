"""SoAI - File explorer batch task cancelled finalization [backend/features/file_explorer/task_worker/cancelled_finalization.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.concurrency.cancellation_cleanup import shielded_cleanup
from core.errors.exception_logging import log_handled_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.protocols import StandardLogger
from core.tasks.enums import TaskStatus
from core.tasks.finalization import finalize
from core.tasks.protocols import TaskRegistryProtocol

__all__ = ("finalize_cancelled_batch_task",)

OPERATION_FEATURES_FILE_EXPLORER_TASK_WORKER_CANCELLED_FINALIZATION_FINALIZE_CANCELLED_BATCH_TASK = (
    "features.file_explorer.task_worker.cancelled_finalization.finalize_cancelled_batch_task"
)


async def finalize_cancelled_batch_task(
    task_registry: TaskRegistryProtocol,
    task_id: str,
    *,
    total: int,
    succeeded: int,
    failed: int,
    results: list[dict[str, str | bool]],
    logger: StandardLogger,
    operation: str,
    details: dict[str, str],
) -> None:
    try:
        await shielded_cleanup(
            finalize(
                task_registry,
                task_id,
                TaskStatus.CANCELLED,
                result={
                    "total": int(total),
                    "succeeded": int(succeeded),
                    "failed": int(failed),
                    "items": results,
                },
                error_message="Cancelled.",
                status_message="Cancelled.",
            ),
        )
    except RECOVERABLE_EXCEPTIONS as exception:
        resolved_details = dict(details)
        resolved_details["operation"] = operation
        log_handled_exception(
            logger,
            exception,
            message="Failed to finalize cancelled batch task (non-critical).",
            operation=OPERATION_FEATURES_FILE_EXPLORER_TASK_WORKER_CANCELLED_FINALIZATION_FINALIZE_CANCELLED_BATCH_TASK,
            details=resolved_details,
            level="debug",
        )
