"""SoAI - Task failure logging and event helpers [backend/core/tasks/failure_events.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from core.concurrency.reply_queue_terminal_delivery import (
    try_deliver_terminal_reply_event,
)
from core.errors.error_types import ErrorType
from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.exceptions import StateError
from core.errors.http_status_classification import resolve_execution_error_type_for_http_status
from core.errors.payload import ErrorPublicPayload
from core.errors.public_projection import project_public_status_error
from core.errors.status_mapping import error_type_to_status_code
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from core.events.types_base import Event
from core.events.types_plugins import ErrorEvent
from core.logging.trace import get_logger
from core.runtime.request_context import RequestContext
from core.tasks.enums import TaskStatus
from core.tasks.finalization import finalize
from core.tasks.protocols import TaskRegistryLifecycleView
from core.tasks.task_public_fields import resolve_public_task_terminal_fields
from core.timing.constants import RESPONSIVE_TIMEOUT_SEC

if TYPE_CHECKING:
    from core.tasks.task import Task

__all__ = (
    "send_error_event",
    "send_error_event_and_finalize",
)

LOGGER_NAME = "SoAI.core.tasks.failure_events"
OPERATION_SEND_ERROR_EVENT = "core.tasks.failure_events.send_error_event"
OPERATION_SEND_ERROR_EVENT_AND_FINALIZE = "core.tasks.failure_events.send_error_event_and_finalize"


def _build_public_error_event(
    *,
    message: str,
    error_type: ErrorType,
    context: RequestContext | None,
    public_error: ErrorPublicPayload | None,
) -> ErrorEvent:
    if public_error is not None:
        return ErrorEvent(
            message=public_error.message,
            error_type=error_type,
            context=context,
            public_error=public_error,
        )
    projected_error = project_public_status_error(
        status_code=error_type_to_status_code(error_type),
        code=error_type.value,
        message=message,
    )
    return ErrorEvent(message=projected_error.message, error_type=error_type, context=context)


def _build_persisted_failure_event(task: Task, *, context: RequestContext | None) -> ErrorEvent:
    public_fields = resolve_public_task_terminal_fields(task)
    message = public_fields.error_message or public_fields.status_message or "Task failed."
    return ErrorEvent(
        message=message,
        error_type=(
            ErrorType.SERVER_ERROR
            if task.error_code is None
            else resolve_execution_error_type_for_http_status(task.error_code)
        ),
        context=context,
        public_error=ErrorPublicPayload(
            code=task.error_type or ErrorType.SERVER_ERROR.value,
            message=message,
            http_status=task.error_code,
        ),
    )


async def send_error_event(
    reply_channel: asyncio.Queue[Event] | None,
    message: str,
    error_type: ErrorType = ErrorType.SERVER_ERROR,
    *,
    context: RequestContext | None = None,
    public_error: ErrorPublicPayload | None = None,
) -> ErrorEvent:
    logger = get_logger(LOGGER_NAME)
    event = _build_public_error_event(
        message=message,
        error_type=error_type,
        context=context,
        public_error=public_error,
    )
    if reply_channel is not None:
        try:
            await try_deliver_terminal_reply_event(
                reply_queue=reply_channel,
                event=event,
                timeout_seconds=RESPONSIVE_TIMEOUT_SEC,
                logger=logger,
                operation=OPERATION_SEND_ERROR_EVENT,
            )
        except HANDLED_RUNTIME_EXCEPTIONS as exception:
            coerced = coerce_to_soai_error(
                exception,
                operation=OPERATION_SEND_ERROR_EVENT,
            )
            log_exception(
                logger,
                coerced,
                message="Failed to deliver error event (non-critical).",
                operation=OPERATION_SEND_ERROR_EVENT,
                level="warning",
            )
    return event


async def send_error_event_and_finalize(
    reply_channel: asyncio.Queue[Event] | None,
    message: str,
    error_type: ErrorType = ErrorType.SERVER_ERROR,
    *,
    registry: TaskRegistryLifecycleView | None,
    context: RequestContext | None = None,
    task_id: str | None = None,
    public_error: ErrorPublicPayload | None = None,
) -> ErrorEvent:
    logger = get_logger(LOGGER_NAME)
    if task_id is None and reply_channel is not None and registry is not None:
        identity = registry.resolve_task_identity_for_reply_queue(reply_channel)
        if identity is not None:
            task_id = identity[0]
    event = _build_public_error_event(
        message=message,
        error_type=error_type,
        context=context,
        public_error=public_error,
    )
    if task_id is not None and registry is not None:
        task = await registry.get(task_id)
        if task is not None and task.status.is_terminal():
            return event
    if task_id:
        if registry is None:
            raise StateError("Task registry is required.")
        attempted_error_code = (
            public_error.http_status
            if public_error is not None and public_error.http_status is not None
            else error_type_to_status_code(error_type)
        )
        attempted_error_type = (
            str(public_error.code) if public_error is not None else error_type.value
        )
        attempted_error_message = (
            public_error.message if public_error is not None else str(message or "")
        )[:500]
        finalized_task = await finalize(
            registry,
            task_id,
            TaskStatus.FAILED,
            error_code=attempted_error_code,
            error_type=attempted_error_type,
            error_message=attempted_error_message,
            public_error=public_error,
            emit_reply_completion_event=False,
            mutation_fencing_token=(
                context.mutation_fencing_token if context is not None else None
            ),
        )
        if finalized_task is None or finalized_task.status != TaskStatus.FAILED:
            return event
        if (
            finalized_task.error_code != attempted_error_code
            or finalized_task.error_type != attempted_error_type
            or (finalized_task.error_message or "").strip() != attempted_error_message.strip()
        ):
            event = _build_persisted_failure_event(finalized_task, context=context)
    if reply_channel is not None:
        try:
            await try_deliver_terminal_reply_event(
                reply_queue=reply_channel,
                event=event,
                timeout_seconds=RESPONSIVE_TIMEOUT_SEC,
                logger=logger,
                operation=OPERATION_SEND_ERROR_EVENT_AND_FINALIZE,
            )
        except HANDLED_RUNTIME_EXCEPTIONS as exception:
            coerced = coerce_to_soai_error(
                exception,
                operation=OPERATION_SEND_ERROR_EVENT_AND_FINALIZE,
            )
            log_exception(
                logger,
                coerced,
                message="Failed to deliver error event (non-critical).",
                operation=OPERATION_SEND_ERROR_EVENT_AND_FINALIZE,
                level="warning",
            )
    return event
