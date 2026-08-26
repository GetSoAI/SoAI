"""SoAI - MCP inference result waiting from streaming reply queue [backend/mcp/registry/inference_result_waiter.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from core.concurrency.deadlines import deadline_after
from core.config.numeric import coerce_positive_float
from core.errors.exception_logging import log_handled_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.errors.status_mapping import error_type_to_status_code
from core.events.non_streaming_hard_deadline import (
    ProgressEventHandler,
    TerminalEventHandler,
    run_hard_deadline_event_loop,
)
from core.events.publication_errors import HardDeadlineExceededError
from core.events.types_base import Event
from core.events.types_models_streaming import (
    InferenceResultEvent,
    StreamChunkEvent,
    StreamEndEvent,
)
from core.events.types_plugins import ErrorEvent
from core.logging.protocols import LoggerProtocol
from core.openai.stream_transcript.transcript import OpenAIStreamTranscript
from core.runtime.request_context import RequestContext
from core.tasks.task_cancellation import cancel
from mcp.protocol.types import MCPJSONRPCError
from mcp.registry.inference_task_failures import (
    finalize_inference_task_failed_noncritical,
)

if TYPE_CHECKING:
    from core.mcp.protocols_main import MCPServerProtocol
    from core.tasks.protocols import TaskRegistryProtocol
    from core.types.json import JSONDict, JSONValue

__all__ = ("await_inference_result_from_queue",)

OPERATION = "mcp.registry.inference.cancel_after_timeout"


async def await_inference_result_from_queue(
    *,
    manager: MCPServerProtocol,
    payload: JSONDict,
    reply_queue: asyncio.Queue[Event],
    task_id: str,
    context: RequestContext,
    logger: LoggerProtocol,
    trace_id: str | None,
) -> JSONValue:
    task_registry = manager.task_registry
    model_hint = payload.get("model")
    stream_transcript = OpenAIStreamTranscript(
        model_hint=model_hint if isinstance(model_hint, str) else None,
    )
    timeout = coerce_positive_float(
        manager.config.get("TOOLS.MCP.HOST_MODE.SAMPLING.INFERENCE_TIMEOUT_SEC", 300),
        default=300.0,
        minimum=1.0,
    )
    deadline = deadline_after(timeout)
    received_stream_chunk_ref = [False]

    async def next_event(remaining: float) -> Event:
        return await asyncio.wait_for(reply_queue.get(), timeout=remaining)

    try:
        return await run_hard_deadline_event_loop(
            deadline_monotonic=deadline.deadline_monotonic,
            next_event=next_event,
            terminal_handlers=(
                TerminalEventHandler(
                    matches=lambda event: isinstance(event, ErrorEvent),
                    handler=lambda event: _handle_error_reply_event(
                        event,
                        task_registry=task_registry,
                        task_id=task_id,
                        logger=logger,
                        trace_id=trace_id,
                    ),
                ),
                TerminalEventHandler(
                    matches=lambda event: isinstance(event, InferenceResultEvent),
                    handler=lambda event: _return_inference_payload_event(
                        event,
                        received_stream_chunk=received_stream_chunk_ref[0],
                        stream_transcript=stream_transcript,
                    ),
                ),
                TerminalEventHandler(
                    matches=lambda event: isinstance(event, StreamEndEvent),
                    handler=lambda event: _handle_stream_end_event(
                        event,
                        received_stream_chunk=received_stream_chunk_ref[0],
                        stream_transcript=stream_transcript,
                    ),
                ),
            ),
            progress_handlers=(
                ProgressEventHandler(
                    matches=lambda event: isinstance(event, StreamChunkEvent),
                    handler=lambda event: _consume_stream_chunk_event(
                        event,
                        stream_transcript=stream_transcript,
                        received_stream_chunk_ref=received_stream_chunk_ref,
                    ),
                ),
            ),
            timeout_message=f"Inference request timed out after {timeout} seconds",
            timeout_operation="mcp.registry.inference.await_inference_result_from_queue",
        )
    except HardDeadlineExceededError as exception:
        try:
            await cancel(
                task_registry,
                task_id,
                reason=f"Inference request timed out after {timeout} seconds",
                context=context,
            )
        except RECOVERABLE_EXCEPTIONS as cancel_exception:
            log_handled_exception(
                logger,
                cancel_exception,
                message="Failed to cancel MCP inference task after timeout (non-critical).",
                trace_id=trace_id,
                operation=OPERATION,
                details={"task_id": task_id},
                level="debug",
            )
        raise MCPJSONRPCError(
            -32603,
            f"Inference request timed out after {timeout} seconds",
        ) from exception


async def _handle_error_reply(
    event: ErrorEvent,
    *,
    task_registry: TaskRegistryProtocol,
    task_id: str,
    logger: LoggerProtocol,
    trace_id: str | None,
) -> JSONValue:
    error_code = (
        error_type_to_status_code(event.error_type) if event.error_type is not None else 500
    )
    await finalize_inference_task_failed_noncritical(
        task_registry=task_registry,
        task_id=task_id,
        error_code=error_code,
        error_message=event.message[:500] if event.message else "Error",
        logger=logger,
        trace_id=trace_id,
        operation="mcp.registry.inference.finalize_after_error_event",
    )
    raise MCPJSONRPCError(-32603, event.message)


async def _handle_error_reply_event(
    event: Event,
    *,
    task_registry: TaskRegistryProtocol,
    task_id: str,
    logger: LoggerProtocol,
    trace_id: str | None,
) -> JSONValue:
    if not isinstance(event, ErrorEvent):
        raise MCPJSONRPCError(-32603, "Unexpected inference event type")
    return await _handle_error_reply(
        event,
        task_registry=task_registry,
        task_id=task_id,
        logger=logger,
        trace_id=trace_id,
    )


async def _return_inference_payload(event: InferenceResultEvent) -> JSONValue:
    return event.payload


async def _return_inference_payload_event(
    event: Event,
    *,
    received_stream_chunk: bool,
    stream_transcript: OpenAIStreamTranscript,
) -> JSONValue:
    if not isinstance(event, InferenceResultEvent):
        raise MCPJSONRPCError(-32603, "Unexpected inference event type")
    if received_stream_chunk:
        stream_transcript.finalize()
    return await _return_inference_payload(event)


async def _consume_stream_chunk(
    event: StreamChunkEvent,
    *,
    stream_transcript: OpenAIStreamTranscript,
    received_stream_chunk_ref: list[bool],
) -> None:
    received_stream_chunk_ref[0] = True
    stream_transcript.feed(event.chunk)


async def _consume_stream_chunk_event(
    event: Event,
    *,
    stream_transcript: OpenAIStreamTranscript,
    received_stream_chunk_ref: list[bool],
) -> None:
    if not isinstance(event, StreamChunkEvent):
        raise MCPJSONRPCError(-32603, "Unexpected inference event type")
    await _consume_stream_chunk(
        event,
        stream_transcript=stream_transcript,
        received_stream_chunk_ref=received_stream_chunk_ref,
    )


async def _handle_stream_end(
    event: StreamEndEvent,
    *,
    received_stream_chunk: bool,
    stream_transcript: OpenAIStreamTranscript,
) -> JSONValue:
    if received_stream_chunk:
        stream_transcript.finalize()
        converted_result = stream_transcript.build_result_payload()
        if isinstance(event.usage, dict):
            converted_result["usage"] = event.usage
        return converted_result
    raise MCPJSONRPCError(-32603, "No response received from inference engine")


async def _handle_stream_end_event(
    event: Event,
    *,
    received_stream_chunk: bool,
    stream_transcript: OpenAIStreamTranscript,
) -> JSONValue:
    if not isinstance(event, StreamEndEvent):
        raise MCPJSONRPCError(-32603, "Unexpected inference event type")
    return await _handle_stream_end(
        event,
        received_stream_chunk=received_stream_chunk,
        stream_transcript=stream_transcript,
    )
