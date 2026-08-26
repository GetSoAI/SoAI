"""SoAI - WebSocket OpenAI speech session cancellation [backend/features/api/routes/system/events/websocket_openai_audio/speech_session_cancellation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from features.api.streaming.stream_cancel import schedule_streaming_task_cancel

if TYPE_CHECKING:
    from core.logging.protocols import LoggerProtocol
    from features.api.runtime.context import ApiContext
    from features.api.streaming.websocket import WebsocketConnection
    from features.api.streaming.websocket_openai_runtime import (
        OpenAiAudioSpeechSessionRuntime,
    )

__all__ = ("cancel_openai_audio_speech_session_runtime",)


def cancel_openai_audio_speech_session_runtime(
    *,
    runtime: OpenAiAudioSpeechSessionRuntime,
    api_context: ApiContext,
    connection: WebsocketConnection,
    reason: str,
    operation: str,
    logger: LoggerProtocol,
) -> None:
    runtime.detach_event.set()
    runtime.state_event.set()
    while not runtime.queue.empty():
        runtime.queue.get_nowait()
    if (
        not runtime.admitting_task
        and runtime.runner_task is not None
        and not runtime.runner_task.done()
    ):
        runtime.runner_task.cancel()
    if runtime.active_task_id:
        schedule_streaming_task_cancel(
            registry=api_context.dependencies.task_registry,
            task_id=runtime.active_task_id,
            reason=reason,
            context=connection.request.state.context,
            logger=logger,
            operation=operation,
            track_background_task=api_context.dependencies.application_control.track_background_task,
        )
