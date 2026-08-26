"""SoAI - WebSocket OpenAI audio runtime and upload staging [backend/features/api/routes/system/events/websocket_openai_audio/runtime.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import os
from collections.abc import Awaitable, Callable, Mapping
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.files.temp_files import create_secure_temp_file_descriptor
from core.filesystem.open_files import open_binary
from core.hardware.reservation_claims import claim_reserved_write
from core.serialization.base64_values import decode_base64_ascii
from features.api.routes.system.events.internal_protocols import WebSocketEventTypes
from features.api.routes.system.events.websocket_openai_audio.payloads import (
    build_openai_audio_transcription_error,
)
from features.api.routes.system.events.websocket_openai_run_start_guard import (
    guard_openai_ws_run_start,
)
from features.api.routes.system.events.websocket_run_payloads import (
    require_run_id,
)
from features.api.runtime.event_enqueue import enqueue_event_or_warn
from features.api.streaming.websocket_openai_runtime import (
    OpenAiAudioSpeechRuntime,
    OpenAiAudioSpeechSessionRuntime,
    OpenAiAudioSpeechSessionSegment,
    OpenAiAudioTranscriptionRuntime,
)

if TYPE_CHECKING:
    from core.hardware.protocols_storage import StorageManagerProtocol
    from core.types.json import JSONDict, JSONValue
    from features.api.runtime.container.enqueue_warning_tracker import (
        EnqueueWarningTracker,
    )
    from features.api.streaming.websocket import WebsocketConnection

__all__ = (
    "OpenAiAudioSpeechRuntime",
    "OpenAiAudioSpeechSessionRuntime",
    "OpenAiAudioSpeechSessionSegment",
    "OpenAiAudioTranscriptionRuntime",
    "append_bytes_to_file",
    "create_empty_temp_file",
    "extract_suffix_from_filename",
    "guard_openai_audio_transcription_run_start",
    "require_base64_chunk",
    "require_original_filename",
    "require_run_id",
    "try_resolve_active_transcription_runtime",
    "with_locked_active_transcription_runtime",
)


def try_resolve_active_transcription_runtime(
    *,
    run_id: str,
    connection: WebsocketConnection,
    enqueue_warning_tracker: EnqueueWarningTracker,
) -> tuple[dict[str, OpenAiAudioTranscriptionRuntime], OpenAiAudioTranscriptionRuntime] | None:
    transcriptions = connection.openai_audio_transcriptions
    runtime = transcriptions.get(run_id)
    if runtime is None:
        enqueue_event_or_warn(
            enqueue_warning_tracker,
            connection.queue,
            build_openai_audio_transcription_error(
                run_id=run_id,
                message="Unknown transcription run_id.",
                code="not_found_error",
            ),
            "OpenAI audio transcription error",
        )
        return None
    if runtime.detach_event is not None and runtime.detach_event.is_set():
        return None
    return transcriptions, runtime


async def with_locked_active_transcription_runtime(
    *,
    run_id: str,
    connection: WebsocketConnection,
    enqueue_warning_tracker: EnqueueWarningTracker,
    handler: Callable[
        [dict[str, OpenAiAudioTranscriptionRuntime], OpenAiAudioTranscriptionRuntime],
        Awaitable[None],
    ],
) -> None:
    resolution = try_resolve_active_transcription_runtime(
        run_id=run_id,
        connection=connection,
        enqueue_warning_tracker=enqueue_warning_tracker,
    )
    if resolution is None:
        return
    transcriptions, runtime = resolution
    async with runtime.lock:
        if transcriptions.get(run_id) is not runtime:
            return
        if runtime.detach_event is not None and runtime.detach_event.is_set():
            return
        await handler(transcriptions, runtime)


async def guard_openai_audio_transcription_run_start(
    data: JSONDict,
    *,
    connection: WebsocketConnection,
    enqueue_warning_tracker: EnqueueWarningTracker,
    trace_id: str | None,
) -> str | None:
    return await guard_openai_ws_run_start(
        data,
        connection=connection,
        enqueue_warning_tracker=enqueue_warning_tracker,
        trace_id=trace_id,
        error_event_type=WebSocketEventTypes.OPENAI_AUDIO_TRANSCRIPTION_ERROR,
        build_forbidden_error_payload=build_openai_audio_transcription_error,
        warn_label="OpenAI audio transcription error",
        require_run_id=require_run_id,
    )


def require_original_filename(data: JSONDict) -> str:
    value = data.get("original_filename")
    name = value.strip() if isinstance(value, str) else ""
    if not name:
        raise ValidationError("original_filename is required.")
    return name


def require_base64_chunk(data: JSONDict) -> bytes:
    chunk_value = data.get("chunk_base64")
    if not isinstance(chunk_value, str) or not chunk_value.strip():
        raise ValidationError("chunk_base64 is required.")
    return decode_base64_ascii(chunk_value, error_message="chunk_base64 is invalid base64.")


def extract_suffix_from_filename(original_filename: str) -> str:
    normalized = original_filename.strip()
    if "." not in normalized:
        return ""
    extension = normalized.rsplit(".", 1)[-1].strip()
    if not extension:
        return ""
    safe = "".join(ch for ch in extension if ch.isalnum())
    return f".{safe.lower()}" if safe else ""


def create_empty_temp_file(
    *,
    temp_dir: str,
    suffix: str,
) -> str:
    fd, path = create_secure_temp_file_descriptor(
        directory=temp_dir,
        prefix="soai-",
        suffix=suffix,
    )
    os.close(fd)
    return path


async def append_bytes_to_file(
    *,
    path: str,
    chunk: bytes,
    storage_manager: StorageManagerProtocol,
    operation: str,
    details: Mapping[str, JSONValue] | None = None,
) -> None:
    chunk_length = len(chunk)
    if chunk_length <= 0:
        return
    reservation = storage_manager.reserve_disk_space(
        path=path,
        required_bytes=chunk_length,
        operation=operation,
        details=details,
    )

    def _write() -> None:
        written_total = 0
        with claim_reserved_write(reservation, size_bytes=chunk_length):
            with open_binary(path, mode="ab", buffering=0) as file_handle:
                while written_total < chunk_length:
                    written = file_handle.write(chunk[written_total:])
                    if written is None or written <= 0:
                        raise OSError("Failed to append audio upload bytes.")
                    written_total += written

    try:
        await asyncio.to_thread(_write)
    finally:
        reservation.release()
