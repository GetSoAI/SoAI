"""SoAI - WebSocket OpenAI speech session start handler [backend/features/api/routes/system/events/websocket_openai_audio/speech_session_start.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exceptions import SoAIError
from core.runtime.request_context_cloning import clone_request_context
from core.timing.monotonic import monotonic_ms
from core.users.user_id import coerce_user_id
from features.api.routes.system.events.internal_protocols import WebSocketEventTypes
from features.api.routes.system.events.websocket_openai_audio.payloads import (
    build_openai_audio_speech_session_error,
    build_openai_audio_speech_session_started,
)
from features.api.routes.system.events.websocket_openai_audio.runtime import (
    OpenAiAudioSpeechSessionRuntime,
    require_run_id,
)
from features.api.routes.system.events.websocket_openai_audio.speech_session_errors import (
    enqueue_speech_session_error,
    log_speech_session_validation_exception,
)
from features.api.routes.system.events.websocket_openai_audio.speech_session_runner import (
    run_openai_audio_speech_session,
)
from features.api.routes.system.events.websocket_openai_audio.speech_session_validation import (
    build_speech_session_payload,
)
from features.api.routes.system.events.websocket_openai_run_start_guard import (
    guard_openai_ws_run_start,
)
from features.api.runtime.event_enqueue import enqueue_event_or_warn

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from features.api.runtime.container.enqueue_warning_tracker import (
        EnqueueWarningTracker,
    )
    from features.api.runtime.context import ApiContext
    from features.api.streaming.types import StreamDependencies
    from features.api.streaming.websocket import WebsocketConnection

__all__ = ("handle_openai_audio_speech_session_start",)

SPEECH_SESSION_QUEUE_SIZE = 16


async def handle_openai_audio_speech_session_start(
    data: JSONDict,
    *,
    connection: WebsocketConnection,
    api_context: ApiContext,
    stream_dependencies: StreamDependencies,
    enqueue_warning_tracker: EnqueueWarningTracker,
    trace_id: str | None,
    shutdown_event: asyncio.Event,
) -> None:
    run_id = await guard_openai_ws_run_start(
        data,
        connection=connection,
        enqueue_warning_tracker=enqueue_warning_tracker,
        trace_id=trace_id,
        error_event_type=WebSocketEventTypes.OPENAI_AUDIO_SPEECH_SESSION_ERROR,
        build_forbidden_error_payload=build_openai_audio_speech_session_error,
        warn_label="OpenAI audio speech session error",
        require_run_id=require_run_id,
    )
    if run_id is None:
        return
    if run_id in connection.openai_audio_speech_sessions:
        enqueue_speech_session_error(
            connection,
            enqueue_warning_tracker,
            run_id,
            "Speech session run_id already exists.",
            "conflict_error",
        )
        return
    try:
        payload, media_type = await build_speech_session_payload(data=data, api_context=api_context)
    except (SoAIError, ValueError) as exception:
        coerced = coerce_to_soai_error(exception)
        log_speech_session_validation_exception(exception, trace_id)
        enqueue_speech_session_error(
            connection,
            enqueue_warning_tracker,
            run_id,
            str(coerced),
            str(coerced.code),
        )
        return
    context = clone_request_context(connection.request.state.context, task_id=None)
    runtime = OpenAiAudioSpeechSessionRuntime(
        run_id=run_id,
        user_id=coerce_user_id(context.user_id),
        started_at_ms=monotonic_ms(),
        payload=payload,
        media_type=media_type,
        queue=asyncio.Queue(maxsize=SPEECH_SESSION_QUEUE_SIZE),
        lock=asyncio.Lock(),
        state_event=asyncio.Event(),
        detach_event=asyncio.Event(),
        runner_task=None,
        active_task_id=None,
        admitting_task=False,
        sealed=False,
        next_segment_sequence=0,
        terminal_emitted=False,
    )
    connection.openai_audio_speech_sessions[run_id] = runtime
    runner_task = api_context.dependencies.application_control.schedule_background_task(
        run_openai_audio_speech_session(
            runtime=runtime,
            connection=connection,
            api_context=api_context,
            stream_dependencies=stream_dependencies,
            request_context=context,
            enqueue_warning_tracker=enqueue_warning_tracker,
            trace_id=trace_id,
            shutdown_event=shutdown_event,
        ),
        name=f"ws_openai_audio_speech_session:{run_id}",
    )
    if runner_task is None:
        connection.openai_audio_speech_sessions.pop(run_id, None)
        enqueue_speech_session_error(
            connection,
            enqueue_warning_tracker,
            run_id,
            "Speech session runner could not be scheduled.",
            "server_error",
        )
        return
    runtime.runner_task = runner_task
    enqueue_event_or_warn(
        enqueue_warning_tracker,
        connection.queue,
        build_openai_audio_speech_session_started(run_id=run_id, media_type=media_type),
        "OpenAI audio speech session started",
    )
