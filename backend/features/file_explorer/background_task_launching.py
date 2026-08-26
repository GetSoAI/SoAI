"""SoAI - File explorer background task launching helpers [backend/features/file_explorer/background_task_launching.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import uuid
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from core.concurrency.cancellation_cleanup import uncancel_then_cleanup
from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger
from core.runtime.soai_identifiers import build_soai_id
from core.tasks.asyncio_task_spawner import create_tracked_and_track_task
from core.tasks.creation import create
from core.tasks.enums import TaskStatus
from core.tasks.finalization import finalize
from core.tasks.type_catalog import TaskTypeId

if TYPE_CHECKING:
    from core.tasks.protocols import (
        TaskCancellationBinderProtocol,
        TaskRegistryProtocol,
    )

__all__ = ("start_file_explorer_background_task",)

OPERATION_FEATURES_FILE_EXPLORER_START_BACKGROUND_TASK = (
    "features.file_explorer.task_launcher.start_background_task"
)
LOGGER_NAME = "SoAI.features.file_explorer.background_task_launching"


async def start_file_explorer_background_task(
    *,
    cancellation_binder: TaskCancellationBinderProtocol,
    task_registry: TaskRegistryProtocol,
    track_task: Callable[[asyncio.Task[None]], None],
    task_type: TaskTypeId,
    user_id: int,
    owner_id: str,
    status_message: str,
    task_name_prefix: str,
    metadata_operation: str,
    launch_message: str,
    error_operation: str,
    error_message: str,
    details: dict[str, str | int],
    build_worker: Callable[[str], Awaitable[None]],
    on_task_created: Callable[[str], Awaitable[None]] | None = None,
) -> str:
    logger = get_logger(LOGGER_NAME)
    task = await create(
        task_registry,
        task_type=task_type,
        user_id=user_id,
        owner_id=owner_id,
        owner_type="system",
        cancellation_id=build_soai_id(
            (
                "task",
                "file_explorer",
                metadata_operation,
                owner_id,
                uuid.uuid4().hex[:12],
            ),
        ),
        status_message=status_message,
    )
    task_details: dict[str, str | int] = {
        "task_id": task.task_id,
        **details,
    }
    try:
        if on_task_created is not None:
            await on_task_created(task.task_id)
        worker = build_worker(task.task_id)
        _ = await create_tracked_and_track_task(
            worker,
            cancellation_binder=cancellation_binder,
            cancellation_id=task.cancellation_id,
            owner="file_explorer_op",
            track_task=track_task,
            name=f"{task_name_prefix}{task.task_id}",
            logger=logger,
            metadata={"task_id": task.task_id, "operation": metadata_operation},
        )
    except asyncio.CancelledError:
        await uncancel_then_cleanup(
            finalize(
                task_registry,
                task.task_id,
                TaskStatus.CANCELLED,
                error_message="Task launch was cancelled.",
                status_message="Cancelled.",
            ),
        )
        raise
    except RECOVERABLE_EXCEPTIONS as exception:
        log_exception(
            logger,
            exception,
            message=launch_message,
            operation=OPERATION_FEATURES_FILE_EXPLORER_START_BACKGROUND_TASK,
            details=task_details,
        )
        await finalize(
            task_registry,
            task.task_id,
            TaskStatus.FAILED,
            error_message=error_message,
        )
        raise
    except (AttributeError, KeyError, OSError, RuntimeError, TypeError, ValueError) as exception:
        coerced = coerce_to_soai_error(
            exception,
            operation=error_operation,
        )
        log_exception(
            logger,
            coerced,
            message=launch_message,
            operation=OPERATION_FEATURES_FILE_EXPLORER_START_BACKGROUND_TASK,
            details=task_details,
        )
        await finalize(
            task_registry,
            task.task_id,
            TaskStatus.FAILED,
            error_message=error_message,
        )
        raise
    return task.task_id
