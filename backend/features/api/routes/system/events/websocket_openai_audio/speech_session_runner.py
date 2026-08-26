"""SoAI - WebSocket OpenAI speech session runner [backend/features/api/routes/system/events/websocket_openai_audio/speech_session_runner.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger
from features.api.routes.system.events.websocket_openai_audio.payloads import (
    build_openai_audio_speech_session_completed,
    build_openai_audio_speech_session_error,
)
from features.api.routes.system.events.websocket_openai_audio.speech_session_processing import (
    process_speech_session_segment,
)
from features.api.routes.system.events.websocket_openai_runner_failure_handling import (
    openai_ws_detach_event_is_set,
)
from features.api.runtime.event_enqueue import enqueue_correlated_media_event

if TYPE_CHECKING:
    from core.runtime.request_context import RequestContext
    from features.api.routes.system.events.websocket_openai_audio.runtime import (
        OpenAiAudioSpeechSessionRuntime,
        OpenAiAudioSpeechSessionSegment,
    )
    from features.api.runtime.container.enqueue_warning_tracker import (
        EnqueueWarningTracker,
    )
    from features.api.runtime.context import ApiContext
    from features.api.streaming.types import StreamDependencies
    from features.api.streaming.websocket import WebsocketConnection

__all__ = ("run_openai_audio_speech_session",)

LOGGER_NAME = "SoAI.features.api.speech_session_runner"
OPERATION_WS_OPENAI_AUDIO_SPEECH_SESSION = "ws_openai_audio.speech_session"


async def run_openai_audio_speech_session(
    *,
    runtime: OpenAiAudioSpeechSessionRuntime,
    connection: WebsocketConnection,
    api_context: ApiContext,
    stream_dependencies: StreamDependencies,
    request_context: RequestContext,
    enqueue_warning_tracker: EnqueueWarningTracker,
    trace_id: str | None,
    shutdown_event: asyncio.Event,
) -> None:
    logger = get_logger(LOGGER_NAME)
    try:
        while True:
            segment = await _resolve_next_segment(runtime)
            if segment is None:
                await _emit_completed_if_needed(
                    runtime,
                    connection,
                    enqueue_warning_tracker,
                    shutdown_event,
                )
                return
            await process_speech_session_segment(
                runtime=runtime,
                segment=segment,
                connection=connection,
                api_context=api_context,
                stream_dependencies=stream_dependencies,
                request_context=request_context,
                enqueue_warning_tracker=enqueue_warning_tracker,
                shutdown_event=shutdown_event,
            )
    except asyncio.CancelledError:
        detached = openai_ws_detach_event_is_set(runtime.detach_event)
        if detached:
            return
        raise
    except RECOVERABLE_EXCEPTIONS as exception:
        detached = openai_ws_detach_event_is_set(runtime.detach_event)
        if detached:
            return
        coerced = coerce_to_soai_error(
            exception,
            operation=OPERATION_WS_OPENAI_AUDIO_SPEECH_SESSION,
        )
        log_exception(
            logger,
            exception,
            message="OpenAI speech session failed.",
            operation=OPERATION_WS_OPENAI_AUDIO_SPEECH_SESSION,
            trace_id=trace_id,
            level="error",
        )
        await enqueue_correlated_media_event(
            enqueue_warning_tracker=enqueue_warning_tracker,
            queue=connection.queue,
            event=build_openai_audio_speech_session_error(
                run_id=runtime.run_id,
                message=str(coerced),
                code=str(coerced.code),
                task_id=runtime.active_task_id,
            ),
            shutdown_event=shutdown_event,
            context_label="OpenAI audio speech session error",
        )
    finally:
        if connection.openai_audio_speech_sessions.get(runtime.run_id) is runtime:
            connection.openai_audio_speech_sessions.pop(runtime.run_id, None)


async def _resolve_next_segment(
    runtime: OpenAiAudioSpeechSessionRuntime,
) -> OpenAiAudioSpeechSessionSegment | None:
    while True:
        async with runtime.lock:
            if runtime.detach_event.is_set():
                return None
            try:
                return runtime.queue.get_nowait()
            except asyncio.QueueEmpty:
                if runtime.sealed:
                    return None
                runtime.state_event.clear()
        await runtime.state_event.wait()


async def _emit_completed_if_needed(
    runtime: OpenAiAudioSpeechSessionRuntime,
    connection: WebsocketConnection,
    enqueue_warning_tracker: EnqueueWarningTracker,
    shutdown_event: asyncio.Event,
) -> None:
    async with runtime.lock:
        if runtime.detach_event.is_set() or runtime.terminal_emitted:
            return
        runtime.terminal_emitted = True
    await enqueue_correlated_media_event(
        enqueue_warning_tracker,
        connection.queue,
        build_openai_audio_speech_session_completed(run_id=runtime.run_id),
        shutdown_event,
        "OpenAI audio speech session completed",
    )
