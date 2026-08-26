"""SoAI - MCP read_audio result analysis [backend/mcp/tools/read_audio_analysis.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.validation.integers import is_strict_int
from mcp.tools.read_audio_transcript import json_float

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = ("build_audio_analysis",)

_SENTENCE_PATTERN_TEXT = r"[.!?]+"
_WORD_PATTERN_TEXT = r"\b[\w']+\b"


@dataclass(frozen=True, slots=True)
class _SegmentStats:
    speech_seconds: float
    longest_segment_seconds: float
    first_speech_second: float | None
    last_speech_second: float | None
    silence_gaps: list[JSONDict]


def build_audio_analysis(
    *,
    text: str,
    duration_seconds: float,
    segments: list[JSONDict],
    diagnostics: JSONDict,
) -> tuple[JSONDict, JSONDict, list[str]]:
    segment_stats = _build_segment_stats(segments)
    word_count = len(re.findall(_WORD_PATTERN_TEXT, text, re.UNICODE))
    character_count = len(text)
    segment_count = len(segments)
    sentence_count = len(re.findall(_SENTENCE_PATTERN_TEXT, text))
    speech_seconds = segment_stats.speech_seconds
    non_speech_seconds = max(0.0, duration_seconds - speech_seconds)
    words_per_minute = _words_per_minute(word_count, speech_seconds)
    speech_timeline: JSONDict = {
        "segment_count": segment_count,
        "first_speech_second": segment_stats.first_speech_second,
        "last_speech_second": segment_stats.last_speech_second,
        "speech_seconds": speech_seconds,
        "non_speech_seconds": non_speech_seconds,
        "silence_gaps": segment_stats.silence_gaps,
        "longest_silence_gap_seconds": _longest_gap_seconds(segment_stats.silence_gaps),
        "average_segment_seconds": speech_seconds / segment_count if segment_count else 0.0,
        "longest_segment_seconds": segment_stats.longest_segment_seconds,
    }
    content_stats: JSONDict = {
        "word_count": word_count,
        "character_count": character_count,
        "sentence_count": sentence_count,
        "words_per_minute": words_per_minute,
        "average_words_per_segment": word_count / segment_count if segment_count else 0.0,
        "text_density_chars_per_second": (
            character_count / speech_seconds if speech_seconds > 0.0 else 0.0
        ),
    }
    notes = _build_model_notes(
        duration_seconds=duration_seconds,
        speech_seconds=speech_seconds,
        word_count=word_count,
        speech_timeline=speech_timeline,
        diagnostics=diagnostics,
    )
    return speech_timeline, content_stats, notes


def _build_segment_stats(segments: list[JSONDict]) -> _SegmentStats:
    speech_seconds = 0.0
    longest_segment_seconds = 0.0
    first_speech_second: float | None = None
    last_speech_second: float | None = None
    silence_gaps: list[JSONDict] = []
    previous_end: float | None = None
    for segment in segments:
        start = json_float(segment.get("start"), default=0.0)
        end = json_float(segment.get("end"), default=start)
        end = max(end, start)
        if first_speech_second is None:
            first_speech_second = start
        last_speech_second = end
        segment_seconds = max(0.0, end - start)
        speech_seconds += segment_seconds
        longest_segment_seconds = max(longest_segment_seconds, segment_seconds)
        if previous_end is not None and start > previous_end:
            silence_gaps.append(
                {
                    "start": previous_end,
                    "end": start,
                    "duration_seconds": start - previous_end,
                },
            )
        previous_end = end
    return _SegmentStats(
        speech_seconds=speech_seconds,
        longest_segment_seconds=longest_segment_seconds,
        first_speech_second=first_speech_second,
        last_speech_second=last_speech_second,
        silence_gaps=silence_gaps,
    )


def _longest_gap_seconds(silence_gaps: list[JSONDict]) -> float:
    longest = 0.0
    for gap in silence_gaps:
        longest = max(longest, json_float(gap.get("duration_seconds"), default=0.0))
    return longest


def _words_per_minute(word_count: int, speech_seconds: float) -> float:
    if word_count <= 0 or speech_seconds <= 0.0:
        return 0.0
    return float(word_count) / (speech_seconds / 60.0)


def _build_model_notes(
    *,
    duration_seconds: float,
    speech_seconds: float,
    word_count: int,
    speech_timeline: JSONDict,
    diagnostics: JSONDict,
) -> list[str]:
    notes: list[str] = []
    if word_count == 0:
        notes.append("No speech text was detected.")
    if duration_seconds > 0.0 and speech_seconds / duration_seconds < 0.25:
        notes.append("Audio appears to contain mostly silence or non-speech content.")
    if 0.0 < duration_seconds < 2.0:
        notes.append("Audio is very short, so speech recognition confidence may be limited.")
    longest_gap = json_float(speech_timeline.get("longest_silence_gap_seconds"), default=0.0)
    if longest_gap >= 5.0:
        notes.append("Audio contains a long pause between speech segments.")
    low_confidence = _json_int(diagnostics.get("low_confidence_segment_count"))
    if low_confidence > 0:
        notes.append("Whisper reported low-confidence segments.")
    high_no_speech = _json_int(diagnostics.get("high_no_speech_segment_count"))
    if high_no_speech > 0:
        notes.append("Whisper marked some segments as likely non-speech.")
    return notes


def _json_int(value: JSONValue) -> int:
    if is_strict_int(value):
        return value
    return 0
