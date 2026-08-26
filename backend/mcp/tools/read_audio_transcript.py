"""SoAI - MCP read_audio transcript shaping [backend/mcp/tools/read_audio_transcript.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.validation.numbers import coerce_float_from_json

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "build_read_audio_diagnostics",
    "build_read_audio_transcript",
    "copy_json_dict",
    "json_float",
    "optional_json_float",
    "require_json_dict_list",
)


def build_read_audio_transcript(
    result: JSONDict,
    *,
    model_name: str,
    include_words: bool,
) -> JSONDict:
    segments = _build_segments(result.get("segments"), include_words=include_words)
    text = _json_text(result.get("text"))
    language = _json_text(result.get("language"))
    duration_seconds = _segments_duration_seconds(segments)
    return {
        "text": text,
        "language": language,
        "duration_seconds": duration_seconds,
        "model_used": model_name,
        "segments": segments,
    }


def build_read_audio_diagnostics(segments: list[JSONDict]) -> JSONDict:
    avg_logprob_values = _segment_number_values(segments, "avg_logprob")
    compression_ratio_values = _segment_number_values(segments, "compression_ratio")
    no_speech_values = _segment_number_values(segments, "no_speech_prob")
    temperature_values = _segment_number_values(segments, "temperature")
    return {
        "average_avg_logprob": _average(avg_logprob_values),
        "average_compression_ratio": _average(compression_ratio_values),
        "average_no_speech_prob": _average(no_speech_values),
        "average_temperature": _average(temperature_values),
        "low_confidence_segment_count": _count_below(avg_logprob_values, -1.0),
        "high_no_speech_segment_count": _count_above(no_speech_values, 0.6),
        "segment_diagnostics": _segment_diagnostics(segments),
    }


def copy_json_dict(raw: dict[str, JSONValue]) -> JSONDict:
    copied: JSONDict = {}
    for key, value in raw.items():
        if isinstance(key, str):
            copied[key] = value
    return copied


def require_json_dict_list(value: JSONValue) -> list[JSONDict]:
    if not isinstance(value, list):
        return []
    return [copy_json_dict(item) for item in value if isinstance(item, dict)]


def json_float(value: JSONValue, *, default: float) -> float:
    if isinstance(value, int | float | bool):
        coerced = coerce_float_from_json(
            value,
            default=default,
            allow_bool=True,
            allow_nonfinite=True,
        )
        return coerced if coerced is not None else default
    return default


def _build_segments(value: JSONValue, *, include_words: bool) -> list[JSONDict]:
    if not isinstance(value, list):
        return []
    segments: list[JSONDict] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        segment = _build_segment(copy_json_dict(item), include_words=include_words)
        segments.append(segment)
    return segments


def _build_segment(raw: JSONDict, *, include_words: bool) -> JSONDict:
    segment: JSONDict = {
        "start": json_float(raw.get("start"), default=0.0),
        "end": json_float(raw.get("end"), default=0.0),
        "text": _json_text(raw.get("text")),
    }
    for key in ("avg_logprob", "compression_ratio", "no_speech_prob", "temperature"):
        value = raw.get(key)
        if isinstance(value, int | float | bool):
            segment[key] = json_float(value, default=0.0)
    if include_words:
        segment["words"] = _build_words(raw.get("words"))
    return segment


def _build_words(value: JSONValue) -> list[JSONDict]:
    if not isinstance(value, list):
        return []
    words: list[JSONDict] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        raw_word = copy_json_dict(item)
        words.append(
            {
                "word": _json_text(raw_word.get("word")),
                "start": json_float(raw_word.get("start"), default=0.0),
                "end": json_float(raw_word.get("end"), default=0.0),
                "probability": json_float(raw_word.get("probability"), default=0.0),
            },
        )
    return words


def _segment_diagnostics(segments: list[JSONDict]) -> list[JSONDict]:
    diagnostics: list[JSONDict] = []
    for index, segment in enumerate(segments):
        diagnostics.append(
            {
                "index": index,
                "start": json_float(segment.get("start"), default=0.0),
                "end": json_float(segment.get("end"), default=0.0),
                "avg_logprob": optional_json_float(segment.get("avg_logprob")),
                "compression_ratio": optional_json_float(segment.get("compression_ratio")),
                "no_speech_prob": optional_json_float(segment.get("no_speech_prob")),
                "temperature": optional_json_float(segment.get("temperature")),
            },
        )
    return diagnostics


def _segment_number_values(segments: list[JSONDict], key: str) -> list[float]:
    values: list[float] = []
    for segment in segments:
        value = optional_json_float(segment.get(key))
        if value is not None:
            values.append(value)
    return values


def _segments_duration_seconds(segments: list[JSONDict]) -> float:
    duration = 0.0
    for segment in segments:
        duration = max(duration, json_float(segment.get("end"), default=0.0))
    return duration


def _json_text(value: JSONValue) -> str:
    return str(value) if value is not None else ""


def optional_json_float(value: JSONValue) -> float | None:
    if isinstance(value, int | float | bool):
        return json_float(value, default=0.0)
    return None


def _average(values: list[float]) -> float | None:
    if not values:
        return None
    return sum(values) / len(values)


def _count_below(values: list[float], threshold: float) -> int:
    return sum(1 for value in values if value < threshold)


def _count_above(values: list[float], threshold: float) -> int:
    return sum(1 for value in values if value > threshold)
