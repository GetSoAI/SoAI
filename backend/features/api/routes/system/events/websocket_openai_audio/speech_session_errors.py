"""SoAI - WebSocket OpenAI speech session error events [backend/features/api/routes/system/events/websocket_openai_audio/speech_session_errors.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exception_logging import log_exception
from core.logging.trace import get_logger
from features.api.routes.system.events.websocket_openai_audio.payloads import (
    build_openai_audio_speech_session_error,
)
from features.api.runtime.event_enqueue import enqueue_event_or_warn

if TYPE_CHECKING:
    from features.api.runtime.container.enqueue_warning_tracker import (
        EnqueueWarningTracker,
    )
    from features.api.streaming.websocket import WebsocketConnection

__all__ = (
    "OPERATION_SPEECH_SESSION_VALIDATE",
    "OPERATION_WS_OPENAI_AUDIO_SPEECH_SESSION",
    "enqueue_speech_session_error",
    "log_speech_session_validation_exception",
)

LOGGER_NAME = "SoAI.features.api.speech_session_errors"
OPERATION_SPEECH_SESSION_VALIDATE = "api_system.websocket.openai_audio.speech_session.validate"
OPERATION_WS_OPENAI_AUDIO_SPEECH_SESSION = "ws_openai_audio.speech_session"


def enqueue_speech_session_error(
    connection: WebsocketConnection,
    enqueue_warning_tracker: EnqueueWarningTracker,
    run_id: str,
    message: str,
    code: str,
    task_id: str | None = None,
) -> None:
    enqueue_event_or_warn(
        enqueue_warning_tracker,
        connection.queue,
        build_openai_audio_speech_session_error(
            run_id=run_id,
            message=message,
            code=code,
            task_id=task_id,
        ),
        "OpenAI audio speech session error",
    )


def log_speech_session_validation_exception(exception: BaseException, trace_id: str | None) -> None:
    log_exception(
        get_logger(LOGGER_NAME),
        exception,
        message="Invalid OpenAI speech session payload (non-critical).",
        operation=OPERATION_SPEECH_SESSION_VALIDATE,
        trace_id=trace_id,
        level="debug",
    )
