"""SoAI - Shared WebSocket OpenAI result collection [backend/features/api/routes/system/events/websocket_openai_result_collection.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import TYPE_CHECKING

from core.errors.exceptions import ApiError, ValidationError
from core.errors.status_mapping import error_type_to_status_code
from core.events.inference_terminal_handlers import build_inference_terminal_handlers
from core.events.non_streaming_hard_deadline import (
    TerminalEventHandler,
    run_inactivity_timeout_event_loop,
)
from core.events.types_base import Event, PayloadEvent
from core.events.types_models_streaming import InferenceResultEvent
from core.events.types_plugins import ErrorEvent
from core.events.types_tasks import TaskCompleteEvent
from core.tasks.enums import TaskStatus
from core.tasks.finalization import finalize

if TYPE_CHECKING:
    from core.tasks.protocols import TaskRegistryProtocol
    from core.types.json import JSONDict, JSONValue

__all__ = ("collect_openai_ws_result",)


async def _finalize_openai_ws_result(
    *,
    registry: TaskRegistryProtocol | None,
    task_id: str | None,
    status: TaskStatus,
    result: JSONDict | None = None,
    error_code: int | None = None,
    error_type: str | None = None,
    error_message: str | None = None,
) -> None:
    if registry is None or task_id is None:
        return
    await finalize(
        registry,
        task_id,
        status,
        result=result,
        error_code=error_code,
        error_type=error_type,
        error_message=error_message,
        status_message="Completed" if status is TaskStatus.COMPLETED else None,
    )


async def collect_openai_ws_result(
    *,
    registry: TaskRegistryProtocol | None,
    task_id: str | None,
    reply_queue: asyncio.Queue[Event],
    timeout_seconds: float,
    timeout_message: str,
    timeout_operation: str,
    include_payload_event: bool,
    finalization_result_builder: Callable[[JSONValue], JSONDict] | None,
) -> JSONValue:
    async def next_event(timeout: float) -> Event:
        return await asyncio.wait_for(reply_queue.get(), timeout=timeout)

    async def handle_payload(event: Event) -> JSONValue:
        if not isinstance(event, PayloadEvent):
            raise ValidationError("Expected PayloadEvent.")
        await _finalize_openai_ws_result(
            registry=registry,
            task_id=task_id,
            status=TaskStatus.COMPLETED,
            result=(
                finalization_result_builder(event.payload)
                if finalization_result_builder is not None
                else None
            ),
        )
        return event.payload

    async def handle_inference_result(event: Event) -> JSONValue:
        if not isinstance(event, InferenceResultEvent):
            raise ValidationError("Expected InferenceResultEvent.")
        await _finalize_openai_ws_result(
            registry=registry,
            task_id=task_id,
            status=TaskStatus.COMPLETED,
            result=(
                finalization_result_builder(event.payload)
                if finalization_result_builder is not None
                else None
            ),
        )
        return event.payload

    async def handle_error(event: Event) -> JSONValue:
        if not isinstance(event, ErrorEvent):
            raise ValidationError("Expected ErrorEvent.")
        message = event.message or "Request failed."
        error_type = event.error_type
        status_code = error_type_to_status_code(error_type)
        await _finalize_openai_ws_result(
            registry=registry,
            task_id=task_id,
            status=TaskStatus.FAILED,
            error_code=status_code,
            error_type=error_type.value,
            error_message=message,
        )
        raise ApiError(message, code=error_type.value, http_status=status_code)

    async def handle_complete(event: Event) -> JSONValue:
        if not isinstance(event, TaskCompleteEvent):
            raise ValidationError("Expected TaskCompleteEvent.")
        if not event.success:
            message = event.error_message or event.message or "Task failed."
            await _finalize_openai_ws_result(
                registry=registry,
                task_id=task_id,
                status=TaskStatus.FAILED,
                error_code=event.error_code or 500,
                error_type=event.error_type,
                error_message=message,
            )
            raise ApiError(
                message,
                code=event.error_type or "server_error",
                http_status=event.error_code or 500,
            )
        result: JSONDict = {"message": event.message} if event.message else {}
        await _finalize_openai_ws_result(
            registry=registry,
            task_id=task_id,
            status=TaskStatus.COMPLETED,
            result=result,
        )
        return result

    terminal_handlers: tuple[TerminalEventHandler[Event, JSONValue], ...] = (
        build_inference_terminal_handlers(
            handle_inference_result=handle_inference_result,
            handle_error=handle_error,
            handle_complete=handle_complete,
        )
    )
    if include_payload_event:
        terminal_handlers = (
            TerminalEventHandler(
                matches=lambda event: isinstance(event, PayloadEvent),
                handler=handle_payload,
            ),
            *terminal_handlers,
        )
    return await run_inactivity_timeout_event_loop(
        inactivity_timeout_seconds=float(timeout_seconds),
        next_event=next_event,
        terminal_handlers=terminal_handlers,
        timeout_message=timeout_message,
        timeout_operation=timeout_operation,
    )
