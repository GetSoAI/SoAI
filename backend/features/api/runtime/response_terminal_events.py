"""SoAI - API terminal event response handling and finalization [backend/features/api/runtime/response_terminal_events.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.responses import Response

from core.errors.exception_logging import log_exception
from core.errors.exceptions import StateError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.events.types_base import Event, PayloadEvent
from core.events.types_models_streaming import InferenceResultEvent
from core.events.types_tasks import TaskCompleteEvent
from core.logging.trace import get_logger
from core.openai.audio_upload_responses import (
    is_audio_upload_error_response,
    read_audio_upload_error_response,
    resolve_audio_upload_raw_media_type,
)
from core.tasks.enums import TaskStatus
from core.tasks.protocols import TaskRegistryProtocol

if TYPE_CHECKING:
    from core.tasks.task import Task
    from core.types.json import JSONValue

__all__ = (
    "handle_generic_event",
    "handle_inference_result_event",
    "handle_payload_event",
    "handle_task_complete_event",
)

LOGGER_NAME = "SoAI.features.api.response_terminal_events"
OPERATION = "api_runtime.handle_task_command"


async def handle_task_complete_event(
    request: Request,
    event: Event,
    *,
    process_command_reply: Callable[[Request, Event], None],
    json_response_with_task_id: Callable[..., JSONResponse],
    task_id: str,
) -> JSONResponse:
    if not isinstance(event, TaskCompleteEvent):
        raise StateError("Expected TaskCompleteEvent.")
    process_command_reply(request, event)
    return json_response_with_task_id(
        {"status": "success", "message": event.message},
        task_id,
    )


async def handle_inference_result_event(
    request: Request,
    registry: TaskRegistryProtocol,
    event: Event,
    *,
    process_command_reply: Callable[[Request, Event], None],
    finalize_task: Callable[..., Awaitable[Task | None]],
    json_response_with_task_id: Callable[..., JSONResponse],
    task_id: str,
    command_fields: dict[str, JSONValue],
) -> Response:
    if not isinstance(event, InferenceResultEvent):
        raise StateError("Expected InferenceResultEvent.")
    process_command_reply(request, event)
    if is_audio_upload_error_response(event.payload):
        return await _handle_audio_upload_error_response(
            registry,
            event.payload,
            finalize_task=finalize_task,
            task_id=task_id,
        )
    try:
        await finalize_task(
            registry,
            task_id,
            TaskStatus.COMPLETED,
            result={"model": command_fields.get("model")},
            status_message="Completed",
        )
    except RECOVERABLE_EXCEPTIONS as exception:
        log_exception(
            get_logger(LOGGER_NAME),
            exception,
            message="Failed to finalize task after successful inference response",
            operation=OPERATION,
            details={"task_id": task_id},
            level="warning",
        )
    return _response_from_payload(
        event.payload,
        command_fields=command_fields,
        json_response_with_task_id=json_response_with_task_id,
        task_id=task_id,
    )


async def handle_payload_event(
    request: Request,
    registry: TaskRegistryProtocol,
    event: Event,
    *,
    process_command_reply: Callable[[Request, Event], None],
    finalize_task: Callable[..., Awaitable[Task | None]],
    json_response_with_task_id: Callable[..., JSONResponse],
    task_id: str,
) -> Response:
    if not isinstance(event, PayloadEvent):
        raise StateError("Expected PayloadEvent.")
    process_command_reply(request, event)
    if is_audio_upload_error_response(event.payload):
        return await _handle_audio_upload_error_response(
            registry,
            event.payload,
            finalize_task=finalize_task,
            task_id=task_id,
        )
    try:
        await finalize_task(
            registry,
            task_id,
            TaskStatus.COMPLETED,
            result=event.payload,
            status_message="Completed",
        )
    except RECOVERABLE_EXCEPTIONS as exception:
        log_exception(
            get_logger(LOGGER_NAME),
            exception,
            message="Failed to finalize task after successful payload response",
            operation=OPERATION,
            details={"task_id": task_id},
            level="warning",
        )
    return _response_from_payload(
        event.payload,
        json_response_with_task_id=json_response_with_task_id,
        task_id=task_id,
    )


async def _handle_audio_upload_error_response(
    registry: TaskRegistryProtocol,
    payload: JSONValue,
    *,
    finalize_task: Callable[..., Awaitable[Task | None]],
    task_id: str,
) -> JSONResponse:
    status_code, error_payload = read_audio_upload_error_response(payload)
    message_value = error_payload.get("message")
    status_message = message_value if isinstance(message_value, str) else "Request rejected."
    try:
        await finalize_task(
            registry,
            task_id,
            TaskStatus.FAILED,
            result=None,
            status_message=status_message,
            error_code=status_code,
            error_message=status_message,
        )
    except RECOVERABLE_EXCEPTIONS as exception:
        log_exception(
            get_logger(LOGGER_NAME),
            exception,
            message="Failed to finalize task after rejected audio upload response",
            operation=OPERATION,
            details={"task_id": task_id},
            level="warning",
        )
    response = JSONResponse(content={"error": error_payload}, status_code=status_code)
    response.headers["X-SoAI-Task-Id"] = task_id
    return response


def _response_from_payload(
    payload: JSONValue,
    *,
    command_fields: dict[str, JSONValue] | None = None,
    json_response_with_task_id: Callable[..., JSONResponse],
    task_id: str,
) -> Response:
    media_type = _resolve_raw_audio_media_type(command_fields)
    if media_type is not None:
        content = _read_raw_audio_text(payload)
        response = Response(content=content, media_type=media_type)
        response.headers["X-SoAI-Task-Id"] = task_id
        return response
    return json_response_with_task_id(payload, task_id)


def _resolve_raw_audio_media_type(command_fields: dict[str, JSONValue] | None) -> str | None:
    if command_fields is None:
        return None
    response_format = command_fields.get("response_format")
    if not isinstance(response_format, str):
        return None
    normalized = response_format.strip().lower()
    if normalized not in ("text", "srt", "vtt"):
        return None
    return resolve_audio_upload_raw_media_type(normalized)


def _read_raw_audio_text(payload: JSONValue) -> str:
    if not isinstance(payload, dict):
        raise StateError("Raw audio upload response payload must be a JSON object.")
    text_value = payload.get("text")
    if not isinstance(text_value, str):
        raise StateError("Raw audio upload response payload must include text.")
    return text_value


async def handle_generic_event(
    request: Request,
    registry: TaskRegistryProtocol,
    event: Event,
    *,
    process_command_reply: Callable[[Request, Event], None],
    finalize_task: Callable[..., Awaitable[Task | None]],
    normalize_json: Callable[..., JSONValue],
    event_to_transport_payload: Callable[[Event], JSONValue],
    json_response_with_task_id: Callable[..., JSONResponse],
    task_id: str,
) -> JSONResponse:
    process_command_reply(request, event)
    response_payload = normalize_json(event_to_transport_payload(event))
    try:
        await finalize_task(
            registry,
            task_id,
            TaskStatus.COMPLETED,
            result={"response": response_payload},
            status_message="Completed",
        )
    except RECOVERABLE_EXCEPTIONS as exception:
        log_exception(
            get_logger(LOGGER_NAME),
            exception,
            message="Failed to finalize task after successful response",
            operation=OPERATION,
            details={"task_id": task_id},
            level="warning",
        )
    return json_response_with_task_id(response_payload, task_id)
