"""SoAI - Neutral ffprobe media validation and metadata [backend/core/media/probing.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.files.document_type_detection import detect_mime_from_path
from core.media.process_runtime import run_media_process
from core.media.types import AudioProbeResult, VideoProbeResult
from core.serialization.json_parsing import parse_json_dict

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = ("probe_audio", "probe_video")


def _number(value: JSONValue) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        candidate = float(value) if isinstance(value, int | float | str) else math.nan
    except ValueError:
        return None
    return candidate if math.isfinite(candidate) else None


def _positive_int(value: JSONValue) -> int | None:
    candidate = _number(value)
    if candidate is None or candidate <= 0 or candidate != int(candidate):
        return None
    return int(candidate)


def _text(value: JSONValue) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def _parse_rate(value: JSONValue) -> float | None:
    raw = _text(value)
    if raw is None:
        return _number(value)
    numerator_text, separator, denominator_text = raw.partition("/")
    if not separator:
        return _number(raw)
    numerator = _number(numerator_text)
    denominator = _number(denominator_text)
    if numerator is None or denominator is None or denominator <= 0:
        return None
    return numerator / denominator


def _document(raw: bytes) -> JSONDict:
    return parse_json_dict(raw, field="media probe metadata")


def _sections(document: JSONDict) -> tuple[list[JSONDict], JSONDict]:
    streams_value = document.get("streams")
    format_value = document.get("format")
    if not isinstance(streams_value, list):
        raise ValidationError("Media source has no readable streams.")
    streams = [stream for stream in streams_value if isinstance(stream, dict)]
    return streams, format_value if isinstance(format_value, dict) else {}


def _duration(format_section: JSONDict, stream: JSONDict) -> float:
    value = _number(format_section.get("duration")) or _number(stream.get("duration"))
    if value is None or value <= 0:
        raise ValidationError("Media source has no usable duration.")
    return value


async def _probe(source_path: str, timeout_seconds: float) -> JSONDict:
    output = await run_media_process(
        (
            "ffprobe",
            "-v",
            "error",
            "-print_format",
            "json",
            "-show_format",
            "-show_streams",
            source_path,
        ),
        timeout_seconds=timeout_seconds,
        dependency_name="ffprobe",
        operation_name="Media probing",
        capture_stdout=True,
    )
    return _document(output)


async def probe_audio(source_path: str, *, timeout_seconds: float) -> AudioProbeResult:
    streams, format_section = _sections(await _probe(source_path, timeout_seconds))
    if any(_is_playable_video_stream(stream) for stream in streams):
        raise ValidationError("Audio source contains a video stream.")
    audio_stream = next((stream for stream in streams if stream.get("codec_type") == "audio"), None)
    if audio_stream is None:
        raise ValidationError("Media source has no audio stream.")
    return AudioProbeResult(
        duration_seconds=_duration(format_section, audio_stream),
        container=_text(format_section.get("format_name")) or "unknown",
        audio_codec=_text(audio_stream.get("codec_name")) or "unknown",
        sample_rate_hz=_positive_int(audio_stream.get("sample_rate")),
        channels=_positive_int(audio_stream.get("channels")),
        bit_rate=_positive_int(audio_stream.get("bit_rate")),
    )


def _is_playable_video_stream(stream: JSONDict) -> bool:
    if stream.get("codec_type") != "video":
        return False
    disposition = stream.get("disposition")
    return not isinstance(disposition, dict) or disposition.get("attached_pic") != 1


async def probe_video(source_path: str, *, timeout_seconds: float) -> VideoProbeResult:
    streams, format_section = _sections(await _probe(source_path, timeout_seconds))
    video_stream = next(
        (stream for stream in streams if _is_playable_video_stream(stream)),
        None,
    )
    if video_stream is None:
        raise ValidationError("Media source has no video stream.")
    width = _positive_int(video_stream.get("width"))
    height = _positive_int(video_stream.get("height"))
    if width is None or height is None:
        raise ValidationError("Media source has invalid video dimensions.")
    audio_stream = next((stream for stream in streams if stream.get("codec_type") == "audio"), None)
    return VideoProbeResult(
        duration_seconds=_duration(format_section, video_stream),
        width=width,
        height=height,
        container=_text(format_section.get("format_name")) or "unknown",
        video_codec=_text(video_stream.get("codec_name")) or "unknown",
        audio_codec=_text(audio_stream.get("codec_name")) if audio_stream is not None else None,
        audio_present=audio_stream is not None,
        frame_rate=_parse_rate(video_stream.get("avg_frame_rate")),
        mime_type=detect_mime_from_path(source_path) or "application/octet-stream",
    )
