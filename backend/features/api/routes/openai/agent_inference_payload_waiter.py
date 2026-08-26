"""SoAI - Agent inference payload awaiting helpers [backend/features/api/routes/openai/agent_inference_payload_waiter.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Literal

from core.errors.exception_logging import log_handled_exception
from core.errors.exceptions import ModelOutputContractError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.events.publication_errors import HardDeadlineExceededError
from core.events.types_base import Event
from core.events.types_models_streaming import (
    InferenceResultEvent,
    StreamChunkEvent,
    StreamEndEvent,
)
from core.events.types_tasks import TaskCompleteEvent
from core.logging.trace import get_logger
from core.runtime.protocols import RequestProtocol
from core.runtime.request_context import RequestContext
from core.tasks.task_cancellation import cancel
from features.api.routes.openai.non_streaming_errors import (
    raise_malformed_stream_chunk_error,
    raise_task_completed_without_result,
    raise_task_succeeded_without_payload,
    raise_task_timeout_error,
)
from features.api.routes.openai.non_streaming_event_loop import (
    run_non_streaming_event_loop,
)
from features.api.streaming.non_streaming_sse_reconstructor import (
    NonStreamingSSEMalformedFrameError,
    NonStreamingSSEReconstructor,
)
from features.api.streaming.types import StreamDependencies

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("await_agent_inference_payload",)

LOGGER_NAME = "SoAI.features.api.agent_inference_payload_waiter"
OPERATION = "api_openai.agent_inference_payload_waiter.cancel_task"


async def await_agent_inference_payload(
    request: RequestProtocol,
    stream_dependencies: StreamDependencies,
    context: RequestContext,
    request_json: JSONDict,
    reply_queue: asyncio.Queue[Event],
    task_id: str,
    timeout: float,
    *,
    allow_image_events: bool,
    converter_format: Literal["chat", "completions"],
) -> JSONDict:
    reconstructor = NonStreamingSSEReconstructor(
        allow_image_events=allow_image_events,
        converter_format=converter_format,
    )

    async def _cancel_task_noncritical(reason: str) -> None:
        try:
            await cancel(
                stream_dependencies.task_registry,
                task_id,
                reason=reason,
                context=context,
            )
        except RECOVERABLE_EXCEPTIONS as exception:
            log_handled_exception(
                get_logger(LOGGER_NAME),
                exception,
                message=(
                    "Failed to cancel agent inference task after non-streaming stream "
                    "error (non-critical)."
                ),
                trace_id=context.trace_id,
                operation=OPERATION,
                level="debug",
            )

    async def _on_inference_result(result_event: InferenceResultEvent) -> JSONDict:
        await _finalize_reconstructor(
            "Malformed OpenAI SSE frame before agent inference result.",
        )
        return result_event.payload

    async def _on_stream_chunk(result_event: StreamChunkEvent) -> None:
        try:
            reconstructor.consume_chunk(
                context=context,
                request_json=request_json,
                chunk=result_event.chunk,
                buffering_log_label="(agent loop)",
            )
        except NonStreamingSSEMalformedFrameError as exception:
            await _cancel_task_noncritical(
                "Malformed OpenAI SSE frame in non-streaming agent loop.",
            )
            logger = get_logger(LOGGER_NAME)
            logger.warning(
                "[%s] Malformed OpenAI SSE frame in agent non-streaming buffering: %s",
                context.trace_id,
                exception.frame_preview,
            )
            raise_malformed_stream_chunk_error(request)
        except ModelOutputContractError:
            await _cancel_task_noncritical(
                "Invalid OpenAI SSE byte stream in non-streaming agent loop.",
            )
            raise_malformed_stream_chunk_error(request)

    async def _finalize_reconstructor(reason: str) -> JSONDict | None:
        try:
            return reconstructor.finalize()
        except (ModelOutputContractError, NonStreamingSSEMalformedFrameError):
            await _cancel_task_noncritical(reason)
            raise_malformed_stream_chunk_error(request)

    async def _on_stream_end(_result_event: StreamEndEvent) -> JSONDict:
        result_payload = await _finalize_reconstructor(
            "Malformed OpenAI SSE frame in agent loop finalization.",
        )
        if result_payload is not None:
            return result_payload
        raise_task_succeeded_without_payload(request)

    async def _on_task_complete(result_event: TaskCompleteEvent) -> JSONDict:
        result_payload = await _finalize_reconstructor(
            "Malformed OpenAI SSE frame on agent task complete.",
        )
        if result_payload is not None:
            return result_payload
        if result_event.success:
            raise_task_succeeded_without_payload(request)
        raise_task_completed_without_result(request, result_event.message)

    async def _on_unknown_event(result_event: Event) -> None:
        get_logger(LOGGER_NAME).debug(
            "Agent loop ignoring event type: %s",
            type(result_event).__name__,
        )

    try:
        return await run_non_streaming_event_loop(
            request=request,
            stream_dependencies=stream_dependencies,
            task_id=task_id,
            reply_queue=reply_queue,
            timeout=timeout,
            on_stream_chunk=_on_stream_chunk,
            on_inference_result=_on_inference_result,
            on_task_complete=_on_task_complete,
            on_stream_end=_on_stream_end,
            on_unknown_event=_on_unknown_event,
        )
    except HardDeadlineExceededError:
        await _cancel_task_noncritical(f"Timed out after {timeout} seconds.")
        raise_task_timeout_error(request, timeout)
