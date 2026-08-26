"""SoAI - WebSocket OpenAI transcription runner [backend/features/api/routes/system/events/websocket_openai_audio/transcription_runner.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.exceptions import ValidationError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.events.types_models_requests import AudioTranscriptionRequestReceived
from core.files.content_hashing import hash_file_content
from core.files.upload_staging import cleanup_temp_file
from core.logging.protocols import LoggerProtocol
from core.logging.trace import get_logger
from core.runtime.request_context_cloning import clone_request_context
from core.runtime.request_sources import REQUEST_SOURCE_WEBUI_WS
from core.tasks.creation import create_streaming_task
from core.tasks.enums import TaskStatus
from core.tasks.finalization import finalize
from core.types.json import JSONValue
from core.users.user_id import coerce_user_id
from features.api.routes.openai.audio_upload_payloads import (
    build_openai_audio_upload_payloads,
)
from features.api.routes.system.events.websocket_openai_audio.payloads import (
    build_openai_audio_transcription_completed,
    build_openai_audio_transcription_error,
    build_openai_audio_transcription_started,
)
from features.api.routes.system.events.websocket_openai_audio.transcription_command_building import (
    build_audio_transcription_request_received,
)
from features.api.routes.system.events.websocket_openai_audio.transcription_result_collection import (
    collect_openai_transcription_result,
)
from features.api.routes.system.events.websocket_openai_runner_failure_handling import (
    enqueue_openai_ws_runner_error_payload,
    openai_ws_detach_event_is_set,
)
from features.api.routes.upload_streaming_multipart_models import StreamingStagedPart
from features.api.runtime.event_enqueue import enqueue_event_or_warn
from features.api.runtime.openai_audio_model_resolution import (
    resolve_audio_upload_model_fields,
)

if TYPE_CHECKING:
    from core.events.types_base import Event
    from core.runtime.request_context import RequestContext
    from features.api.routes.system.events.websocket_openai_audio.runtime import (
        OpenAiAudioTranscriptionRuntime,
    )
    from features.api.runtime.container.enqueue_warning_tracker import (
        EnqueueWarningTracker,
    )
    from features.api.runtime.context import ApiContext
    from features.api.streaming.websocket import WebsocketConnection

__all__ = ("run_openai_audio_transcription",)

LOGGER_NAME = "SoAI.features.api.transcription_runner"
OPERATION_TRANSCRIPTION_COLLECT = "api_system.websocket.openai_audio.transcription.collect"
OPERATION_TRANSCRIPTION_PUBLISH = "api_system.websocket.openai_audio.transcription.publish"


async def _collect_transcription_result_or_emit_error(
    *,
    runtime: OpenAiAudioTranscriptionRuntime,
    run_id: str,
    task_id: str,
    api_context: ApiContext,
    reply_queue: asyncio.Queue[Event],
    enqueue_warning_tracker: EnqueueWarningTracker,
    connection: WebsocketConnection,
    trace_id: str | None,
    logger: LoggerProtocol,
) -> JSONValue | None:
    try:
        return await collect_openai_transcription_result(
            registry=api_context.dependencies.task_registry,
            task_id=task_id,
            reply_queue=reply_queue,
            timeout_seconds=60.0,
        )
    except asyncio.CancelledError:
        if openai_ws_detach_event_is_set(runtime.detach_event):
            return None
        raise
    except RECOVERABLE_EXCEPTIONS as exception:
        if openai_ws_detach_event_is_set(runtime.detach_event):
            return None
        coerced = coerce_to_soai_error(
            exception,
            operation=OPERATION_TRANSCRIPTION_COLLECT,
        )
        log_exception(
            logger,
            exception,
            message="OpenAI transcription result collection failed.",
            operation=OPERATION_TRANSCRIPTION_COLLECT,
            trace_id=trace_id,
            level="error",
        )
        enqueue_openai_ws_runner_error_payload(
            coerced=coerced,
            enqueue_warning_tracker=enqueue_warning_tracker,
            queue=connection.queue,
            warn_label="OpenAI audio transcription error",
            build_error_payload=build_openai_audio_transcription_error,
            run_id=run_id,
            task_id=task_id,
        )
        return None


async def run_openai_audio_transcription(
    *,
    run_id: str,
    runtime: OpenAiAudioTranscriptionRuntime,
    transcriptions: dict[str, OpenAiAudioTranscriptionRuntime],
    connection: WebsocketConnection,
    request_context: RequestContext,
    api_context: ApiContext,
    enqueue_warning_tracker: EnqueueWarningTracker,
    trace_id: str | None,
) -> None:
    logger = get_logger(LOGGER_NAME)
    try:
        context = clone_request_context(request_context, task_id=None)
        user_id = coerce_user_id(context.user_id)
        task_type = api_context.dependencies.task_type_routing_service.get_task_type_for_command(
            AudioTranscriptionRequestReceived,
        )
        task, reply_queue = await create_streaming_task(
            api_context.dependencies.task_registry,
            task_type=task_type,
            user_id=user_id,
            owner_id=run_id,
            owner_type="system",
            task_id=None,
            cancellation_id=context.cancellation_id,
            initial_status=TaskStatus.QUEUED,
            progress_total=None,
            metadata={"run_id": run_id, "openai_audio_transcription": True},
            request_source=REQUEST_SOURCE_WEBUI_WS,
            delivery_mode="streaming",
        )
        context.task_id = task.task_id
        runtime.active_task_id = task.task_id
        try:
            content_hash = await asyncio.to_thread(hash_file_content, runtime.temp_path)
            staged_part = StreamingStagedPart(
                field_name="file",
                original_filename=runtime.original_filename,
                temp_path=runtime.temp_path,
                size_bytes=int(runtime.sealed_bytes),
                content_sha256=content_hash.sha256_hex,
            )
            fields = await resolve_audio_upload_model_fields(
                api_context=api_context,
                fields=runtime.fields,
                endpoint_capability="audio_transcriptions",
                unavailable_message="No transcription models available. Configure/install a plugin or provider that supports OpenAI audio transcriptions.",
            )
            payloads = build_openai_audio_upload_payloads(
                event_type=AudioTranscriptionRequestReceived,
                staged_part=staged_part,
                fields=fields,
                required_capabilities=("audio_transcriptions",),
            )
            cmd = build_audio_transcription_request_received(
                reply_queue=reply_queue,
                context=context,
                command_fields=payloads.command_fields,
            )
        except ValidationError as exception:
            await finalize(
                api_context.dependencies.task_registry,
                task.task_id,
                TaskStatus.FAILED,
                error_code=400,
                error_message=exception.message,
            )
            enqueue_event_or_warn(
                enqueue_warning_tracker,
                connection.queue,
                build_openai_audio_transcription_error(
                    run_id=run_id,
                    message=exception.message,
                    code="invalid_request_error",
                    task_id=task.task_id,
                ),
                "OpenAI audio transcription error",
            )
            return
        try:
            await api_context.dependencies.event_bus.publish(cmd)
        except RECOVERABLE_EXCEPTIONS as exception:
            log_exception(
                logger,
                exception,
                message="Failed to publish transcription command.",
                operation=OPERATION_TRANSCRIPTION_PUBLISH,
                trace_id=trace_id,
                level="error",
            )
            await finalize(
                api_context.dependencies.task_registry,
                task.task_id,
                TaskStatus.FAILED,
                error_code=500,
                error_message="Failed to dispatch request.",
            )
            enqueue_event_or_warn(
                enqueue_warning_tracker,
                connection.queue,
                build_openai_audio_transcription_error(
                    run_id=run_id,
                    message="Failed to dispatch transcription request.",
                    code="server_error",
                    task_id=task.task_id,
                ),
                "OpenAI audio transcription error",
            )
            return
        enqueue_event_or_warn(
            enqueue_warning_tracker,
            connection.queue,
            build_openai_audio_transcription_started(run_id=run_id, task_id=task.task_id),
            "OpenAI audio transcription started",
        )
        result = await _collect_transcription_result_or_emit_error(
            runtime=runtime,
            run_id=run_id,
            task_id=task.task_id,
            api_context=api_context,
            reply_queue=reply_queue,
            enqueue_warning_tracker=enqueue_warning_tracker,
            connection=connection,
            trace_id=trace_id,
            logger=logger,
        )
        if result is None:
            return
        enqueue_event_or_warn(
            enqueue_warning_tracker,
            connection.queue,
            build_openai_audio_transcription_completed(
                run_id=run_id,
                task_id=task.task_id,
                result=result,
            ),
            "OpenAI audio transcription completed",
        )
    finally:
        async with runtime.lock:
            if runtime.state not in {"cancelled", "failed"}:
                runtime.state = "finished"
            await cleanup_temp_file(runtime.temp_path)
            if transcriptions.get(run_id) is runtime:
                transcriptions.pop(run_id, None)
