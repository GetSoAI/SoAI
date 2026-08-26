"""SoAI - WebSocket OpenAI speech session task admission [backend/features/api/routes/system/events/websocket_openai_audio/speech_session_tasks.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.events.types_models_requests import TextToSpeechRequestReceived
from core.logging.trace import get_logger
from core.orchestrator.protocols_lifecycle import InferenceAdmissionRequest
from core.runtime.request_sources import REQUEST_SOURCE_WEBUI_WS
from core.runtime.soai_identifiers import create_system_id
from core.tasks.type_catalog import TASK_TYPE_TEXT_TO_SPEECH
from core.types.json_value import coerce_json_dict
from features.api.routes.system.events.websocket_openai_audio.payloads import (
    build_openai_audio_speech_session_error,
)
from features.api.routes.system.events.websocket_openai_audio.speech_session_errors import (
    OPERATION_WS_OPENAI_AUDIO_SPEECH_SESSION,
)
from features.api.routes.system.events.websocket_openai_runner_failure_handling import (
    resolve_openai_ws_reply_queue_or_enqueue_unavailable,
)
from features.api.streaming.stream_cancel import schedule_streaming_task_cancel

if TYPE_CHECKING:
    import asyncio

    from core.events.types_base import Event
    from core.runtime.request_context import RequestContext
    from core.types.json import JSONDict
    from features.api.runtime.container.enqueue_warning_tracker import (
        EnqueueWarningTracker,
    )
    from features.api.runtime.context import ApiContext
    from features.api.streaming.websocket import WebsocketConnection

__all__ = ("accept_speech_session_segment_task",)

LOGGER_NAME = "SoAI.features.api.speech_session_tasks"


async def accept_speech_session_segment_task(
    *,
    api_context: ApiContext,
    connection: WebsocketConnection,
    enqueue_warning_tracker: EnqueueWarningTracker,
    request_context: RequestContext,
    run_id: str,
    user_id: int,
    session_payload: JSONDict,
    segment_sequence: int,
    input_text: str,
) -> tuple[str, asyncio.Queue[Event]] | None:
    payload_dict = dict(session_payload)
    payload_dict["input"] = input_text
    cancellation_id = create_system_id(
        subsystem="ws_openai_tts_session",
        owner=f"{run_id}:{segment_sequence}",
        include_random_suffix=True,
    )
    request_payload = coerce_json_dict(payload_dict) or {}
    admission_request = InferenceAdmissionRequest(
        request_context=request_context,
        payload=request_payload,
        metadata={
            "run_id": run_id,
            "segment_sequence": segment_sequence,
            "voice_call_session": True,
        },
        task_type=TASK_TYPE_TEXT_TO_SPEECH,
        user_id=user_id,
        owner_type="system",
        owner_id=run_id,
        cancellation_id=cancellation_id,
        request_event_class=TextToSpeechRequestReceived,
        request_source=REQUEST_SOURCE_WEBUI_WS,
        required_capabilities=("audio_speech",),
        required_modalities=(),
        delivery_mode="streaming",
        attach_reply_queue=True,
    )
    receipt = await api_context.dependencies.orchestrator_control.accept_inference_request(
        admission_request,
    )
    reply_queue = resolve_openai_ws_reply_queue_or_enqueue_unavailable(
        receipt=receipt,
        enqueue_warning_tracker=enqueue_warning_tracker,
        queue=connection.queue,
        warn_label="OpenAI audio speech session error",
        build_error_payload=build_openai_audio_speech_session_error,
        run_id=run_id,
        message="Speech session reply channel is not available.",
    )
    if reply_queue is None:
        schedule_streaming_task_cancel(
            registry=api_context.dependencies.task_registry,
            task_id=receipt.task.task_id,
            reason="Speech session reply channel is not available.",
            context=connection.request.state.context,
            logger=get_logger(LOGGER_NAME),
            operation=OPERATION_WS_OPENAI_AUDIO_SPEECH_SESSION,
            track_background_task=api_context.dependencies.application_control.track_background_task,
        )
        return None
    return receipt.task.task_id, reply_queue
