"""SoAI - WebSocket cleanup and teardown for system events channel [backend/features/api/routes/system/events/websocket_cleanup.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable

from fastapi import WebSocket

from core.concurrency.cancellation_cleanup import uncancel_then_cleanup
from core.concurrency.task_groups import (
    DEFAULT_CANCELLATION_TIMEOUT_SEC,
    cancel_and_await,
)
from core.errors.exception_logging import log_exception, log_handled_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.events.protocols import EventBusProtocol
from core.events.types_base import Event
from core.files.upload_staging import cleanup_temp_file
from core.logging.trace import get_logger
from features.api.routes.system.events.chat_stream.cancel import (
    schedule_ws_chat_stream_cancel,
)
from features.api.routes.system.events.websocket_model_test_stream.runner import (
    schedule_ws_model_test_stream_cancel,
)
from features.api.routes.system.events.websocket_openai_audio.speech_session_cancellation import (
    cancel_openai_audio_speech_session_runtime,
)
from features.api.routes.system.events.websocket_openai_audio.speech_session_errors import (
    OPERATION_WS_OPENAI_AUDIO_SPEECH_SESSION,
)
from features.api.routes.system.events.websocket_transport_lifecycle import (
    WEBSOCKET_CLIENT_DISCONNECT_EXCEPTIONS,
    is_websocket_close_state_error,
    should_close_websocket_application_state,
)
from features.api.runtime.context import ApiContext
from features.api.streaming.stream_cancel import schedule_streaming_task_cancel
from features.api.streaming.websocket import WebsocketConnection
from features.chat.conversation_input_disconnect import (
    cancel_running_chat_input_for_disconnected_client,
)

__all__ = ("cleanup_websocket_connection",)

LOGGER_NAME = "SoAI.features.api.websocket_cleanup"
OPERATION_API_SYSTEM_WEBSOCKET_SYSTEM_EVENTS_CLEANUP_CLOSE_PTY_SESSION = (
    "api_system.websocket.system_events.cleanup.close_pty_session"
)
OPERATION_API_SYSTEM_WEBSOCKET_SYSTEM_EVENTS_CLEANUP_UNSUBSCRIBE = (
    "api_system.websocket.system_events.cleanup.unsubscribe"
)
OPERATION_API_SYSTEM_WEBSOCKET_SYSTEM_EVENTS_CLEANUP_WEBSOCKET_CLOSE = (
    "api_system.websocket.system_events.cleanup.websocket_close"
)
OPERATION_CHAT_INPUT_DISCONNECT = "api_system.websocket.chat_input_disconnect"
OPERATION_WS_OPENAI_AUDIO_SPEECH_DISCONNECT = "ws_openai_audio.speech.disconnect"
OPERATION_WS_OPENAI_AUDIO_TRANSCRIPTION_DISCONNECT = "ws_openai_audio.transcription.disconnect"
OPERATION_WS_OPENAI_IMAGES_DISCONNECT = "ws_openai_images.disconnect"


async def cleanup_websocket_connection(
    *,
    event_bus: EventBusProtocol,
    connection: WebsocketConnection,
    api_context: ApiContext,
    websocket: WebSocket,
    event_handler: Callable[[Event], Awaitable[None]],
    trace_id: str | None,
) -> None:
    logger = get_logger(LOGGER_NAME)
    track_background_task = api_context.dependencies.application_control.track_background_task
    unsubscribed_count = 0
    for event_type in connection.subscribed_types:
        try:
            event_bus.unsubscribe(event_type, event_handler)
            unsubscribed_count += 1
        except RECOVERABLE_EXCEPTIONS as unsubscribe_exception:
            log_handled_exception(
                get_logger(LOGGER_NAME),
                unsubscribe_exception,
                message="Event unsubscribe failed during WebSocket cleanup.",
                operation=OPERATION_API_SYSTEM_WEBSOCKET_SYSTEM_EVENTS_CLEANUP_UNSUBSCRIBE,
                details={"event_type": _describe_event_type(event_type)},
                level="debug",
            )
    logger.debug(
        "Unregistered %s WebSocket event subscriptions for %s.",
        unsubscribed_count,
        connection.user.get("username", "unknown"),
    )
    snapshot_tasks = list(connection.snapshot_tasks.values())
    if snapshot_tasks:
        await uncancel_then_cleanup(
            cancel_and_await(
                snapshot_tasks,
                logger=logger,
                task_label="websocket snapshot task",
                log_level=logging.DEBUG,
                timeout_sec=DEFAULT_CANCELLATION_TIMEOUT_SEC,
                timeout_log_level=logging.DEBUG,
            ),
        )
        connection.snapshot_tasks.clear()
    try:
        await cancel_running_chat_input_for_disconnected_client(
            api_context=api_context,
            connection=connection,
        )
    except RECOVERABLE_EXCEPTIONS as exception:
        log_handled_exception(
            logger,
            exception,
            message="Chat input disconnect cancellation failed during WebSocket cleanup.",
            operation=OPERATION_CHAT_INPUT_DISCONNECT,
            level="warning",
        )
    chat_streams = connection.chat_streams
    cancel_on_disconnect = api_context.dependencies.config.get_bool(
        "MODELS.ROUTING.CANCEL_ON_CLIENT_DISCONNECT",
    )
    for conv_id, chat_runtime in list(chat_streams.items()):
        if chat_runtime is None:
            continue
        if cancel_on_disconnect:
            if not chat_runtime.cancellation_requested:
                chat_runtime.cancellation_requested = True
                chat_runtime.cancellation_reason = "WebSocket disconnected."
            if chat_runtime.detach_event is not None:
                chat_runtime.detach_event.set()
            _ = schedule_ws_chat_stream_cancel(
                api_context=api_context,
                context=connection.request.state.context,
                runtime=chat_runtime,
                reason=chat_runtime.cancellation_reason or "WebSocket disconnected.",
            )
        existing = chat_streams.get(conv_id)
        if existing is chat_runtime:
            del chat_streams[conv_id]
    for run_id, model_test_runtime in list(connection.model_test_streams.items()):
        if model_test_runtime.detach_event is not None:
            model_test_runtime.detach_event.set()
        _ = schedule_ws_model_test_stream_cancel(
            api_context=api_context,
            request=connection.request,
            runtime=model_test_runtime,
            reason="WebSocket disconnected.",
        )
        existing_model_test_runtime = connection.model_test_streams.get(run_id)
        if existing_model_test_runtime is model_test_runtime:
            del connection.model_test_streams[run_id]
    for run_id, transcription_runtime in list(connection.openai_audio_transcriptions.items()):
        async with transcription_runtime.lock:
            transcription_runtime.state = "cancelled"
            if transcription_runtime.detach_event is not None:
                transcription_runtime.detach_event.set()
            if (
                transcription_runtime.runner_task is not None
                and not transcription_runtime.runner_task.done()
            ):
                transcription_runtime.runner_task.cancel()
            if transcription_runtime.active_task_id:
                _ = schedule_streaming_task_cancel(
                    registry=api_context.dependencies.task_registry,
                    task_id=transcription_runtime.active_task_id,
                    reason="WebSocket disconnected.",
                    context=connection.request.state.context,
                    logger=logger,
                    operation=OPERATION_WS_OPENAI_AUDIO_TRANSCRIPTION_DISCONNECT,
                    track_background_task=track_background_task,
                )
            await cleanup_temp_file(transcription_runtime.temp_path)
            existing_transcription_runtime = connection.openai_audio_transcriptions.get(run_id)
            if existing_transcription_runtime is transcription_runtime:
                del connection.openai_audio_transcriptions[run_id]
    for run_id, speech_runtime in list(connection.openai_audio_speech_streams.items()):
        if speech_runtime.detach_event is not None:
            speech_runtime.detach_event.set()
        if speech_runtime.runner_task is not None and not speech_runtime.runner_task.done():
            speech_runtime.runner_task.cancel()
        _ = schedule_streaming_task_cancel(
            registry=api_context.dependencies.task_registry,
            task_id=speech_runtime.task_id,
            reason="WebSocket disconnected.",
            context=connection.request.state.context,
            logger=logger,
            operation=OPERATION_WS_OPENAI_AUDIO_SPEECH_DISCONNECT,
            track_background_task=track_background_task,
        )
        existing_speech_runtime = connection.openai_audio_speech_streams.get(run_id)
        if existing_speech_runtime is speech_runtime:
            del connection.openai_audio_speech_streams[run_id]
    for run_id, speech_session_runtime in list(connection.openai_audio_speech_sessions.items()):
        async with speech_session_runtime.lock:
            cancel_openai_audio_speech_session_runtime(
                runtime=speech_session_runtime,
                api_context=api_context,
                connection=connection,
                reason="WebSocket disconnected.",
                operation=OPERATION_WS_OPENAI_AUDIO_SPEECH_SESSION,
                logger=logger,
            )
            existing_speech_session_runtime = connection.openai_audio_speech_sessions.get(run_id)
            if existing_speech_session_runtime is speech_session_runtime:
                del connection.openai_audio_speech_sessions[run_id]
    for run_id, image_generation_runtime in list(connection.openai_image_generations.items()):
        if image_generation_runtime.detach_event is not None:
            image_generation_runtime.detach_event.set()
        if (
            image_generation_runtime.runner_task is not None
            and not image_generation_runtime.runner_task.done()
        ):
            image_generation_runtime.runner_task.cancel()
        if image_generation_runtime.active_task_id:
            _ = schedule_streaming_task_cancel(
                registry=api_context.dependencies.task_registry,
                task_id=image_generation_runtime.active_task_id,
                reason="WebSocket disconnected.",
                context=connection.request.state.context,
                logger=logger,
                operation=OPERATION_WS_OPENAI_IMAGES_DISCONNECT,
                track_background_task=track_background_task,
            )
        existing_image_generation_runtime = connection.openai_image_generations.get(run_id)
        if existing_image_generation_runtime is image_generation_runtime:
            del connection.openai_image_generations[run_id]
    for _source_name, forward_task in list(connection.log_streams.items()):
        if forward_task is not None and not forward_task.done():
            await uncancel_then_cleanup(
                cancel_and_await(
                    [forward_task],
                    logger=logger,
                    task_label="websocket log stream forward task",
                    log_level=logging.DEBUG,
                    timeout_sec=DEFAULT_CANCELLATION_TIMEOUT_SEC,
                    timeout_log_level=logging.DEBUG,
                ),
            )
    connection.log_stream_replacements.clear()
    if connection.pty_session_id:
        try:
            await api_context.dependencies.terminal.close_pty_session(connection.pty_session_id)
        except RECOVERABLE_EXCEPTIONS as pty_exception:
            log_handled_exception(
                get_logger(LOGGER_NAME),
                pty_exception,
                message="PTY session cleanup failed during WebSocket cleanup.",
                operation=OPERATION_API_SYSTEM_WEBSOCKET_SYSTEM_EVENTS_CLEANUP_CLOSE_PTY_SESSION,
                details={"pty_session_id": connection.pty_session_id},
                level="debug",
            )
        connection.pty_session_id = None
    try:
        if should_close_websocket_application_state(websocket):
            await websocket.close(code=connection.close_code, reason=connection.close_reason)
    except WEBSOCKET_CLIENT_DISCONNECT_EXCEPTIONS as exception:
        log_handled_exception(
            logger,
            exception,
            message="WebSocket client disconnected during cleanup close.",
            operation=OPERATION_API_SYSTEM_WEBSOCKET_SYSTEM_EVENTS_CLEANUP_WEBSOCKET_CLOSE,
            trace_id=trace_id,
            level="debug",
        )
    except RuntimeError as runtime_error:
        if is_websocket_close_state_error(runtime_error):
            log_handled_exception(
                logger,
                runtime_error,
                message="WebSocket was already closing during cleanup close.",
                operation=OPERATION_API_SYSTEM_WEBSOCKET_SYSTEM_EVENTS_CLEANUP_WEBSOCKET_CLOSE,
                trace_id=trace_id,
                level="debug",
            )
            return
        log_exception(
            logger,
            runtime_error,
            message="WebSocket close failed with unexpected RuntimeError",
            operation=OPERATION_API_SYSTEM_WEBSOCKET_SYSTEM_EVENTS_CLEANUP_WEBSOCKET_CLOSE,
            trace_id=trace_id,
            level="error",
        )
    except OSError as exception:
        log_handled_exception(
            logger,
            exception,
            message="WebSocket transport closed during cleanup close.",
            operation=OPERATION_API_SYSTEM_WEBSOCKET_SYSTEM_EVENTS_CLEANUP_WEBSOCKET_CLOSE,
            trace_id=trace_id,
            level="debug",
        )


def _describe_event_type(event_type: type[Event]) -> str:
    return event_type.__name__
