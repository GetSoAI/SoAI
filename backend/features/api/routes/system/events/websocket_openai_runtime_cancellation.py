"""SoAI - WebSocket OpenAI runtime cancellation helpers [backend/features/api/routes/system/events/websocket_openai_runtime_cancellation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.logging.protocols import LoggerProtocol
from features.api.streaming.stream_cancel import schedule_streaming_task_cancel
from features.api.streaming.websocket_openai_runtime import (
    OpenAiAudioSpeechRuntime,
    OpenAiAudioTranscriptionRuntime,
    OpenAiImageGenerationRuntime,
)

if TYPE_CHECKING:
    from features.api.runtime.context import ApiContext
    from features.api.streaming.websocket import WebsocketConnection

__all__ = (
    "cancel_openai_ws_active_task_runtime",
    "cancel_openai_ws_speech_runtime",
)


def cancel_openai_ws_active_task_runtime(
    *,
    runtime: OpenAiAudioTranscriptionRuntime | OpenAiImageGenerationRuntime,
    api_context: ApiContext,
    connection: WebsocketConnection,
    reason: str,
    operation: str,
    logger: LoggerProtocol,
) -> None:
    if runtime.detach_event is not None:
        runtime.detach_event.set()
    if runtime.runner_task is not None and not runtime.runner_task.done():
        runtime.runner_task.cancel()
    task_id = runtime.active_task_id
    if task_id:
        schedule_streaming_task_cancel(
            registry=api_context.dependencies.task_registry,
            task_id=task_id,
            reason=reason,
            context=connection.request.state.context,
            logger=logger,
            operation=operation,
            track_background_task=api_context.dependencies.application_control.track_background_task,
        )


def cancel_openai_ws_speech_runtime(
    *,
    runtime: OpenAiAudioSpeechRuntime,
    api_context: ApiContext,
    connection: WebsocketConnection,
    reason: str,
    operation: str,
    logger: LoggerProtocol,
) -> None:
    if runtime.detach_event is not None:
        runtime.detach_event.set()
    if runtime.runner_task is not None and not runtime.runner_task.done():
        runtime.runner_task.cancel()
    schedule_streaming_task_cancel(
        registry=api_context.dependencies.task_registry,
        task_id=runtime.task_id,
        reason=reason,
        context=connection.request.state.context,
        logger=logger,
        operation=operation,
        track_background_task=api_context.dependencies.application_control.track_background_task,
    )
