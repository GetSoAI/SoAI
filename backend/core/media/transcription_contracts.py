"""SoAI - Media transcription request contracts [backend/core/media/transcription_contracts.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.files.types import ParseProgressCallback
    from core.media.speech_selection import ResolvedSpeechModel
    from core.media.speech_setup import SpeechTask
    from core.runtime.request_context import RequestContext

__all__ = (
    "MediaTranscriptionRequest",
    "SpeechChunkRequest",
    "SpeechTranscriptionOptions",
)


@dataclass(frozen=True, slots=True)
class SpeechTranscriptionOptions:
    task: SpeechTask
    language: str | None
    include_word_timestamps: bool


@dataclass(frozen=True, slots=True)
class MediaTranscriptionRequest:
    source_path: str
    duration_seconds: float
    selector: str
    options: SpeechTranscriptionOptions
    request_context: RequestContext
    extraction_deadline: float
    progress_callback: ParseProgressCallback | None = None


@dataclass(frozen=True, slots=True)
class SpeechChunkRequest:
    file_path: str
    byte_count: int
    chunk_index: int
    model: ResolvedSpeechModel
    options: SpeechTranscriptionOptions
    request_context: RequestContext
    deadline_monotonic: float
