"""SoAI - Speech-to-text verbose transcript validation and normalization [backend/core/media/transcript_normalization.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from core.errors.exceptions import ModelOutputContractError
from core.media.types import TranscriptionChunkResult, TranscriptSegment
from core.validation.numbers import coerce_optional_float_from_json
from core.validation.strings import coerce_optional_trimmed_str

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = ("normalize_verbose_transcript",)

_SEGMENT_DIAGNOSTIC_KEYS: tuple[str, ...] = (
    "avg_logprob",
    "compression_ratio",
    "no_speech_prob",
    "temperature",
)
_UNDETERMINED_LANGUAGE = "und"


@dataclass(frozen=True, slots=True)
class _Word:
    text: str
    start: float
    end: float
    probability: float | None

    def to_json(self) -> JSONDict:
        return {
            "word": self.text,
            "start": self.start,
            "end": self.end,
            "probability": self.probability,
        }


@dataclass(slots=True)
class _Segment:
    start: float
    end: float
    text: str
    diagnostics: dict[str, float]
    words: list[_Word] | None = field(default=None)

    def to_detail(self) -> JSONDict:
        detail: JSONDict = {"start": self.start, "end": self.end, "text": self.text}
        for key, value in self.diagnostics.items():
            detail[key] = value
        if self.words is not None:
            detail["words"] = [word.to_json() for word in self.words]
        return detail


def _malformed(message: str) -> ModelOutputContractError:
    return ModelOutputContractError(f"Speech-to-text returned a malformed transcript: {message}")


def _time_range(entry: JSONDict, label: str) -> tuple[float, float]:
    start = coerce_optional_float_from_json(entry.get("start"))
    end = coerce_optional_float_from_json(entry.get("end"))
    if start is None or end is None or start < 0.0 or end < start:
        raise _malformed(f"{label} timing is invalid.")
    return start, end


def _word(value: JSONValue) -> _Word:
    if not isinstance(value, dict):
        raise _malformed("a word entry is not an object.")
    text = value.get("word")
    if not isinstance(text, str):
        raise _malformed("a word entry has no text.")
    start, end = _time_range(value, "word")
    return _Word(
        text=text,
        start=start,
        end=end,
        probability=coerce_optional_float_from_json(value.get("probability")),
    )


def _words(value: JSONValue) -> list[_Word]:
    if not isinstance(value, list):
        raise _malformed("words is not a list.")
    return [_word(entry) for entry in value]


def _segment(value: JSONValue) -> _Segment:
    if not isinstance(value, dict):
        raise _malformed("a segment entry is not an object.")
    text = value.get("text")
    if not isinstance(text, str):
        raise _malformed("a segment entry has no text.")
    start, end = _time_range(value, "segment")
    diagnostics = {
        key: number
        for key in _SEGMENT_DIAGNOSTIC_KEYS
        if (number := coerce_optional_float_from_json(value.get(key))) is not None
    }
    words_value = value.get("words")
    return _Segment(
        start=start,
        end=end,
        text=text,
        diagnostics=diagnostics,
        words=None if words_value is None else _words(words_value),
    )


def _attach_top_level_words(segments: list[_Segment], words: list[_Word]) -> None:
    if not words:
        return
    if not segments:
        raise _malformed("words were returned without segments.")
    assigned = {
        (word.text, word.start, word.end) for segment in segments for word in segment.words or ()
    }
    for word in sorted(words, key=lambda entry: (entry.start, entry.end)):
        identity = (word.text, word.start, word.end)
        if identity in assigned:
            continue
        candidates = [segment for segment in segments if segment.start <= word.start <= segment.end]
        if not candidates:
            raise _malformed("word timing does not belong to a segment.")
        owner = max(candidates, key=lambda segment: segment.start)
        if owner.words is None:
            owner.words = []
        owner.words.append(word)
        assigned.add(identity)


def _language(value: JSONValue) -> str | None:
    language = coerce_optional_trimmed_str(value) if isinstance(value, str) else None
    if language is None or language.casefold() == _UNDETERMINED_LANGUAGE:
        return None
    return language


def normalize_verbose_transcript(payload: JSONValue) -> TranscriptionChunkResult:
    if not isinstance(payload, dict):
        raise _malformed("the response is not an object.")
    text_value = payload.get("text")
    if not isinstance(text_value, str):
        raise _malformed("text is missing.")
    text = " ".join(text_value.split())
    segments_value = payload.get("segments", [])
    if not isinstance(segments_value, list):
        raise _malformed("segments is not a list.")
    segments = [_segment(entry) for entry in segments_value]
    if text and not segments:
        raise _malformed("text was returned without segment timing.")
    words_value = payload.get("words")
    if words_value is not None:
        _attach_top_level_words(segments, _words(words_value))
    for segment in segments:
        if segment.words is not None:
            segment.words.sort(key=lambda entry: (entry.start, entry.end))
    return TranscriptionChunkResult(
        text=text,
        language=_language(payload.get("language")),
        segments=tuple(
            TranscriptSegment(
                start_seconds=segment.start,
                end_seconds=segment.end,
                text=segment.text,
            )
            for segment in segments
        ),
        segment_details=tuple(segment.to_detail() for segment in segments),
    )
