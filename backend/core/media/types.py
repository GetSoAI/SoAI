"""SoAI - Shared media extraction value types [backend/core/media/types.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "AudioChunk",
    "AudioProbeResult",
    "OcrFrameText",
    "TranscriptSegment",
    "TranscriptionChunkResult",
    "TranscriptionResult",
    "VideoProbeResult",
    "VisibleTextBudgetResult",
    "VisibleTextOccurrence",
)


@dataclass(frozen=True, slots=True)
class AudioChunk:
    index: int
    start_seconds: float
    end_seconds: float


@dataclass(frozen=True, slots=True)
class TranscriptSegment:
    start_seconds: float
    end_seconds: float
    text: str


@dataclass(frozen=True, slots=True)
class TranscriptionChunkResult:
    text: str
    language: str | None
    segments: tuple[TranscriptSegment, ...]
    segment_details: tuple[JSONDict, ...] = ()


@dataclass(frozen=True, slots=True)
class TranscriptionResult:
    text: str
    language: str | None
    segments: tuple[TranscriptSegment, ...]
    segment_details: tuple[JSONDict, ...] = ()


@dataclass(frozen=True, slots=True)
class AudioProbeResult:
    duration_seconds: float
    container: str
    audio_codec: str
    sample_rate_hz: int | None
    channels: int | None
    bit_rate: int | None


@dataclass(frozen=True, slots=True)
class VideoProbeResult:
    duration_seconds: float
    width: int
    height: int
    container: str
    video_codec: str
    audio_codec: str | None
    audio_present: bool
    frame_rate: float | None
    mime_type: str


@dataclass(frozen=True, slots=True)
class OcrFrameText:
    timestamp_seconds: float
    text: str
    confidence: float


@dataclass(frozen=True, slots=True)
class VisibleTextOccurrence:
    start_seconds: float
    end_seconds: float
    text: str
    confidence: float


@dataclass(frozen=True, slots=True)
class VisibleTextBudgetResult:
    occurrences: tuple[VisibleTextOccurrence, ...]
    truncated: bool
    original_text_chars: int
    retained_text_chars: int
