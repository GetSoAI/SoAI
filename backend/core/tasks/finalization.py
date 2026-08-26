"""SoAI - Task finalization and completion event delivery [backend/core/tasks/finalization.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import dataclasses
import time
from collections.abc import Mapping
from typing import TYPE_CHECKING

from core.concurrency.cancellation_cleanup import uncancel_then_cleanup
from core.database.task_requests import UnifiedTaskFinalizationWriteResult
from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.exceptions import ConcurrencyError, ValidationError
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from core.logging.trace import get_logger
from core.serialization.json import serialize_json_compact_stable
from core.tasks.enums import TaskStatus
from core.tasks.errors import TaskFinalizationPersistenceError
from core.tasks.finalization_notifications import publish_terminal_notifications
from core.tasks.protocols import TaskRegistryLifecycleView
from core.tasks.status_policy import TERMINAL_TASK_STATUS_VALUES
from core.tasks.task import Task
from core.tasks.task_lock_control import load_task_with_drop_control, task_lock_control
from core.tasks.task_registry_cache import resolve_cached_task_locked
from core.tasks.task_state_merge import merge_task_state
from core.types.json_value import copy_json_value, filter_json_mapping_strict

if TYPE_CHECKING:
    from core.logging.protocols import LoggerProtocol
    from core.tasks.interaction_mutations import ConversationInteractionMutation
    from core.types.json import JSONValue

__all__ = ("finalize",)

LOGGER_NAME_TASKS_REGISTRY_LIFECYCLE = "SoAI.core.tasks.registry_lifecycle"
OPERATION_DROP_TASK_LOCK = "core.tasks.finalization.drop_task_lock"
OPERATION_SIGNAL_COMPLETION = "core.tasks.finalization.signal_completion"


async def finalize(
    registry: TaskRegistryLifecycleView,
    task_id: str,
    status: TaskStatus,
    *,
    prefetched_task: Task | None = None,
    result: Mapping[str, JSONValue] | None = None,
    error_code: int | None = None,
    error_type: str | None = None,
    error_message: str | None = None,
    status_message: str | None = None,
    emit_reply_completion_event: bool = True,
    delivery_version: int | None = None,
    mutation_fencing_token: int | None = None,
    interaction_mutation: ConversationInteractionMutation | None = None,
) -> Task | None:
    return await uncancel_then_cleanup(
        _finalize(
            registry,
            task_id,
            status,
            prefetched_task=prefetched_task,
            result=result,
            error_code=error_code,
            error_type=error_type,
            error_message=error_message,
            status_message=status_message,
            emit_reply_completion_event=emit_reply_completion_event,
            delivery_version=delivery_version,
            mutation_fencing_token=mutation_fencing_token,
            interaction_mutation=interaction_mutation,
        ),
    )


async def _finalize(
    registry: TaskRegistryLifecycleView,
    task_id: str,
    status: TaskStatus,
    *,
    prefetched_task: Task | None,
    result: Mapping[str, JSONValue] | None,
    error_code: int | None,
    error_type: str | None,
    error_message: str | None,
    status_message: str | None,
    emit_reply_completion_event: bool,
    delivery_version: int | None,
    mutation_fencing_token: int | None,
    interaction_mutation: ConversationInteractionMutation | None,
) -> Task | None:
    logger = get_logger(LOGGER_NAME_TASKS_REGISTRY_LIFECYCLE)
    if not status.is_terminal():
        raise ValidationError("finalize() requires a terminal TaskStatus.")
    if prefetched_task is not None:
        if not isinstance(prefetched_task, Task):
            raise ValidationError("prefetched_task must be a Task instance or None.")
        if prefetched_task.task_id != task_id:
            raise ValidationError("prefetched_task.task_id must match task_id.")
    result_task: Task | None = None
    notification_task: Task | None = None
    old_status: TaskStatus | None = None
    final_message = ""
    reply_queue = None
    async with task_lock_control(registry, task_id) as lock_control:
        if prefetched_task is None:
            task = await load_task_with_drop_control(registry, lock_control, task_id)
        else:
            task = await _load_task_for_finalization(
                registry,
                task_id,
                prefetched_task=prefetched_task,
            )
            if task is None:
                lock_control.request_drop_after_exit()
                return None
            if task.status.is_terminal():
                lock_control.request_drop_after_exit()
                return task
        if task is None:
            return None
        if task.status.is_terminal():
            return task
        orchestration_context = task.orchestration_context
        if orchestration_context is not None and orchestration_context.delivery_in_progress:
            if delivery_version != orchestration_context.delivery_version:
                raise ConcurrencyError(
                    "Task terminal delivery is owned by another outcome.",
                    details={"task_id": task_id},
                )
        elif delivery_version is not None:
            raise ConcurrencyError(
                "Task terminal delivery claim is no longer active.",
                details={"task_id": task_id},
            )
        old_status = task.status
        reply_queue = task.reply_queue
        if status_message is None:
            if status == TaskStatus.COMPLETED:
                status_message = "Task completed"
            elif status == TaskStatus.CANCELLED:
                status_message = error_message or "Cancelled"
        coerced_result = (
            filter_json_mapping_strict(
                result,
                error_message="Task result must be JSON-compatible.",
            )
            if result is not None
            else None
        )
        normalized_result: dict[str, JSONValue] | None = (
            {key: copy_json_value(value) for key, value in coerced_result.items()}
            if coerced_result is not None
            else None
        )
        write_result = await registry.database_tasks.finalize_unified_task(
            task_id=task_id,
            status=status.value,
            result=(
                serialize_json_compact_stable(coerced_result)
                if coerced_result is not None
                else None
            ),
            error_code=error_code,
            error_type=error_type,
            error_message=error_message,
            status_message=status_message,
            mutation_fencing_token=mutation_fencing_token,
            interaction_mutation=interaction_mutation,
        )
        if not isinstance(write_result, UnifiedTaskFinalizationWriteResult):
            raise TaskFinalizationPersistenceError(
                "Task finalization database returned an invalid result.",
                details={"task_id": task_id},
            )
        if not write_result.updated:
            current_status = write_result.current_status
            if current_status in TERMINAL_TASK_STATUS_VALUES:
                refreshed = await registry.get(task_id, force_refresh=True)
                if refreshed is None or not refreshed.status.is_terminal():
                    raise TaskFinalizationPersistenceError(
                        "Terminal task state could not be reconciled after a competing finalization.",
                        details={"task_id": task_id, "database_status": current_status},
                    )
                await _signal_terminal_completion_noncritical(
                    registry,
                    task_id,
                    logger=logger,
                )
                lock_control.request_drop_after_exit()
                return refreshed
            if current_status is None:
                async with registry.tasks_lock:
                    registry.tasks.pop(task_id, None)
                    registry.terminal_cache.pop(task_id, None)
            raise TaskFinalizationPersistenceError(
                "Task terminal state was not persisted.",
                details={"task_id": task_id, "database_status": current_status},
            )
        completed_at_ms = write_result.completed_at_ms
        if completed_at_ms is None:
            raise TaskFinalizationPersistenceError(
                "Task finalization database omitted the committed timestamp.",
                details={"task_id": task_id},
            )
        task = dataclasses.replace(
            task,
            status=status,
            updated_at_ms=completed_at_ms,
            update_counter=task.update_counter + 1,
            completed_at_ms=completed_at_ms,
            result=normalized_result,
            error_code=error_code,
            error_type=error_type,
            error_message=error_message,
            status_message=status_message,
            progress_current=(
                task.progress_total if task.progress_total is not None else task.progress_current
            ),
        )
        final_message = (status_message or error_message or "").strip()
        if not final_message:
            final_message = (
                "Task completed" if status == TaskStatus.COMPLETED else f"Task {status.value}"
            )
        if task.is_progress_trackable():
            registry.try_log_terminal_progress(task, old_status=old_status)
        notification_task = task
        task = notification_task.snapshot()
        async with registry.tasks_lock:
            registry.tasks.pop(task_id, None)
            registry.terminal_cache[task_id] = (task, time.monotonic())
        await _signal_terminal_completion_noncritical(registry, task_id, logger=logger)
        result_task = task
    try:
        await registry.drop_task_lock(task_id)
    except HANDLED_RUNTIME_EXCEPTIONS as exception:
        coerced = coerce_to_soai_error(
            exception,
            operation=OPERATION_DROP_TASK_LOCK,
        )
        log_exception(
            logger,
            coerced,
            message="Failed to evict terminal task lock.",
            operation=OPERATION_DROP_TASK_LOCK,
            details={"task_id": task_id},
            level="warning",
        )
    if notification_task is not None and old_status is not None:
        await publish_terminal_notifications(
            registry,
            notification_task,
            old_status=old_status,
            final_message=final_message,
            reply_queue=reply_queue,
            emit_reply_completion_event=emit_reply_completion_event,
        )
    return result_task


async def _load_task_for_finalization(
    registry: TaskRegistryLifecycleView,
    task_id: str,
    *,
    prefetched_task: Task,
) -> Task | None:
    now = time.monotonic()
    async with registry.tasks_lock:
        cached = resolve_cached_task_locked(registry, task_id, now=now)
    return merge_task_state(cached=cached, incoming=prefetched_task)


async def _signal_terminal_completion_noncritical(
    registry: TaskRegistryLifecycleView,
    task_id: str,
    *,
    logger: LoggerProtocol,
) -> None:
    try:
        await registry.ensure_completion_event(task_id, set_if_terminal=True)
    except HANDLED_RUNTIME_EXCEPTIONS as exception:
        coerced = coerce_to_soai_error(
            exception,
            operation=OPERATION_SIGNAL_COMPLETION,
        )
        log_exception(
            logger,
            coerced,
            message="Failed to signal terminal task completion.",
            operation=OPERATION_SIGNAL_COMPLETION,
            details={"task_id": task_id},
            level="warning",
        )
