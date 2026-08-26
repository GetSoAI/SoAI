"""SoAI - WebSocket OpenAI transcription upload chunk handlers [backend/features/api/routes/system/events/websocket_openai_audio/transcription_upload_chunks.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.config.upload_limits import UploadLimitType, resolve_upload_limit_bytes
from core.errors.exception_logging import log_exception
from core.errors.exceptions import InsufficientDiskSpaceError, ValidationError
from core.files.upload_staging import cleanup_temp_file
from core.logging.trace import get_logger
from core.state.access import AccessAction
from features.api.routes.system.events.websocket_openai_audio.payloads import (
    build_openai_audio_transcription_cancelled,
    build_openai_audio_transcription_error,
)
from features.api.routes.system.events.websocket_openai_audio.runtime import (
    append_bytes_to_file,
    require_base64_chunk,
    require_run_id,
    with_locked_active_transcription_runtime,
)
from features.api.routes.system.events.websocket_openai_cancel_handling import (
    handle_openai_ws_cancel_with_lock,
)
from features.api.routes.system.events.websocket_openai_runtime_cancellation import (
    cancel_openai_ws_active_task_runtime,
)
from features.api.routes.system.events.websocket_run_payloads import (
    require_non_negative_sequence,
    resolve_run_id,
)
from features.api.runtime.event_enqueue import enqueue_event_or_warn

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from features.api.routes.system.events.websocket_openai_audio.runtime import (
        OpenAiAudioTranscriptionRuntime,
    )
    from features.api.runtime.container.enqueue_warning_tracker import (
        EnqueueWarningTracker,
    )
    from features.api.runtime.context import ApiContext
    from features.api.streaming.websocket import WebsocketConnection

__all__ = (
    "handle_openai_audio_transcription_cancel",
    "handle_openai_audio_transcription_chunk",
)

LOGGER_NAME = "SoAI.features.api.transcription_upload_chunks"
OPERATION_TRANSCRIPTION_CANCEL = "api_system.websocket.openai_audio.transcription.cancel"
OPERATION_TRANSCRIPTION_CHUNK_APPEND = (
    "api_system.websocket.openai_audio.transcription.chunk.append"
)


async def handle_openai_audio_transcription_chunk(
    data: JSONDict,
    *,
    connection: WebsocketConnection,
    api_context: ApiContext,
    enqueue_warning_tracker: EnqueueWarningTracker,
    trace_id: str | None,
) -> None:
    if AccessAction.OPENAI_API not in connection.granted_actions:
        return
    try:
        run_id = require_run_id(data)
        sequence = require_non_negative_sequence(data)
        chunk = require_base64_chunk(data)
    except ValidationError as exception:
        run_id_value = resolve_run_id(data) or ""
        enqueue_event_or_warn(
            enqueue_warning_tracker,
            connection.queue,
            build_openai_audio_transcription_error(
                run_id=run_id_value,
                message=exception.message,
                code="invalid_request_error",
            ),
            "OpenAI audio transcription error",
        )
        return

    async def _handle_locked_transcription(
        transcriptions: dict[str, OpenAiAudioTranscriptionRuntime],
        runtime: OpenAiAudioTranscriptionRuntime,
    ) -> None:
        if runtime.state != "uploading":
            enqueue_event_or_warn(
                enqueue_warning_tracker,
                connection.queue,
                build_openai_audio_transcription_error(
                    run_id=run_id,
                    message="Transcription upload is no longer accepting chunks.",
                    code="conflict_error",
                ),
                "OpenAI audio transcription error",
            )
            return
        if sequence != runtime.next_sequence:
            enqueue_event_or_warn(
                enqueue_warning_tracker,
                connection.queue,
                build_openai_audio_transcription_error(
                    run_id=run_id,
                    message="Out-of-order transcription upload chunk.",
                    code="conflict_error",
                ),
                "OpenAI audio transcription error",
            )
            return
        max_upload_bytes = resolve_upload_limit_bytes(
            api_context.dependencies.config,
            UploadLimitType.AUDIO,
        )
        new_total = runtime.received_bytes + len(chunk)
        if new_total > max_upload_bytes:
            runtime.state = "cancelled"
            if runtime.detach_event is not None:
                runtime.detach_event.set()
            await cleanup_temp_file(runtime.temp_path)
            if transcriptions.get(run_id) is runtime:
                transcriptions.pop(run_id, None)
            enqueue_event_or_warn(
                enqueue_warning_tracker,
                connection.queue,
                build_openai_audio_transcription_error(
                    run_id=run_id,
                    message="Audio upload exceeded configured limit.",
                    code="invalid_request_error",
                ),
                "OpenAI audio transcription error",
            )
            return
        try:
            await append_bytes_to_file(
                path=runtime.temp_path,
                chunk=chunk,
                storage_manager=api_context.dependencies.storage_manager,
                operation=OPERATION_TRANSCRIPTION_CHUNK_APPEND,
                details={
                    "run_id": run_id,
                    "temp_path": runtime.temp_path,
                    "chunk_bytes": len(chunk),
                    "received_bytes": runtime.received_bytes,
                },
            )
        except (InsufficientDiskSpaceError, OSError) as exception:
            logger = get_logger(LOGGER_NAME)
            log_exception(
                logger,
                exception,
                message="Failed appending audio upload chunk.",
                operation=OPERATION_TRANSCRIPTION_CHUNK_APPEND,
                trace_id=trace_id,
                level="error",
            )
            runtime.state = "failed"
            if runtime.detach_event is not None:
                runtime.detach_event.set()
            await cleanup_temp_file(runtime.temp_path)
            if transcriptions.get(run_id) is runtime:
                transcriptions.pop(run_id, None)
            if isinstance(exception, InsufficientDiskSpaceError):
                error_message = str(exception.message)
                error_code = str(exception.code)
            else:
                error_message = "Failed writing upload chunk."
                error_code = "server_error"
            enqueue_event_or_warn(
                enqueue_warning_tracker,
                connection.queue,
                build_openai_audio_transcription_error(
                    run_id=run_id,
                    message=error_message,
                    code=error_code,
                ),
                "OpenAI audio transcription error",
            )
            return
        runtime.received_bytes = new_total
        runtime.next_sequence += 1

    await with_locked_active_transcription_runtime(
        run_id=run_id,
        connection=connection,
        enqueue_warning_tracker=enqueue_warning_tracker,
        handler=_handle_locked_transcription,
    )


async def handle_openai_audio_transcription_cancel(
    data: JSONDict,
    *,
    connection: WebsocketConnection,
    api_context: ApiContext,
    enqueue_warning_tracker: EnqueueWarningTracker,
) -> None:
    async def cancel_runtime(runtime: OpenAiAudioTranscriptionRuntime, reason: str) -> None:
        runtime.state = "cancelled"
        cancel_openai_ws_active_task_runtime(
            runtime=runtime,
            api_context=api_context,
            connection=connection,
            reason=reason,
            operation=OPERATION_TRANSCRIPTION_CANCEL,
            logger=get_logger(LOGGER_NAME),
        )
        await cleanup_temp_file(runtime.temp_path)

    await handle_openai_ws_cancel_with_lock(
        data,
        connection=connection,
        enqueue_warning_tracker=enqueue_warning_tracker,
        require_run_id=require_run_id,
        runtimes=connection.openai_audio_transcriptions,
        cancel_runtime=cancel_runtime,
        build_cancelled_event=lambda run_id, reason: build_openai_audio_transcription_cancelled(
            run_id=run_id,
            reason=reason,
        ),
        warn_label="OpenAI audio transcription cancelled",
    )
