"""SoAI - Task registry cancellation event handlers [backend/tasks/registry/cancellation_handlers.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exception_logging import log_handled_exception
from core.errors.exceptions import ValidationError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.events.types_base import Event
from core.events.types_tasks import CancelTaskCommand
from core.logging.trace import get_logger
from core.tasks.cancellation_commands import cancel_via_registry
from core.tasks.enums import TaskStatus
from core.tasks.finalization import finalize
from core.tasks.protocols import TaskRegistryLifecycleView
from core.tasks.type_catalog import is_orchestrated_inference_task_type
from core.timing.epoch import epoch_ms
from tasks.registry.conversion import task_from_row

__all__ = ("handle_cancel_task_command",)

LOGGER_NAME = "SoAI.tasks.registry.cancellation_handlers"
OPERATION_TASK_REGISTRY_HANDLE_CANCEL_TASK_COMMAND_FINALIZE = (
    "task_registry.handle_cancel_task_command.finalize"
)
OPERATION_TASK_REGISTRY_HANDLE_CANCEL_TASK_COMMAND_TASK_FROM_ROW = (
    "task_registry.handle_cancel_task_command.task_from_row"
)
OPERATION_TASK_REGISTRY_HANDLE_CANCEL_TASK_COMMAND_UPDATE_CANCELLATION_REQUESTED_AT_FOR_CANCELLATION_ID = "task_registry.handle_cancel_task_command.update_cancellation_requested_at_ms_for_cancellation_id"


async def handle_cancel_task_command(
    command: Event,
    *,
    registry: TaskRegistryLifecycleView,
) -> None:
    if not isinstance(command, CancelTaskCommand):
        return
    if registry is None:
        raise ValidationError("Task registry instance is required.")
    logger = get_logger(LOGGER_NAME)
    orchestrated_task_types = frozenset(
        task_type
        for task_type in registry.task_catalog.task_types
        if is_orchestrated_inference_task_type(task_type)
    )
    cancel_args = await cancel_via_registry(
        command,
        registry.cancellation_coordinator,
        registry.cancellation_history,
    )
    if not cancel_args:
        return
    cancellation_id, reason = cancel_args
    normalized_reason = str(reason or "").strip() or "Cancelled"
    cancellation_timestamp = epoch_ms()

    try:
        await registry.database_tasks.update_cancellation_requested_at_ms_for_cancellation_id(
            cancellation_id,
            cancellation_timestamp,
        )
    except RECOVERABLE_EXCEPTIONS as exception:
        log_handled_exception(
            logger,
            exception,
            message="Failed to record cancellation_requested_at_ms during cancellation propagation (non-critical).",
            operation=OPERATION_TASK_REGISTRY_HANDLE_CANCEL_TASK_COMMAND_UPDATE_CANCELLATION_REQUESTED_AT_FOR_CANCELLATION_ID,
            details={"cancellation_id": cancellation_id},
            level="debug",
        )

    after_created_at_ms = 0
    after_task_id = ""
    page_size = 1000
    while True:
        rows = await registry.database_tasks.query_active_tasks_for_cancellation_id(
            cancellation_id,
            after_created_at_ms=after_created_at_ms,
            after_task_id=after_task_id,
            limit=page_size,
        )
        if not rows:
            return
        for row in rows:
            task_id = row.get("task_id")
            if not isinstance(task_id, str) or not task_id:
                continue
            task_type = row.get("task_type")
            if isinstance(task_type, str) and task_type in orchestrated_task_types:
                continue
            try:
                prefetched_task = task_from_row(registry.task_catalog, row)
            except RECOVERABLE_EXCEPTIONS as exception:
                log_handled_exception(
                    logger,
                    exception,
                    message="Failed to load task during cancellation propagation (non-critical).",
                    operation=OPERATION_TASK_REGISTRY_HANDLE_CANCEL_TASK_COMMAND_TASK_FROM_ROW,
                    details={"task_id": task_id, "cancellation_id": cancellation_id},
                    level="debug",
                )
                continue
            try:
                await finalize(
                    registry,
                    task_id,
                    TaskStatus.CANCELLED,
                    error_message=normalized_reason,
                    status_message=normalized_reason,
                    prefetched_task=prefetched_task,
                )
            except RECOVERABLE_EXCEPTIONS as exception:
                log_handled_exception(
                    logger,
                    exception,
                    message="Failed to finalize cancelled task (non-critical).",
                    operation=OPERATION_TASK_REGISTRY_HANDLE_CANCEL_TASK_COMMAND_FINALIZE,
                    details={"task_id": task_id, "cancellation_id": cancellation_id},
                    level="debug",
                )
        last = rows[-1]
        last_task_id = last.get("task_id")
        last_created_at_ms = last.get("created_at_ms")
        if not isinstance(last_task_id, str) or not last_task_id:
            return
        if isinstance(last_created_at_ms, bool):
            logger.warning(
                "Cancellation pagination encountered invalid created_at_ms boolean for task [%s] (cancellation_id=%s).",
                last_task_id,
                cancellation_id,
            )
            return
        if isinstance(last_created_at_ms, int | float | str):
            try:
                after_created_at_ms = int(last_created_at_ms or 0)
            except (TypeError, ValueError):
                return
        else:
            return
        after_task_id = last_task_id
