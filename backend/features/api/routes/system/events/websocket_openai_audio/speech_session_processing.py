"""SoAI - WebSocket OpenAI speech session segment processing [backend/features/api/routes/system/events/websocket_openai_audio/speech_session_processing.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from core.concurrency.cancellation_cleanup import uncancel_then_cleanup
from core.logging.trace import get_logger
from core.runtime.request_context_cloning import clone_request_context
from features.api.routes.system.events.websocket_openai_audio.payloads import (
    build_openai_audio_speech_session_segment_started,
)
from features.api.routes.system.events.websocket_openai_audio.speech_session_errors import (
    OPERATION_WS_OPENAI_AUDIO_SPEECH_SESSION,
)
from features.api.routes.system.events.websocket_openai_audio.speech_session_streaming import (
    forward_speech_session_segment_stream,
)
from features.api.routes.system.events.websocket_openai_audio.speech_session_tasks import (
    accept_speech_session_segment_task,
)
from features.api.runtime.event_enqueue import enqueue_event_or_warn
from features.api.streaming.stream_cancel import schedule_streaming_task_cancel

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

__all__ = ("process_speech_session_segment",)

LOGGER_NAME = "SoAI.features.api.speech_session_processing"


async def process_speech_session_segment(
    *,
    runtime: OpenAiAudioSpeechSessionRuntime,
    segment: OpenAiAudioSpeechSessionSegment,
    connection: WebsocketConnection,
    api_context: ApiContext,
    stream_dependencies: StreamDependencies,
    request_context: RequestContext,
    enqueue_warning_tracker: EnqueueWarningTracker,
    shutdown_event: asyncio.Event,
) -> None:
    async with runtime.lock:
        if runtime.detach_event.is_set():
            return
        runtime.admitting_task = True
    task_bundle = None
    try:
        task_bundle = await accept_speech_session_segment_task(
            api_context=api_context,
            connection=connection,
            enqueue_warning_tracker=enqueue_warning_tracker,
            request_context=clone_request_context(request_context, task_id=None),
            run_id=runtime.run_id,
            user_id=runtime.user_id,
            session_payload=runtime.payload,
            segment_sequence=segment.segment_sequence,
            input_text=segment.input,
        )
    finally:
        if task_bundle is None:

            async def clear_admission_state() -> None:
                async with runtime.lock:
                    runtime.admitting_task = False
                    runtime.state_event.set()

            await uncancel_then_cleanup(clear_admission_state())
    async with runtime.lock:
        runtime.admitting_task = False
        detach_requested = runtime.detach_event.is_set()
        if task_bundle is not None:
            task_id, reply_queue = task_bundle
            runtime.active_task_id = task_id
        runtime.state_event.set()
    if task_bundle is None:
        if not detach_requested:
            runtime.detach_event.set()
            runtime.state_event.set()
        return
    task_id, reply_queue = task_bundle
    if detach_requested:
        _schedule_segment_cancel(api_context, connection, task_id)
        async with runtime.lock:
            if runtime.active_task_id == task_id:
                runtime.active_task_id = None
        return
    enqueue_event_or_warn(
        enqueue_warning_tracker,
        connection.queue,
        build_openai_audio_speech_session_segment_started(
            run_id=runtime.run_id,
            segment_sequence=segment.segment_sequence,
            task_id=task_id,
        ),
        "OpenAI audio speech session segment started",
    )
    try:
        await forward_speech_session_segment_stream(
            runtime=runtime,
            segment=segment,
            task_id=task_id,
            reply_queue=reply_queue,
            connection=connection,
            stream_dependencies=stream_dependencies,
            request_context=request_context,
            enqueue_warning_tracker=enqueue_warning_tracker,
            shutdown_event=shutdown_event,
        )
    finally:

        async def clear_active_task() -> None:
            async with runtime.lock:
                if runtime.active_task_id == task_id:
                    runtime.active_task_id = None
                runtime.state_event.set()

        await uncancel_then_cleanup(clear_active_task())


def _schedule_segment_cancel(
    api_context: ApiContext,
    connection: WebsocketConnection,
    task_id: str,
) -> None:
    schedule_streaming_task_cancel(
        registry=api_context.dependencies.task_registry,
        task_id=task_id,
        reason="Speech session cancelled.",
        context=connection.request.state.context,
        logger=get_logger(LOGGER_NAME),
        operation=OPERATION_WS_OPENAI_AUDIO_SPEECH_SESSION,
        track_background_task=api_context.dependencies.application_control.track_background_task,
    )
