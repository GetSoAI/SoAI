"""SoAI - WebSocket OpenAI speech stream runner [backend/features/api/routes/system/events/websocket_openai_audio/speech_runner.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger
from core.serialization.base64_values import encode_base64_ascii
from features.api.routes.system.events.websocket_openai_audio.payloads import (
    build_openai_audio_speech_chunk,
    build_openai_audio_speech_completed,
    build_openai_audio_speech_error,
)
from features.api.routes.system.events.websocket_openai_runner_failure_handling import (
    openai_ws_detach_event_is_set,
)
from features.api.runtime.event_enqueue import enqueue_correlated_media_event
from features.api.streaming.openai_stream_binary_request_stream import (
    BinaryStreamRuntimeFailure,
    prepare_binary_stream_payload,
)

if TYPE_CHECKING:
    from core.events.types_base import Event
    from core.runtime.request_context import RequestContext
    from features.api.routes.system.events.websocket_openai_audio.runtime import (
        OpenAiAudioSpeechRuntime,
    )
    from features.api.runtime.container.enqueue_warning_tracker import (
        EnqueueWarningTracker,
    )
    from features.api.streaming.types import StreamDependencies
    from features.api.streaming.websocket import WebsocketConnection

__all__ = ("run_openai_audio_speech_stream",)

LOGGER_NAME = "SoAI.features.api.speech_runner"
OPERATION_WS_OPENAI_AUDIO_SPEECH_STREAM = "ws_openai_audio.speech.stream"


async def run_openai_audio_speech_stream(
    *,
    run_id: str,
    runtime: OpenAiAudioSpeechRuntime,
    connection: WebsocketConnection,
    reply_queue: asyncio.Queue[Event],
    stream_dependencies: StreamDependencies,
    request_context: RequestContext,
    enqueue_warning_tracker: EnqueueWarningTracker,
    trace_id: str | None,
    shutdown_event: asyncio.Event,
) -> None:
    logger = get_logger(LOGGER_NAME)
    try:
        prepared = await prepare_binary_stream_payload(
            reply_queue,
            stream_dependencies,
            request_context,
            trace_id=request_context.trace_id,
        )
        if prepared.stream is None:
            message = prepared.error_message or "Speech stream failed."
            await enqueue_correlated_media_event(
                enqueue_warning_tracker,
                connection.queue,
                build_openai_audio_speech_error(
                    run_id=run_id,
                    message=message,
                    code=prepared.error_type or "server_error",
                    task_id=runtime.task_id,
                ),
                shutdown_event,
                "OpenAI audio speech error",
            )
            return
        sequence = 0
        async for chunk in prepared.stream:
            if openai_ws_detach_event_is_set(runtime.detach_event):
                return
            if not chunk:
                continue
            chunk_base64 = encode_base64_ascii(chunk)
            delivered = await enqueue_correlated_media_event(
                enqueue_warning_tracker,
                connection.queue,
                build_openai_audio_speech_chunk(
                    run_id=run_id,
                    sequence=sequence,
                    chunk_base64=chunk_base64,
                ),
                shutdown_event,
                "OpenAI audio speech chunk",
            )
            if not delivered:
                return
            sequence += 1
        await enqueue_correlated_media_event(
            enqueue_warning_tracker,
            connection.queue,
            build_openai_audio_speech_completed(
                run_id=run_id,
                task_id=runtime.task_id,
                chunk_count=sequence,
            ),
            shutdown_event,
            "OpenAI audio speech completed",
        )
    except BinaryStreamRuntimeFailure as exception:
        await enqueue_correlated_media_event(
            enqueue_warning_tracker,
            connection.queue,
            build_openai_audio_speech_error(
                run_id=run_id,
                message=exception.message,
                code=exception.error_type,
                task_id=runtime.task_id,
            ),
            shutdown_event,
            "OpenAI audio speech error",
        )
    except asyncio.CancelledError:
        if openai_ws_detach_event_is_set(runtime.detach_event):
            return
        raise
    except RECOVERABLE_EXCEPTIONS as exception:
        if openai_ws_detach_event_is_set(runtime.detach_event):
            return
        coerced = coerce_to_soai_error(
            exception,
            operation=OPERATION_WS_OPENAI_AUDIO_SPEECH_STREAM,
        )
        log_exception(
            logger,
            exception,
            message="OpenAI speech streaming failed.",
            operation=OPERATION_WS_OPENAI_AUDIO_SPEECH_STREAM,
            trace_id=trace_id,
            level="error",
        )
        await enqueue_correlated_media_event(
            enqueue_warning_tracker=enqueue_warning_tracker,
            queue=connection.queue,
            event=build_openai_audio_speech_error(
                run_id=run_id,
                message=str(coerced),
                code=str(coerced.code),
                task_id=runtime.task_id,
            ),
            shutdown_event=shutdown_event,
            context_label="OpenAI audio speech error",
        )
    finally:
        if connection.openai_audio_speech_streams.get(run_id) is runtime:
            connection.openai_audio_speech_streams.pop(run_id, None)
