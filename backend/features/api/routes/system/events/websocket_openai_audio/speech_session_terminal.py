"""SoAI - WebSocket OpenAI speech session terminal events [backend/features/api/routes/system/events/websocket_openai_audio/speech_session_terminal.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.logging.trace import get_logger
from features.api.routes.system.events.websocket_openai_audio.payloads import (
    build_openai_audio_speech_session_cancelled,
)
from features.api.routes.system.events.websocket_openai_audio.speech_session_cancellation import (
    cancel_openai_audio_speech_session_runtime,
)
from features.api.routes.system.events.websocket_openai_audio.speech_session_errors import (
    OPERATION_WS_OPENAI_AUDIO_SPEECH_SESSION,
    enqueue_speech_session_error,
)
from features.api.runtime.event_enqueue import enqueue_event_or_warn

if TYPE_CHECKING:
    from features.api.runtime.container.enqueue_warning_tracker import (
        EnqueueWarningTracker,
    )
    from features.api.runtime.context import ApiContext
    from features.api.streaming.websocket import WebsocketConnection
    from features.api.streaming.websocket_openai_runtime import (
        OpenAiAudioSpeechSessionRuntime,
    )

__all__ = (
    "cancel_speech_session_with_client_event",
    "cancel_speech_session_with_error",
)

LOGGER_NAME = "SoAI.features.api.speech_session_terminal"


def cancel_speech_session_with_error(
    *,
    connection: WebsocketConnection,
    api_context: ApiContext,
    enqueue_warning_tracker: EnqueueWarningTracker,
    runtime: OpenAiAudioSpeechSessionRuntime,
    message: str,
    code: str = "conflict_error",
) -> None:
    _cancel_runtime(connection=connection, api_context=api_context, runtime=runtime, reason=message)
    runtime.terminal_emitted = True
    enqueue_speech_session_error(
        connection,
        enqueue_warning_tracker,
        runtime.run_id,
        message,
        code,
        task_id=runtime.active_task_id,
    )


def cancel_speech_session_with_client_event(
    *,
    connection: WebsocketConnection,
    api_context: ApiContext,
    enqueue_warning_tracker: EnqueueWarningTracker,
    runtime: OpenAiAudioSpeechSessionRuntime,
    reason: str,
) -> None:
    _cancel_runtime(connection=connection, api_context=api_context, runtime=runtime, reason=reason)
    if runtime.terminal_emitted:
        return
    runtime.terminal_emitted = True
    enqueue_event_or_warn(
        enqueue_warning_tracker,
        connection.queue,
        build_openai_audio_speech_session_cancelled(run_id=runtime.run_id, reason=reason),
        "OpenAI audio speech session cancelled",
    )


def _cancel_runtime(
    *,
    connection: WebsocketConnection,
    api_context: ApiContext,
    runtime: OpenAiAudioSpeechSessionRuntime,
    reason: str,
) -> None:
    cancel_openai_audio_speech_session_runtime(
        runtime=runtime,
        api_context=api_context,
        connection=connection,
        reason=reason,
        operation=OPERATION_WS_OPENAI_AUDIO_SPEECH_SESSION,
        logger=get_logger(LOGGER_NAME),
    )
    if connection.openai_audio_speech_sessions.get(runtime.run_id) is runtime:
        connection.openai_audio_speech_sessions.pop(runtime.run_id, None)
