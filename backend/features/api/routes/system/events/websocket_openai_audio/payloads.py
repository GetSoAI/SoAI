"""SoAI - WebSocket payload builders for OpenAI audio commands [backend/features/api/routes/system/events/websocket_openai_audio/payloads.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.system_api.websocket_run_events import (
    build_websocket_run_error_event,
    build_websocket_run_event,
)
from features.api.routes.system.events.internal_protocols import WebSocketEventTypes

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "build_openai_audio_speech_cancelled",
    "build_openai_audio_speech_chunk",
    "build_openai_audio_speech_completed",
    "build_openai_audio_speech_error",
    "build_openai_audio_speech_session_cancelled",
    "build_openai_audio_speech_session_chunk",
    "build_openai_audio_speech_session_completed",
    "build_openai_audio_speech_session_error",
    "build_openai_audio_speech_session_segment_completed",
    "build_openai_audio_speech_session_segment_started",
    "build_openai_audio_speech_session_started",
    "build_openai_audio_speech_started",
    "build_openai_audio_transcription_cancelled",
    "build_openai_audio_transcription_completed",
    "build_openai_audio_transcription_error",
    "build_openai_audio_transcription_started",
)


def build_openai_audio_transcription_started(
    *,
    run_id: str,
    task_id: str,
) -> JSONDict:
    return build_websocket_run_event(
        event_type=WebSocketEventTypes.OPENAI_AUDIO_TRANSCRIPTION_STARTED,
        run_id=run_id,
        task_id=task_id,
    )


def build_openai_audio_transcription_completed(
    *,
    run_id: str,
    task_id: str,
    result: JSONValue,
) -> JSONDict:
    return build_websocket_run_event(
        event_type=WebSocketEventTypes.OPENAI_AUDIO_TRANSCRIPTION_COMPLETED,
        run_id=run_id,
        task_id=task_id,
        fields={"result": result},
    )


def build_openai_audio_transcription_cancelled(
    *,
    run_id: str,
    reason: str,
) -> JSONDict:
    return build_websocket_run_event(
        event_type=WebSocketEventTypes.OPENAI_AUDIO_TRANSCRIPTION_CANCELLED,
        run_id=run_id,
        fields={"reason": reason},
    )


def build_openai_audio_transcription_error(
    *,
    run_id: str,
    message: str,
    code: str,
    task_id: str | None = None,
) -> JSONDict:
    return build_websocket_run_error_event(
        event_type=WebSocketEventTypes.OPENAI_AUDIO_TRANSCRIPTION_ERROR,
        run_id=run_id,
        message=message,
        code=code,
        task_id=task_id,
    )


def build_openai_audio_speech_started(
    *,
    run_id: str,
    task_id: str,
    media_type: str,
) -> JSONDict:
    return build_websocket_run_event(
        event_type=WebSocketEventTypes.OPENAI_AUDIO_SPEECH_STARTED,
        run_id=run_id,
        task_id=task_id,
        fields={"media_type": media_type},
    )


def build_openai_audio_speech_chunk(
    *,
    run_id: str,
    sequence: int,
    chunk_base64: str,
) -> JSONDict:
    return build_websocket_run_event(
        event_type=WebSocketEventTypes.OPENAI_AUDIO_SPEECH_CHUNK,
        run_id=run_id,
        fields={"sequence": sequence, "chunk_base64": chunk_base64},
    )


def build_openai_audio_speech_completed(
    *,
    run_id: str,
    task_id: str,
    chunk_count: int,
) -> JSONDict:
    return build_websocket_run_event(
        event_type=WebSocketEventTypes.OPENAI_AUDIO_SPEECH_COMPLETED,
        run_id=run_id,
        task_id=task_id,
        fields={"chunk_count": chunk_count},
    )


def build_openai_audio_speech_cancelled(
    *,
    run_id: str,
    reason: str,
) -> JSONDict:
    return build_websocket_run_event(
        event_type=WebSocketEventTypes.OPENAI_AUDIO_SPEECH_CANCELLED,
        run_id=run_id,
        fields={"reason": reason},
    )


def build_openai_audio_speech_error(
    *,
    run_id: str,
    message: str,
    code: str,
    task_id: str | None = None,
) -> JSONDict:
    return build_websocket_run_error_event(
        event_type=WebSocketEventTypes.OPENAI_AUDIO_SPEECH_ERROR,
        run_id=run_id,
        message=message,
        code=code,
        task_id=task_id,
    )


def build_openai_audio_speech_session_started(
    *,
    run_id: str,
    media_type: str,
) -> JSONDict:
    return build_websocket_run_event(
        event_type=WebSocketEventTypes.OPENAI_AUDIO_SPEECH_SESSION_STARTED,
        run_id=run_id,
        fields={"media_type": media_type},
    )


def build_openai_audio_speech_session_segment_started(
    *,
    run_id: str,
    segment_sequence: int,
    task_id: str,
) -> JSONDict:
    return build_websocket_run_event(
        event_type=WebSocketEventTypes.OPENAI_AUDIO_SPEECH_SESSION_SEGMENT_STARTED,
        run_id=run_id,
        task_id=task_id,
        fields={"segment_sequence": segment_sequence},
    )


def build_openai_audio_speech_session_chunk(
    *,
    run_id: str,
    segment_sequence: int,
    chunk_sequence: int,
    chunk_base64: str,
) -> JSONDict:
    return build_websocket_run_event(
        event_type=WebSocketEventTypes.OPENAI_AUDIO_SPEECH_SESSION_CHUNK,
        run_id=run_id,
        fields={
            "segment_sequence": segment_sequence,
            "chunk_sequence": chunk_sequence,
            "chunk_base64": chunk_base64,
        },
    )


def build_openai_audio_speech_session_segment_completed(
    *,
    run_id: str,
    segment_sequence: int,
    task_id: str,
    chunk_count: int,
) -> JSONDict:
    return build_websocket_run_event(
        event_type=WebSocketEventTypes.OPENAI_AUDIO_SPEECH_SESSION_SEGMENT_COMPLETED,
        run_id=run_id,
        task_id=task_id,
        fields={"segment_sequence": segment_sequence, "chunk_count": chunk_count},
    )


def build_openai_audio_speech_session_completed(
    *,
    run_id: str,
) -> JSONDict:
    return build_websocket_run_event(
        event_type=WebSocketEventTypes.OPENAI_AUDIO_SPEECH_SESSION_COMPLETED,
        run_id=run_id,
    )


def build_openai_audio_speech_session_cancelled(
    *,
    run_id: str,
    reason: str,
) -> JSONDict:
    return build_websocket_run_event(
        event_type=WebSocketEventTypes.OPENAI_AUDIO_SPEECH_SESSION_CANCELLED,
        run_id=run_id,
        fields={"reason": reason},
    )


def build_openai_audio_speech_session_error(
    *,
    run_id: str,
    message: str,
    code: str,
    task_id: str | None = None,
) -> JSONDict:
    return build_websocket_run_error_event(
        event_type=WebSocketEventTypes.OPENAI_AUDIO_SPEECH_SESSION_ERROR,
        run_id=run_id,
        message=message,
        code=code,
        task_id=task_id,
    )
