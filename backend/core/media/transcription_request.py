"""SoAI - Canonical media transcription request [backend/core/media/transcription_request.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.media.cancellation import await_media_operation
from core.media.speech_errors import SPEECH_TO_TEXT_CAPABILITY, SpeechToTextUnavailableError
from core.media.speech_setup import SpeechTask
from core.media.transcription_contracts import (
    MediaTranscriptionRequest,
    SpeechTranscriptionOptions,
)
from core.media.types import TranscriptionResult

if TYPE_CHECKING:
    from core.files.types import ParseExecutionContext, ParseProgressCallback
    from core.media.protocols import MediaTranscriptionRuntimeProtocol

__all__ = (
    "DocumentTranscription",
    "request_document_transcription",
    "request_media_transcription",
)

_SPEECH_NOT_TRANSCRIBED = "Speech not transcribed"


@dataclass(frozen=True, slots=True)
class DocumentTranscription:
    result: TranscriptionResult
    setup_warning: str | None

    @property
    def missing_capabilities(self) -> tuple[str, ...]:
        return (SPEECH_TO_TEXT_CAPABILITY,) if self.setup_warning is not None else ()


async def request_media_transcription(
    runtime: MediaTranscriptionRuntimeProtocol,
    *,
    context: ParseExecutionContext,
    duration_seconds: float,
    selector: str,
    progress_callback: ParseProgressCallback | None,
) -> TranscriptionResult:
    return await await_media_operation(
        runtime.transcribe(
            MediaTranscriptionRequest(
                source_path=context.source_path,
                duration_seconds=duration_seconds,
                selector=selector,
                options=SpeechTranscriptionOptions(
                    task=SpeechTask.TRANSCRIBE,
                    language=None,
                    include_word_timestamps=False,
                ),
                request_context=context.request_context,
                extraction_deadline=context.extraction_deadline,
                progress_callback=progress_callback,
            ),
        ),
        context.cancellation_token,
        extraction_deadline=context.extraction_deadline,
    )


async def request_document_transcription(
    runtime: MediaTranscriptionRuntimeProtocol,
    *,
    context: ParseExecutionContext,
    duration_seconds: float,
    selector: str,
    progress_callback: ParseProgressCallback | None,
) -> DocumentTranscription:
    try:
        result = await request_media_transcription(
            runtime,
            context=context,
            duration_seconds=duration_seconds,
            selector=selector,
            progress_callback=progress_callback,
        )
    except SpeechToTextUnavailableError as error:
        return DocumentTranscription(
            result=TranscriptionResult(text="", language=None, segments=()),
            setup_warning=f"{_SPEECH_NOT_TRANSCRIBED}: {error.message}",
        )
    return DocumentTranscription(result=result, setup_warning=None)
