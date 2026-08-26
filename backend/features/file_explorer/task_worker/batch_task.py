"""SoAI - Shared batch task execution helpers for file explorer workers [backend/features/file_explorer/task_worker/batch_task.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception, log_handled_exception
from core.errors.exceptions import InsufficientDiskSpaceError
from core.errors.public_projection import project_public_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.events.types_file_explorer import FileExplorerOperation
from core.logging.protocols import StandardLogger
from core.tasks.enums import TaskStatus
from core.tasks.finalization import finalize
from core.tasks.protocols import TaskRegistryProtocol
from core.tasks.status_transitions import update_progress
from features.file_explorer.task_worker.cancelled_finalization import (
    finalize_cancelled_batch_task,
)

__all__ = ("run_batch_task",)

OPERATION_FEATURES_FILE_EXPLORER_TASK_WORKER_BATCH_TASK_RUN_BATCH_TASK = (
    "features.file_explorer.task_worker.batch_task.run_batch_task"
)


async def run_batch_task(
    *,
    task_registry: TaskRegistryProtocol,
    logger: StandardLogger,
    task_id: str,
    operation: FileExplorerOperation,
    item_paths: list[str],
    progress_verb: str,
    action_verb: str,
    item_error_operation: str,
    cancel_finalization_operation: str,
    cancel_details: dict[str, str],
    process_item: Callable[[str], Awaitable[None]],
) -> None:
    total = len(item_paths)
    succeeded = 0
    failed = 0
    results: list[dict[str, str | bool]] = []

    try:
        for item_index, item_path in enumerate(item_paths):
            try:
                await process_item(item_path)
                succeeded += 1
                results.append({"path": item_path, "success": True})
            except InsufficientDiskSpaceError as exception:
                log_handled_exception(
                    logger,
                    exception,
                    message=f"Insufficient disk space while attempting to {action_verb} {item_path}",
                    operation=OPERATION_FEATURES_FILE_EXPLORER_TASK_WORKER_BATCH_TASK_RUN_BATCH_TASK,
                    details={
                        "path": item_path,
                        "operation": item_error_operation,
                        **(dict(exception.details or {})),
                    },
                    level="warning",
                )
                failed += 1
                results.append(
                    {
                        "path": item_path,
                        "success": False,
                        "error": "Insufficient disk space.",
                    }
                )
                await finalize(
                    task_registry,
                    task_id,
                    TaskStatus.FAILED,
                    error_code=exception.http_status,
                    error_message=str(exception.message),
                    result={
                        "total": total,
                        "succeeded": succeeded,
                        "failed": failed,
                        "items": results,
                    },
                    status_message=str(exception.message),
                )
                return
            except RECOVERABLE_EXCEPTIONS as exception:
                log_exception(
                    logger,
                    exception,
                    message=f"Failed to {action_verb} {item_path}",
                    operation=OPERATION_FEATURES_FILE_EXPLORER_TASK_WORKER_BATCH_TASK_RUN_BATCH_TASK,
                    details={"path": item_path, "operation": item_error_operation},
                )
                failed += 1
                results.append(
                    {
                        "path": item_path,
                        "success": False,
                        "error": project_public_exception(exception).message,
                    }
                )

            if total > 0:
                await update_progress(
                    task_registry,
                    task_id,
                    int(((item_index + 1) / total) * 100),
                    status_message=f"{progress_verb} entries ({item_index + 1}/{total})...",
                )

        await finalize(
            task_registry,
            task_id,
            TaskStatus.COMPLETED,
            result={
                "total": total,
                "succeeded": succeeded,
                "failed": failed,
                "items": results,
            },
            status_message=f"Batch {operation.value} completed: {succeeded} succeeded, {failed} failed",
        )
    except asyncio.CancelledError:
        await finalize_cancelled_batch_task(
            task_registry,
            task_id,
            total=total,
            succeeded=succeeded,
            failed=failed,
            results=results,
            logger=logger,
            operation=cancel_finalization_operation,
            details=cancel_details,
        )
        return
    except RECOVERABLE_EXCEPTIONS as exception:
        operation_value = str(operation.value)
        if isinstance(exception, InsufficientDiskSpaceError):
            log_handled_exception(
                logger,
                exception,
                message=str(exception.message),
                operation=OPERATION_FEATURES_FILE_EXPLORER_TASK_WORKER_BATCH_TASK_RUN_BATCH_TASK,
                details=dict(exception.details or {}),
                level="warning",
            )
            await finalize(
                task_registry,
                task_id,
                TaskStatus.FAILED,
                error_code=exception.http_status,
                error_message=str(exception.message),
                status_message=str(exception.message),
            )
            return
        coerced = coerce_to_soai_error(
            exception,
            operation=f"file_explorer.{operation_value}_batch",
        )
        log_exception(
            logger,
            coerced,
            message=f"Task {operation_value}_batch failed",
            operation=OPERATION_FEATURES_FILE_EXPLORER_TASK_WORKER_BATCH_TASK_RUN_BATCH_TASK,
        )
        await finalize(
            task_registry,
            task_id,
            TaskStatus.FAILED,
            error_message=coerced.message,
            status_message=f"Error: {coerced.message}",
        )
