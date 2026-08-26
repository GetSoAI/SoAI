"""SoAI - WebSocket OpenAI speech session stream forwarding [backend/features/api/routes/system/events/websocket_openai_audio/speech_session_streaming.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from core.serialization.base64_values import encode_base64_ascii
from features.api.routes.system.events.websocket_openai_audio.payloads import (
    build_openai_audio_speech_session_chunk,
    build_openai_audio_speech_session_error,
    build_openai_audio_speech_session_segment_completed,
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
        OpenAiAudioSpeechSessionRuntime,
        OpenAiAudioSpeechSessionSegment,
    )
    from features.api.runtime.container.enqueue_warning_tracker import (
        EnqueueWarningTracker,
    )
    from features.api.streaming.types import StreamDependencies
    from features.api.streaming.websocket import WebsocketConnection

__all__ = ("forward_speech_session_segment_stream",)


async def forward_speech_session_segment_stream(
    *,
    runtime: OpenAiAudioSpeechSessionRuntime,
    segment: OpenAiAudioSpeechSessionSegment,
    task_id: str,
    reply_queue: asyncio.Queue[Event],
    connection: WebsocketConnection,
    stream_dependencies: StreamDependencies,
    request_context: RequestContext,
    enqueue_warning_tracker: EnqueueWarningTracker,
    shutdown_event: asyncio.Event,
) -> None:
    prepared = await prepare_binary_stream_payload(
        reply_queue,
        stream_dependencies,
        request_context,
        trace_id=request_context.trace_id,
    )
    if prepared.stream is None:
        await enqueue_correlated_media_event(
            enqueue_warning_tracker,
            connection.queue,
            build_openai_audio_speech_session_error(
                run_id=runtime.run_id,
                message=prepared.error_message or "Speech session segment failed.",
                code=prepared.error_type or "server_error",
                task_id=task_id,
            ),
            shutdown_event,
            "OpenAI audio speech session error",
        )
        runtime.detach_event.set()
        runtime.state_event.set()
        return
    chunk_sequence = 0
    try:
        async for chunk in prepared.stream:
            if openai_ws_detach_event_is_set(runtime.detach_event):
                return
            if not chunk:
                continue
            delivered = await enqueue_correlated_media_event(
                enqueue_warning_tracker,
                connection.queue,
                build_openai_audio_speech_session_chunk(
                    run_id=runtime.run_id,
                    segment_sequence=segment.segment_sequence,
                    chunk_sequence=chunk_sequence,
                    chunk_base64=encode_base64_ascii(chunk),
                ),
                shutdown_event,
                "OpenAI audio speech session chunk",
            )
            if not delivered:
                runtime.detach_event.set()
                runtime.state_event.set()
                return
            chunk_sequence += 1
    except BinaryStreamRuntimeFailure as exception:
        await enqueue_correlated_media_event(
            enqueue_warning_tracker,
            connection.queue,
            build_openai_audio_speech_session_error(
                run_id=runtime.run_id,
                message=exception.message,
                code=exception.error_type,
                task_id=task_id,
            ),
            shutdown_event,
            "OpenAI audio speech session error",
        )
        runtime.detach_event.set()
        runtime.state_event.set()
        return
    delivered = await enqueue_correlated_media_event(
        enqueue_warning_tracker,
        connection.queue,
        build_openai_audio_speech_session_segment_completed(
            run_id=runtime.run_id,
            segment_sequence=segment.segment_sequence,
            task_id=task_id,
            chunk_count=chunk_sequence,
        ),
        shutdown_event,
        "OpenAI audio speech session segment completed",
    )
    if not delivered:
        runtime.detach_event.set()
        runtime.state_event.set()
