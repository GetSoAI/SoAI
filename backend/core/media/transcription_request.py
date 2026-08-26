"""SoAI - Canonical media transcription request [backend/core/media/transcription_request.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.media.cancellation import await_media_operation

if TYPE_CHECKING:
    from core.files.types import ParseExecutionContext, ParseProgressCallback
    from core.media.protocols import MediaTranscriptionRuntimeProtocol
    from core.media.types import TranscriptionResult

__all__ = ("request_media_transcription",)


async def request_media_transcription(
    runtime: MediaTranscriptionRuntimeProtocol,
    *,
    context: ParseExecutionContext,
    duration_seconds: float,
    model_name: str,
    progress_callback: ParseProgressCallback | None,
) -> TranscriptionResult:
    return await await_media_operation(
        runtime.transcribe(
            source_path=context.source_path,
            duration_seconds=duration_seconds,
            model_name=model_name,
            language=None,
            task="transcribe",
            include_word_timestamps=False,
            extraction_deadline=context.extraction_deadline,
            progress_callback=progress_callback,
        ),
        context.cancellation_token,
        extraction_deadline=context.extraction_deadline,
    )
