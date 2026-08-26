"""SoAI - API command response collection and serialization [backend/features/api/runtime/response_collection.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from fastapi import Request
from starlette.responses import Response

from core.concurrency.task_groups import QueueEventWaiter
from core.errors.error_types import ErrorType
from core.errors.exceptions import StateError
from core.events.non_streaming_hard_deadline import (
    ProgressEventHandler,
    TerminalEventHandler,
    run_inactivity_timeout_event_loop,
)
from core.events.types_base import Event, PayloadEvent
from core.events.types_models_streaming import InferenceResultEvent
from core.events.types_tasks import TaskCompleteEvent, TaskProgressEvent
from core.logging.trace import get_logger
from core.serialization.json import normalize_for_json
from core.state.command_results import normalize_command_result
from core.tasks.finalization import finalize
from core.tasks.protocols import TaskRegistryProtocol
from features.api.runtime.errors import raise_action_failed, raise_error_type
from features.api.runtime.response_terminal_events import (
    handle_generic_event,
    handle_inference_result_event,
    handle_payload_event,
    handle_task_complete_event,
)
from features.api.runtime.responses import create_json_response_with_task_id
from features.api.streaming.event_payload_mapping import event_to_transport_payload

if TYPE_CHECKING:
    from core.types.json import JSONValue

__all__ = (
    "collect_final_response",
    "process_command_reply",
)

LOGGER_NAME = "SoAI.features.api.response_collection"


def process_command_reply(request: Request, reply_event: Event) -> None:
    view = normalize_command_result(reply_event)
    if view.result_type == "error":
        error_type = view.error_type or ErrorType.SERVER_ERROR
        raise_error_type(request, error_type, view.message or "Command execution failed.")
    elif view.result_type == "task" and view.success is False:
        raise_action_failed(request, view.message or "Command execution failed.")


async def collect_final_response(
    request: Request,
    registry: TaskRegistryProtocol,
    reply_channel: asyncio.Queue[Event],
    task_id: str,
    cmd: Event,
    command_fields: dict[str, JSONValue],
    timeout_value: float,
) -> Response:
    command_type = type(cmd)
    shutdown_event = asyncio.Event()
    waiter = QueueEventWaiter(reply_channel, shutdown_event)

    async def next_event(timeout: float) -> Event:
        event = await waiter.wait(timeout=timeout)
        if event is None:
            raise StateError("Task reply channel closed before completion.")
        return event

    return await run_inactivity_timeout_event_loop(
        inactivity_timeout_seconds=timeout_value,
        next_event=next_event,
        terminal_handlers=(
            TerminalEventHandler(
                matches=lambda event: isinstance(event, TaskCompleteEvent),
                handler=lambda event: handle_task_complete_event(
                    request,
                    event,
                    process_command_reply=process_command_reply,
                    json_response_with_task_id=create_json_response_with_task_id,
                    task_id=task_id,
                ),
            ),
            TerminalEventHandler(
                matches=lambda event: isinstance(event, InferenceResultEvent),
                handler=lambda event: handle_inference_result_event(
                    request,
                    registry,
                    event,
                    process_command_reply=process_command_reply,
                    finalize_task=finalize,
                    json_response_with_task_id=create_json_response_with_task_id,
                    task_id=task_id,
                    command_fields=command_fields,
                ),
            ),
            TerminalEventHandler(
                matches=lambda event: isinstance(event, PayloadEvent),
                handler=lambda event: handle_payload_event(
                    request,
                    registry,
                    event,
                    process_command_reply=process_command_reply,
                    finalize_task=finalize,
                    json_response_with_task_id=create_json_response_with_task_id,
                    task_id=task_id,
                ),
            ),
            TerminalEventHandler(
                matches=lambda event: not isinstance(event, TaskProgressEvent),
                handler=lambda event: handle_generic_event(
                    request,
                    registry,
                    event,
                    process_command_reply=process_command_reply,
                    finalize_task=finalize,
                    normalize_json=normalize_for_json,
                    event_to_transport_payload=event_to_transport_payload,
                    json_response_with_task_id=create_json_response_with_task_id,
                    task_id=task_id,
                ),
            ),
        ),
        progress_handlers=(
            ProgressEventHandler(
                matches=lambda event: isinstance(event, TaskProgressEvent),
                handler=lambda event: _log_task_progress_event(command_type.__name__, event),
            ),
        ),
        cleanup_callbacks=(waiter.cancel,),
        timeout_message=(
            f"Command '{command_type.__name__}' timed out after {timeout_value}s without new task events."
        ),
        timeout_operation="api_runtime.handle_task_command",
    )


async def _log_task_progress_event(command_name: str, event: Event) -> None:
    if not isinstance(event, TaskProgressEvent):
        raise StateError("Expected TaskProgressEvent.")
    await _log_task_progress(command_name, event)


async def _log_task_progress(command_name: str, event: TaskProgressEvent) -> None:
    get_logger(LOGGER_NAME).debug(
        "Received TaskProgressEvent for %s: %s%% %s",
        command_name,
        event.percent,
        event.message,
    )
