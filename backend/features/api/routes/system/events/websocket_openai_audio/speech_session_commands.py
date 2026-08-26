"""SoAI - WebSocket OpenAI speech session command handlers [backend/features/api/routes/system/events/websocket_openai_audio/speech_session_commands.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from core.errors.exceptions import SoAIError
from features.api.routes.system.events.websocket_openai_audio.runtime import (
    OpenAiAudioSpeechSessionSegment,
    require_run_id,
)
from features.api.routes.system.events.websocket_openai_audio.speech_session_errors import (
    enqueue_speech_session_error,
    log_speech_session_validation_exception,
)
from features.api.routes.system.events.websocket_openai_audio.speech_session_terminal import (
    cancel_speech_session_with_client_event,
    cancel_speech_session_with_error,
)
from features.api.routes.system.events.websocket_openai_audio.speech_session_validation import (
    require_speech_session_input,
    require_speech_session_segment_sequence,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from features.api.runtime.container.enqueue_warning_tracker import (
        EnqueueWarningTracker,
    )
    from features.api.runtime.context import ApiContext
    from features.api.streaming.websocket import WebsocketConnection

__all__ = (
    "handle_openai_audio_speech_session_cancel",
    "handle_openai_audio_speech_session_finish",
    "handle_openai_audio_speech_session_segment",
)


async def handle_openai_audio_speech_session_segment(
    data: JSONDict,
    *,
    connection: WebsocketConnection,
    api_context: ApiContext,
    enqueue_warning_tracker: EnqueueWarningTracker,
) -> None:
    try:
        run_id = require_run_id(data)
    except (SoAIError, ValueError) as exception:
        log_speech_session_validation_exception(exception, None)
        return
    try:
        segment_sequence = require_speech_session_segment_sequence(data)
        input_text = require_speech_session_input(data)
    except (SoAIError, ValueError) as exception:
        log_speech_session_validation_exception(exception, None)
        runtime = connection.openai_audio_speech_sessions.get(run_id)
        if runtime is None:
            enqueue_speech_session_error(
                connection,
                enqueue_warning_tracker,
                run_id,
                "Unknown speech session run_id.",
                "not_found_error",
            )
            return
        async with runtime.lock:
            if runtime.detach_event.is_set():
                return
            cancel_speech_session_with_error(
                connection=connection,
                api_context=api_context,
                enqueue_warning_tracker=enqueue_warning_tracker,
                runtime=runtime,
                message=str(exception),
                code="invalid_request_error",
            )
        return
    runtime = connection.openai_audio_speech_sessions.get(run_id)
    if runtime is None:
        enqueue_speech_session_error(
            connection,
            enqueue_warning_tracker,
            run_id,
            "Unknown speech session run_id.",
            "not_found_error",
        )
        return
    async with runtime.lock:
        if runtime.detach_event.is_set():
            return
        if runtime.sealed:
            cancel_speech_session_with_error(
                connection=connection,
                api_context=api_context,
                enqueue_warning_tracker=enqueue_warning_tracker,
                runtime=runtime,
                message="Speech session already finished.",
            )
            return
        if segment_sequence != runtime.next_segment_sequence:
            cancel_speech_session_with_error(
                connection=connection,
                api_context=api_context,
                enqueue_warning_tracker=enqueue_warning_tracker,
                runtime=runtime,
                message="Speech session segment_sequence is out of order.",
            )
            return
        try:
            runtime.queue.put_nowait(OpenAiAudioSpeechSessionSegment(segment_sequence, input_text))
        except asyncio.QueueFull:
            cancel_speech_session_with_error(
                connection=connection,
                api_context=api_context,
                enqueue_warning_tracker=enqueue_warning_tracker,
                runtime=runtime,
                message="Speech session queue is full.",
            )
            return
        runtime.next_segment_sequence += 1
        runtime.state_event.set()


async def handle_openai_audio_speech_session_finish(
    data: JSONDict,
    *,
    connection: WebsocketConnection,
    enqueue_warning_tracker: EnqueueWarningTracker,
) -> None:
    try:
        run_id = require_run_id(data)
    except (SoAIError, ValueError):
        return
    runtime = connection.openai_audio_speech_sessions.get(run_id)
    if runtime is None:
        enqueue_speech_session_error(
            connection,
            enqueue_warning_tracker,
            run_id,
            "Unknown speech session run_id.",
            "not_found_error",
        )
        return
    async with runtime.lock:
        if runtime.detach_event.is_set():
            return
        runtime.sealed = True
        runtime.state_event.set()


async def handle_openai_audio_speech_session_cancel(
    data: JSONDict,
    *,
    connection: WebsocketConnection,
    api_context: ApiContext,
    enqueue_warning_tracker: EnqueueWarningTracker,
) -> None:
    try:
        run_id = require_run_id(data)
    except (SoAIError, ValueError):
        return
    reason = _resolve_cancel_reason(data)
    runtime = connection.openai_audio_speech_sessions.get(run_id)
    if runtime is None:
        return
    async with runtime.lock:
        cancel_speech_session_with_client_event(
            connection=connection,
            api_context=api_context,
            enqueue_warning_tracker=enqueue_warning_tracker,
            runtime=runtime,
            reason=reason,
        )


def _resolve_cancel_reason(data: JSONDict) -> str:
    reason_value = data.get("reason")
    if isinstance(reason_value, str) and reason_value.strip():
        return reason_value.strip()
    return "Cancelled"
