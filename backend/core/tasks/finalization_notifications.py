"""SoAI - Post-commit task finalization notifications [backend/core/tasks/finalization_notifications.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from core.events.types_tasks import TaskCompleteEvent
from core.logging.trace import get_logger
from core.openai.capability_taxonomy import OpenAIModality
from core.openai.request_requirement_failures import (
    classify_openai_request_requirement_mismatch,
)
from core.tasks.enums import TaskStatus
from core.tasks.finalization_reply_queue import deliver_completion_event_to_reply_queue
from core.tasks.notifications import notify_status_changed, publish_event
from core.tasks.task_public_fields import resolve_public_task_terminal_fields

if TYPE_CHECKING:
    from core.events.types_base import Event
    from core.tasks.protocols import TaskRegistryLifecycleView
    from core.tasks.task import Task

__all__ = ("publish_terminal_notifications",)

LOGGER_NAME_LIFECYCLE = "SoAI.core.tasks.registry_lifecycle"
LOGGER_NAME_PROGRESS = "SoAI.core.tasks.task_registry_progress"
OPERATION_LOG_TERMINAL_PROGRESS = "core.tasks.finalization_notifications.log_terminal_progress"
OPERATION_PUBLISH_TERMINAL_NOTIFICATIONS = (
    "core.tasks.finalization_notifications.publish_terminal_notifications"
)
_AGENT_TOOL_IMAGE_RELAY_REQUESTED_METADATA_KEY = "agent_tool_image_relay_requested"


def _should_log_failure_as_warning(task: Task) -> bool:
    if task.error_code is not None and 400 <= task.error_code < 500:
        return True
    mismatch = classify_openai_request_requirement_mismatch(message=task.error_message)
    if mismatch is None:
        return False
    if task.metadata.get(_AGENT_TOOL_IMAGE_RELAY_REQUESTED_METADATA_KEY) is not True:
        return False
    return (
        OpenAIModality.VISION.value in mismatch.missing_modalities
        or OpenAIModality.VISION.value in mismatch.missing_capabilities
    )


def _log_terminal_progress(task: Task, old_status: TaskStatus, final_message: str) -> None:
    logger = get_logger(LOGGER_NAME_LIFECYCLE)
    progress_logger = get_logger(LOGGER_NAME_PROGRESS)
    if task.is_progress_trackable():
        return
    log_line = f"[Task/{task.task_type}] {final_message} ({task.task_id})"
    try:
        if task.status == TaskStatus.FAILED:
            if _should_log_failure_as_warning(task):
                progress_logger.warning(log_line)
            else:
                progress_logger.error(log_line)
        else:
            progress_logger.info(log_line)
    except HANDLED_RUNTIME_EXCEPTIONS as exception:
        coerced = coerce_to_soai_error(
            exception,
            operation=OPERATION_LOG_TERMINAL_PROGRESS,
        )
        log_exception(
            logger,
            coerced,
            message="Failed to log task finalization.",
            operation=OPERATION_LOG_TERMINAL_PROGRESS,
            details={"task_id": task.task_id},
            level="warning",
        )
    logger.debug(
        "Finalized task %s: %s -> %s",
        task.task_id,
        old_status.value,
        task.status.value,
    )


async def publish_terminal_notifications(
    registry: TaskRegistryLifecycleView,
    task: Task,
    *,
    old_status: TaskStatus,
    final_message: str,
    reply_queue: asyncio.Queue[Event] | None,
    emit_reply_completion_event: bool,
) -> None:
    logger = get_logger(LOGGER_NAME_LIFECYCLE)
    try:
        _log_terminal_progress(task, old_status, final_message)
        await notify_status_changed(registry.event_bus, task, old_status)
        public_terminal_fields = resolve_public_task_terminal_fields(
            status=task.status,
            error_code=task.error_code,
            error_type=task.error_type,
            status_message=task.status_message,
            error_message=task.error_message,
        )
        completion_event = TaskCompleteEvent(
            success=task.status == TaskStatus.COMPLETED,
            message=public_terminal_fields.status_message or final_message,
            task_id=task.task_id,
            user_id=task.user_id,
            status=task.status.value,
            error_code=task.error_code,
            error_type=task.error_type,
            error_message=public_terminal_fields.error_message,
        )
        await publish_event(registry.event_bus, completion_event, "TaskCompleteEvent")
        if reply_queue is not None and emit_reply_completion_event:
            await deliver_completion_event_to_reply_queue(
                logger=logger,
                task=task,
                completion_event=completion_event,
            )
    except HANDLED_RUNTIME_EXCEPTIONS as exception:
        coerced = coerce_to_soai_error(
            exception,
            operation=OPERATION_PUBLISH_TERMINAL_NOTIFICATIONS,
        )
        log_exception(
            logger,
            coerced,
            message="Post-commit terminal task notifications failed.",
            operation=OPERATION_PUBLISH_TERMINAL_NOTIFICATIONS,
            details={"task_id": task.task_id},
            level="warning",
        )
