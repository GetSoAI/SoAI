"""SoAI - WebSocket OpenAI speech handlers [backend/features/api/routes/system/events/websocket_openai_audio/speech_handlers.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.exceptions import SoAIError
from core.events.types_models_requests import TextToSpeechRequestReceived
from core.logging.trace import get_logger
from core.orchestrator.protocols_lifecycle import InferenceAdmissionRequest
from core.runtime.protocols import RequestProtocol
from core.runtime.request_context_cloning import clone_request_context
from core.runtime.request_sources import REQUEST_SOURCE_WEBUI_WS
from core.runtime.soai_identifiers import create_system_id
from core.tasks.type_catalog import TASK_TYPE_TEXT_TO_SPEECH
from core.timing.monotonic import monotonic_ms
from core.types.json_value import coerce_json_dict
from core.users.user_id import coerce_user_id
from features.api.routes.system.events.internal_protocols import WebSocketEventTypes
from features.api.routes.system.events.websocket_openai_audio.payloads import (
    build_openai_audio_speech_cancelled,
    build_openai_audio_speech_error,
    build_openai_audio_speech_started,
)
from features.api.routes.system.events.websocket_openai_audio.runtime import (
    OpenAiAudioSpeechRuntime,
    require_run_id,
)
from features.api.routes.system.events.websocket_openai_audio.speech_runner import (
    run_openai_audio_speech_stream,
)
from features.api.routes.system.events.websocket_openai_cancel_handling import (
    handle_openai_ws_cancel,
)
from features.api.routes.system.events.websocket_openai_run_start_guard import (
    guard_openai_ws_run_start,
)
from features.api.routes.system.events.websocket_openai_runner_failure_handling import (
    resolve_openai_ws_reply_queue_or_enqueue_unavailable,
)
from features.api.routes.system.events.websocket_openai_runtime_cancellation import (
    cancel_openai_ws_speech_runtime,
)
from features.api.runtime.event_enqueue import enqueue_event_or_warn
from features.api.runtime.openai_tts_request_preparation import (
    prepare_text_to_speech_request,
)
from features.api.schemas.openai_audio import WebuiTextToSpeechRequest

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from features.api.runtime.container.enqueue_warning_tracker import (
        EnqueueWarningTracker,
    )
    from features.api.runtime.context import ApiContext
    from features.api.streaming.types import StreamDependencies
    from features.api.streaming.websocket import WebsocketConnection

__all__ = (
    "handle_openai_audio_speech_cancel",
    "handle_openai_audio_speech_start",
)

LOGGER_NAME = "SoAI.features.api.speech_handlers"
OPERATION_SPEECH_VALIDATE = "api_system.websocket.openai_audio.speech.validate"
OPERATION_SPEECH_CANCEL = "api_system.websocket.openai_audio.speech.cancel"


async def handle_openai_audio_speech_start(
    data: JSONDict,
    *,
    connection: WebsocketConnection,
    request: RequestProtocol,
    api_context: ApiContext,
    stream_dependencies: StreamDependencies,
    enqueue_warning_tracker: EnqueueWarningTracker,
    trace_id: str | None,
    shutdown_event: asyncio.Event,
) -> None:
    logger = get_logger(LOGGER_NAME)

    run_id = await guard_openai_ws_run_start(
        data,
        connection=connection,
        enqueue_warning_tracker=enqueue_warning_tracker,
        trace_id=trace_id,
        error_event_type=WebSocketEventTypes.OPENAI_AUDIO_SPEECH_ERROR,
        build_forbidden_error_payload=build_openai_audio_speech_error,
        warn_label="OpenAI audio speech error",
        require_run_id=require_run_id,
    )
    if run_id is None:
        return
    speech_streams = connection.openai_audio_speech_streams
    if run_id in speech_streams:
        enqueue_event_or_warn(
            enqueue_warning_tracker,
            connection.queue,
            build_openai_audio_speech_error(
                run_id=run_id,
                message="Speech run_id already exists.",
                code="conflict_error",
            ),
            "OpenAI audio speech error",
        )
        return
    payload_value = coerce_json_dict(data.get("payload"))
    if payload_value is None:
        payload_value = data
    try:
        tts_payload = WebuiTextToSpeechRequest.model_validate(payload_value)
        prepared = await prepare_text_to_speech_request(
            api_context=api_context,
            request=tts_payload,
            include_input=True,
        )
    except (SoAIError, ValueError) as exception:
        coerced = coerce_to_soai_error(exception, operation=OPERATION_SPEECH_VALIDATE)
        log_exception(
            logger,
            exception,
            message="Invalid OpenAI speech request payload (non-critical).",
            operation=OPERATION_SPEECH_VALIDATE,
            trace_id=trace_id,
            level="debug",
        )
        enqueue_event_or_warn(
            enqueue_warning_tracker,
            connection.queue,
            build_openai_audio_speech_error(
                run_id=run_id,
                message=str(coerced),
                code=str(coerced.code),
            ),
            "OpenAI audio speech error",
        )
        return
    context = clone_request_context(request.state.context, task_id=None)
    user_id = coerce_user_id(context.user_id)
    cancellation_id = create_system_id(
        subsystem="ws_openai_tts",
        owner=run_id,
        include_random_suffix=True,
    )
    receipt = await api_context.dependencies.orchestrator_control.accept_inference_request(
        InferenceAdmissionRequest(
            request_context=context,
            payload=prepared.payload,
            task_type=TASK_TYPE_TEXT_TO_SPEECH,
            user_id=user_id,
            owner_type="system",
            owner_id=run_id,
            cancellation_id=cancellation_id,
            metadata={
                "run_id": run_id,
                "openai_audio_speech": True,
                "media_type": prepared.media_type,
            },
            request_event_class=TextToSpeechRequestReceived,
            request_source=REQUEST_SOURCE_WEBUI_WS,
            required_capabilities=("audio_speech",),
            required_modalities=(),
            delivery_mode="streaming",
            attach_reply_queue=True,
        ),
    )
    reply_queue = resolve_openai_ws_reply_queue_or_enqueue_unavailable(
        receipt=receipt,
        enqueue_warning_tracker=enqueue_warning_tracker,
        queue=connection.queue,
        warn_label="OpenAI audio speech error",
        build_error_payload=build_openai_audio_speech_error,
        run_id=run_id,
        message="Speech reply channel is not available.",
    )
    if reply_queue is None:
        return
    task = receipt.task
    runtime = OpenAiAudioSpeechRuntime(
        run_id=run_id,
        user_id=user_id,
        started_at_ms=monotonic_ms(),
        task_id=task.task_id,
        detach_event=asyncio.Event(),
        runner_task=None,
    )
    speech_streams[run_id] = runtime
    runner_task = api_context.dependencies.application_control.schedule_background_task(
        run_openai_audio_speech_stream(
            run_id=run_id,
            runtime=runtime,
            connection=connection,
            reply_queue=reply_queue,
            stream_dependencies=stream_dependencies,
            request_context=context,
            enqueue_warning_tracker=enqueue_warning_tracker,
            trace_id=trace_id,
            shutdown_event=shutdown_event,
        ),
        name=f"ws_openai_audio_speech:{run_id}",
    )
    if runner_task is None:
        if speech_streams.get(run_id) is runtime:
            speech_streams.pop(run_id, None)
        enqueue_event_or_warn(
            enqueue_warning_tracker,
            connection.queue,
            build_openai_audio_speech_error(
                run_id=run_id,
                message="Speech runner could not be scheduled.",
                code="server_error",
                task_id=task.task_id,
            ),
            "OpenAI audio speech error",
        )
        return
    runtime.runner_task = runner_task
    enqueue_event_or_warn(
        enqueue_warning_tracker,
        connection.queue,
        build_openai_audio_speech_started(
            run_id=run_id,
            task_id=task.task_id,
            media_type=prepared.media_type,
        ),
        "OpenAI audio speech started",
    )


async def handle_openai_audio_speech_cancel(
    data: JSONDict,
    *,
    connection: WebsocketConnection,
    api_context: ApiContext,
    enqueue_warning_tracker: EnqueueWarningTracker,
) -> None:
    def cancel_runtime(runtime: OpenAiAudioSpeechRuntime, reason: str) -> None:
        cancel_openai_ws_speech_runtime(
            runtime=runtime,
            api_context=api_context,
            connection=connection,
            reason=reason,
            operation=OPERATION_SPEECH_CANCEL,
            logger=get_logger(LOGGER_NAME),
        )

    await handle_openai_ws_cancel(
        data,
        connection=connection,
        enqueue_warning_tracker=enqueue_warning_tracker,
        require_run_id=require_run_id,
        runtimes=connection.openai_audio_speech_streams,
        cancel_runtime=cancel_runtime,
        build_cancelled_event=lambda run_id, reason: build_openai_audio_speech_cancelled(
            run_id=run_id,
            reason=reason,
        ),
        warn_label="OpenAI audio speech cancelled",
    )
