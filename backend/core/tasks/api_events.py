"""SoAI - Task API event emission helpers [backend/core/tasks/api_events.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from core.errors.exceptions import StateError
from core.events.types_base import Event
from core.events.types_tasks import TaskCompleteEvent, TaskProgressEvent
from core.progress.percent import clamp_percent
from core.progress.transfer_details import resolve_transfer_details_payload
from core.tasks.enums import TaskStatus
from core.tasks.finalization import finalize
from core.tasks.progress_details import serialize_progress_details
from core.tasks.protocols import TaskRegistryLifecycleView
from core.tasks.status_transitions import update_progress
from core.tasks.task_cancellation import cancel
from core.tasks.task_public_fields import resolve_public_task_terminal_fields
from core.types.json import is_json_value

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "send_task_complete_event",
    "send_task_progress_event",
)


async def send_task_progress_event(
    reply_channel: asyncio.Queue[Event] | None,
    *,
    registry: TaskRegistryLifecycleView | None,
    percent: int,
    message: str,
    details: JSONValue | None = None,
    task_id: str | None = None,
    user_id: int | None = None,
) -> TaskProgressEvent | None:
    if registry is None:
        raise StateError("Task registry is required.")
    if task_id is None and reply_channel is not None:
        identity = registry.resolve_task_identity_for_reply_queue(reply_channel)
        if identity is not None:
            task_id, bound_user_id = identity
            if user_id is None:
                user_id = bound_user_id
    try:
        normalized_percent = int(percent)
    except (TypeError, ValueError):
        normalized_percent = 0
    normalized_percent = clamp_percent(normalized_percent)
    if task_id is None:
        raise StateError(
            "send_task_progress_event requires a task_id (or a reply_channel bound to a unified task).",
        )
    details_payload = resolve_transfer_details_payload(details) if is_json_value(details) else None
    updated_task = await update_progress(
        registry,
        task_id,
        normalized_percent,
        status_message=message,
        details=details_payload,
        percent_override=normalized_percent,
    )
    if updated_task is None:
        return None
    event_percent = (
        updated_task.progress_current
        if updated_task.progress_current is not None
        else normalized_percent
    )
    stale_progress = normalized_percent < event_percent
    event_message = updated_task.status_message or ""
    if stale_progress:
        event_details = updated_task.progress_details or ""
    else:
        event_details = serialize_progress_details(details_payload)
    event = TaskProgressEvent(
        percent=clamp_percent(event_percent),
        message=event_message,
        details=event_details,
        task_id=task_id,
        user_id=user_id if user_id is not None else updated_task.user_id,
    )
    return event


async def send_task_complete_event(
    reply_channel: asyncio.Queue[Event] | None,
    message: str,
    *,
    registry: TaskRegistryLifecycleView | None,
    success: bool = True,
    task_id: str | None = None,
    user_id: int | None = None,
    result: JSONDict | None = None,
    cancelled: bool = False,
    error_code: int | None = None,
    error_type: str | None = None,
    error_message: str | None = None,
    mutation_fencing_token: int | None = None,
) -> TaskCompleteEvent | None:
    if registry is None:
        raise StateError("Task registry is required.")
    if task_id is None and reply_channel is not None:
        identity = registry.resolve_task_identity_for_reply_queue(reply_channel)
        if identity is not None:
            task_id, bound_user_id = identity
            if user_id is None:
                user_id = bound_user_id
    if task_id is None:
        raise StateError(
            "send_task_complete_event requires a task_id (or a reply_channel bound to a unified task).",
        )
    normalized_message = str(message or "").strip()
    resolved_error_code: int | None = None
    expected_status: TaskStatus
    if cancelled:
        expected_status = TaskStatus.CANCELLED
        terminal_task = await cancel(
            registry,
            task_id,
            reason=normalized_message or "Operation cancelled",
            mutation_fencing_token=mutation_fencing_token,
        )
    elif success:
        expected_status = TaskStatus.COMPLETED
        completion_result = dict(result) if isinstance(result, dict) else None
        if normalized_message:
            completion_result = completion_result or {}
            completion_result["message"] = normalized_message
        terminal_task = await finalize(
            registry,
            task_id,
            TaskStatus.COMPLETED,
            result=completion_result,
            status_message=normalized_message or None,
            mutation_fencing_token=mutation_fencing_token,
        )
    else:
        expected_status = TaskStatus.FAILED
        resolved_error_code = 500
        if error_code is not None:
            try:
                candidate_code = int(error_code)
            except (TypeError, ValueError):
                candidate_code = 500
            if 100 <= candidate_code <= 599:
                resolved_error_code = candidate_code
        terminal_task = await finalize(
            registry,
            task_id,
            TaskStatus.FAILED,
            error_code=resolved_error_code,
            error_type=error_type,
            error_message=error_message or normalized_message or "Operation failed",
            mutation_fencing_token=mutation_fencing_token,
        )
    if terminal_task is None or terminal_task.status != expected_status:
        return None
    public_terminal_fields = resolve_public_task_terminal_fields(
        status=terminal_task.status,
        error_code=terminal_task.error_code,
        error_type=terminal_task.error_type,
        status_message=terminal_task.status_message,
        error_message=terminal_task.error_message,
    )
    resolved_status = terminal_task.status.value
    event = TaskCompleteEvent(
        success=success,
        message=public_terminal_fields.status_message or message,
        task_id=task_id,
        user_id=user_id if user_id is not None else terminal_task.user_id,
        status=resolved_status,
        error_code=(None if success or cancelled else resolved_error_code),
        error_type=(None if success or cancelled else terminal_task.error_type),
        error_message=(None if success or cancelled else public_terminal_fields.error_message),
    )
    return event
