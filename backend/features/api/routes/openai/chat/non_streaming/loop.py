"""SoAI - Non-streaming inference result loop [backend/features/api/routes/openai/chat/non_streaming/loop.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Literal

from fastapi.responses import JSONResponse

from core.errors.exceptions import ModelOutputContractError
from core.errors.http_status_classification import resolve_openai_error_type_for_http_status
from core.errors.status_mapping import error_type_to_status_code
from core.events.publication_errors import HardDeadlineExceededError
from core.events.types_base import Event
from core.events.types_models_streaming import InferenceResultEvent, StreamChunkEvent
from core.events.types_plugins import ErrorEvent
from core.events.types_tasks import TaskCompleteEvent
from core.logging.trace import get_logger
from core.runtime.request_context import RequestContext
from core.tasks.protocols import TaskRegistryProtocol
from core.tasks.task import Task
from features.api.openai.openai_error_responses import (
    build_openai_error_json_response,
    build_openai_error_json_response_for_status,
)
from features.api.routes.openai.chat.chat_ops import (
    resolve_non_streaming_timeout_from_request_json,
)
from features.api.routes.openai.chat.inference_payload import (
    handle_inference_payload_response,
)
from features.api.routes.openai.chat.non_streaming.event_handlers import (
    cancel_and_return_error,
    handle_client_disconnect,
    handle_shutdown,
    handle_timeout,
)
from features.api.routes.openai.chat.non_streaming.payload_flush import (
    flush_and_handle_stream_end,
    flush_and_handle_task_complete,
)
from features.api.routes.openai.non_streaming_errors import (
    MALFORMED_STREAM_CHUNK_MESSAGE,
)
from features.api.routes.openai.non_streaming_event_loop import (
    run_non_streaming_event_loop,
)
from features.api.runtime.openai_context.internal_protocols import (
    OpenAIApiContextProtocol,
)
from features.api.streaming.non_streaming_sse_reconstructor import (
    NonStreamingSSEMalformedFrameError,
    NonStreamingSSEReconstructor,
)
from features.api.streaming.types import StreamDependencies

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "NonStreamingLoopTerminalResponseError",
    "run_non_streaming_result_loop",
)

LOGGER_NAME = "SoAI.features.api.loop"


class NonStreamingLoopTerminalResponseError(Exception):
    def __init__(self, response: JSONResponse) -> None:
        super().__init__("Non-streaming loop terminated with a prepared response.")
        self.response = response


async def run_non_streaming_result_loop(
    api_context: OpenAIApiContextProtocol,
    *,
    stream_dependencies: StreamDependencies,
    registry: TaskRegistryProtocol,
    task: Task,
    context: RequestContext,
    request_json: JSONDict,
    required_capabilities: tuple[str, ...],
    listener_queue: asyncio.Queue[Event | None],
) -> JSONResponse:
    timeout = resolve_non_streaming_timeout_from_request_json(request_json)
    converter_format: Literal["chat", "completions"] = (
        "completions" if "completions" in (required_capabilities or ()) else "chat"
    )
    allow_image_events = "images" in (required_capabilities or ())
    reconstructor = NonStreamingSSEReconstructor(
        allow_image_events=allow_image_events,
        converter_format=converter_format,
    )

    async def _malformed_stream_response() -> NonStreamingLoopTerminalResponseError:
        return NonStreamingLoopTerminalResponseError(
            await cancel_and_return_error(
                api_context,
                registry=registry,
                task=task,
                context=context,
                status_code=502,
                message=MALFORMED_STREAM_CHUNK_MESSAGE,
                error_type="invalid_stream_error",
            )
        )

    async def _handle_closed_queue() -> JSONResponse:
        if stream_dependencies.shutdown_event.is_set():
            return await handle_shutdown(
                api_context,
                registry=registry,
                task=task,
                context=context,
            )
        api_context.dependencies.metrics_manager.increment_counter(
            "api",
            "openai",
            "requests_failed",
        )
        return build_openai_error_json_response_for_status(
            status_code=503,
            message="Task stream closed before completion.",
            soai_code="service_unavailable",
            param=None,
            trace_id=context.trace_id,
            headers=None,
        )

    async def _handle_stream_chunk(event: StreamChunkEvent) -> None:
        try:
            reconstructor.consume_chunk(
                context=context,
                request_json=request_json,
                chunk=event.chunk,
                buffering_log_label="",
            )
        except ModelOutputContractError as exception:
            raise await _malformed_stream_response() from exception
        except NonStreamingSSEMalformedFrameError as exception:
            raise await _malformed_stream_response() from exception

    async def _handle_unknown_event(event: Event) -> None:
        get_logger(LOGGER_NAME).debug(
            "Non-stream handler ignoring event type: %s",
            type(event).__name__,
        )

    async def _handle_inference_result(event: InferenceResultEvent) -> JSONResponse:
        try:
            reconstructor.finalize()
        except (ModelOutputContractError, NonStreamingSSEMalformedFrameError) as exception:
            raise await _malformed_stream_response() from exception
        return await handle_inference_payload_response(
            api_context,
            context,
            event.payload,
            task,
            response_format=converter_format,
        )

    async def _handle_task_complete(event: TaskCompleteEvent) -> JSONResponse:
        return await flush_and_handle_task_complete(
            api_context,
            context=context,
            reconstructor=reconstructor,
            task=task,
            success=bool(event.success),
            message=str(event.message or ""),
        )

    response: JSONResponse
    try:
        response = await run_non_streaming_event_loop(
            request=None,
            stream_dependencies=stream_dependencies,
            listener_queue=listener_queue,
            task_id=task.task_id,
            timeout=timeout,
            on_stream_chunk=_handle_stream_chunk,
            on_inference_result=_handle_inference_result,
            on_stream_end=lambda _event: flush_and_handle_stream_end(
                api_context,
                context=context,
                reconstructor=reconstructor,
                task=task,
            ),
            on_task_complete=_handle_task_complete,
            on_error_event=_handle_error_event,
            on_closed_queue=_handle_closed_queue,
            on_unknown_event=_handle_unknown_event,
            timeout_message=(
                "Timed out waiting for non-streaming OpenAI result without new task events."
            ),
            timeout_operation="api_openai.chat.non_streaming.loop",
        )
    except HardDeadlineExceededError:
        response = await handle_timeout(
            api_context,
            registry=registry,
            task=task,
            context=context,
            timeout=timeout,
        )
    except asyncio.CancelledError:
        response = await handle_client_disconnect(
            api_context,
            registry=registry,
            task=task,
            context=context,
        )
    except NonStreamingLoopTerminalResponseError as exception:
        response = exception.response
    return response


async def _handle_error_event(event: ErrorEvent) -> JSONResponse:
    status_code = error_type_to_status_code(event.error_type)
    return build_openai_error_json_response(
        status_code=status_code,
        message=event.message,
        canonical_error_type=resolve_openai_error_type_for_http_status(status_code),
        param=None,
        code=event.error_type.value,
        trace_id=event.trace_id,
        headers=None,
        message_is_public=True,
    )
