"""SoAI - WebSocket OpenAI transcription upload start handler [backend/features/api/routes/system/events/websocket_openai_audio/transcription_upload_start.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from core.config.upload_limits import UploadLimitType, resolve_upload_limit_bytes
from core.errors.exception_logging import log_exception
from core.errors.exceptions import ValidationError
from core.files.upload_policy import resolve_temp_directory_runtime
from core.files.upload_staging import cleanup_temp_file
from core.logging.trace import get_logger
from core.openai.audio_upload_fields import OPENAI_AUDIO_TRANSCRIPTION_ALLOWED_FIELDS
from core.runtime.protocols import RequestProtocol
from core.timing.monotonic import monotonic_ms
from core.users.user_id import coerce_user_id
from features.api.routes.multipart_field_mapping import (
    build_multipart_style_fields_from_payload,
)
from features.api.routes.system.events.internal_protocols import WebSocketEventTypes
from features.api.routes.system.events.websocket_errors import enqueue_websocket_error
from features.api.routes.system.events.websocket_openai_audio.payloads import (
    build_openai_audio_transcription_error,
)
from features.api.routes.system.events.websocket_openai_audio.runtime import (
    OpenAiAudioTranscriptionRuntime,
    create_empty_temp_file,
    extract_suffix_from_filename,
    guard_openai_audio_transcription_run_start,
    require_original_filename,
)
from features.api.routes.system.events.websocket_openai_audio.transcription_command_building import (
    reject_webui_transcription_stream_field,
)
from features.api.runtime.event_enqueue import enqueue_event_or_warn

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from features.api.runtime.container.enqueue_warning_tracker import (
        EnqueueWarningTracker,
    )
    from features.api.runtime.context import ApiContext
    from features.api.streaming.websocket import WebsocketConnection

__all__ = ("handle_openai_audio_transcription_start",)

LOGGER_NAME = "SoAI.features.api.transcription_upload_start"
OPERATION_TRANSCRIPTION_START_CREATE_TEMP = (
    "api_system.websocket.openai_audio.transcription.start.create_temp"
)


async def handle_openai_audio_transcription_start(
    data: JSONDict,
    *,
    connection: WebsocketConnection,
    request: RequestProtocol,
    api_context: ApiContext,
    enqueue_warning_tracker: EnqueueWarningTracker,
    trace_id: str | None,
) -> None:
    logger = get_logger(LOGGER_NAME)

    run_id = await guard_openai_audio_transcription_run_start(
        data,
        connection=connection,
        enqueue_warning_tracker=enqueue_warning_tracker,
        trace_id=trace_id,
    )
    if run_id is None:
        return
    try:
        reject_webui_transcription_stream_field(data)
        original_filename = require_original_filename(data)
    except ValidationError as exception:
        await enqueue_websocket_error(
            enqueue_warning_tracker,
            connection.queue,
            trace_id,
            WebSocketEventTypes.OPENAI_AUDIO_TRANSCRIPTION_ERROR,
            exception.message,
            code="invalid_request_error",
            run_id=run_id,
        )
        return
    transcriptions = connection.openai_audio_transcriptions
    if run_id in transcriptions:
        enqueue_event_or_warn(
            enqueue_warning_tracker,
            connection.queue,
            build_openai_audio_transcription_error(
                run_id=run_id,
                message="Transcription run_id already exists.",
                code="conflict_error",
            ),
            "OpenAI audio transcription error",
        )
        return
    max_upload_bytes = resolve_upload_limit_bytes(
        api_context.dependencies.config,
        UploadLimitType.AUDIO,
    )
    if max_upload_bytes <= 0:
        enqueue_event_or_warn(
            enqueue_warning_tracker,
            connection.queue,
            build_openai_audio_transcription_error(
                run_id=run_id,
                message="Audio uploads are disabled.",
                code="feature_disabled",
            ),
            "OpenAI audio transcription error",
        )
        return
    temp_dir = resolve_temp_directory_runtime(api_context.dependencies.config)
    suffix = extract_suffix_from_filename(original_filename)
    try:
        temp_path = create_empty_temp_file(temp_dir=temp_dir, suffix=suffix)
    except OSError as exception:
        log_exception(
            logger,
            exception,
            message="Failed to create audio transcription temp file.",
            operation=OPERATION_TRANSCRIPTION_START_CREATE_TEMP,
        )
        enqueue_event_or_warn(
            enqueue_warning_tracker,
            connection.queue,
            build_openai_audio_transcription_error(
                run_id=run_id,
                message="Failed to allocate upload space.",
                code="server_error",
            ),
            "OpenAI audio transcription error",
        )
        return
    try:
        fields = build_multipart_style_fields_from_payload(
            payload=data,
            allowed_fields=OPENAI_AUDIO_TRANSCRIPTION_ALLOWED_FIELDS,
        )
    except ValidationError as exception:
        await cleanup_temp_file(temp_path)
        error_payload = build_openai_audio_transcription_error(
            run_id=run_id,
            message=exception.message,
            code="invalid_request_error",
        )
        enqueue_event_or_warn(
            enqueue_warning_tracker,
            connection.queue,
            error_payload,
            "OpenAI audio transcription error",
        )
        return
    model_values = fields.get("model")
    model_id = model_values[0] if isinstance(model_values, tuple) and model_values else ""
    if not model_id:
        await cleanup_temp_file(temp_path)
        enqueue_event_or_warn(
            enqueue_warning_tracker,
            connection.queue,
            build_openai_audio_transcription_error(
                run_id=run_id,
                message="Missing required field 'model'.",
                code="invalid_request_error",
            ),
            "OpenAI audio transcription error",
        )
        return
    transcriptions[run_id] = OpenAiAudioTranscriptionRuntime(
        run_id=run_id,
        user_id=coerce_user_id(request.state.context.user_id),
        started_at_ms=monotonic_ms(),
        original_filename=original_filename,
        temp_path=temp_path,
        fields=fields,
        received_bytes=0,
        next_sequence=0,
        active_task_id=None,
        detach_event=asyncio.Event(),
        runner_task=None,
        lock=asyncio.Lock(),
        state="uploading",
        sealed_bytes=0,
    )
