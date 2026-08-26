"""SoAI - Media audio chunk and transcript timeline mapping [backend/core/media/timeline.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import math
from collections.abc import Iterator
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.media.types import (
    AudioChunk,
    TranscriptionChunkResult,
    TranscriptionResult,
    TranscriptSegment,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = ("AudioChunkPlan", "map_chunk_transcript", "plan_audio_chunks")

_MINIMUM_DURATION_SECONDS = 0.001


@dataclass(frozen=True, slots=True)
class AudioChunkPlan:
    duration_seconds: float
    chunk_seconds: int
    total_chunks: int

    def __bool__(self) -> bool:
        return self.total_chunks > 0

    def __iter__(self) -> Iterator[AudioChunk]:
        duration_numerator, duration_denominator = self.duration_seconds.as_integer_ratio()
        for index in range(self.total_chunks):
            start_seconds = float(index * self.chunk_seconds)
            end_units = (index + 1) * self.chunk_seconds
            yield AudioChunk(
                index=index,
                start_seconds=start_seconds,
                end_seconds=(
                    self.duration_seconds
                    if end_units * duration_denominator >= duration_numerator
                    else float(end_units)
                ),
            )


def plan_audio_chunks(*, duration_seconds: float, chunk_seconds: int) -> AudioChunkPlan:
    if not math.isfinite(duration_seconds) or duration_seconds < 0.0:
        raise ValidationError("Audio duration must be a finite non-negative number.")
    if chunk_seconds <= 0:
        raise ValidationError("Audio chunk duration must be positive.")
    if duration_seconds < _MINIMUM_DURATION_SECONDS:
        return AudioChunkPlan(duration_seconds, chunk_seconds, 0)
    duration_numerator, duration_denominator = duration_seconds.as_integer_ratio()
    chunk_denominator = duration_denominator * chunk_seconds
    total_chunks = (duration_numerator + chunk_denominator - 1) // chunk_denominator
    return AudioChunkPlan(duration_seconds, chunk_seconds, total_chunks)


def map_chunk_transcript(
    chunk: AudioChunk,
    result: TranscriptionChunkResult,
    *,
    media_duration_seconds: float,
) -> TranscriptionResult:
    mapped: list[TranscriptSegment] = []
    for segment in result.segments:
        text = " ".join(segment.text.split())
        if (
            not text
            or not math.isfinite(segment.start_seconds)
            or not math.isfinite(segment.end_seconds)
        ):
            continue
        start_seconds = max(0.0, chunk.start_seconds + segment.start_seconds)
        end_seconds = min(media_duration_seconds, chunk.start_seconds + segment.end_seconds)
        if end_seconds <= start_seconds:
            continue
        mapped.append(
            TranscriptSegment(
                start_seconds=start_seconds,
                end_seconds=end_seconds,
                text=text,
            ),
        )
    return TranscriptionResult(
        text=" ".join(result.text.split()),
        language=result.language,
        segments=tuple(mapped),
        segment_details=tuple(
            _map_segment_detail(detail, chunk, media_duration_seconds)
            for detail in result.segment_details
        ),
    )


def _number(value: JSONValue) -> float | None:
    if isinstance(value, bool):
        return None
    number = float(value) if isinstance(value, int | float) else math.nan
    return number if math.isfinite(number) else None


def _absolute_time(value: JSONValue, chunk: AudioChunk, duration: float) -> JSONValue:
    number = _number(value)
    if number is None:
        return value
    return min(duration, max(0.0, chunk.start_seconds + number))


def _map_segment_detail(detail: JSONDict, chunk: AudioChunk, duration: float) -> JSONDict:
    mapped = dict(detail)
    mapped["start"] = _absolute_time(detail.get("start"), chunk, duration)
    mapped["end"] = _absolute_time(detail.get("end"), chunk, duration)
    words_value = detail.get("words")
    if isinstance(words_value, list):
        mapped_words: list[JSONDict] = []
        for word_value in words_value:
            if not isinstance(word_value, dict):
                continue
            word = dict(word_value)
            word["start"] = _absolute_time(word_value.get("start"), chunk, duration)
            word["end"] = _absolute_time(word_value.get("end"), chunk, duration)
            mapped_words.append(word)
        mapped["words"] = mapped_words
    return mapped
