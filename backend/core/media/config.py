"""SoAI - Shared media parsing configuration [backend/core/media/config.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.config.numeric_lenient import (
    coerce_lenient_bounded_float,
    coerce_lenient_positive_int,
)
from core.files.document_type_detection import extract_extension
from core.files.extensions.media import AUDIO_EXTENSIONS, VIDEO_EXTENSIONS

if TYPE_CHECKING:
    from core.config.protocols import ConfigProtocol

__all__ = (
    "MediaParsingConfig",
    "resolve_media_parse_timeout",
    "resolve_media_parsing_config",
)


@dataclass(frozen=True, slots=True)
class MediaParsingConfig:
    video_ocr_frames_per_second: float
    video_ocr_max_frames: int
    video_ocr_max_text_chars: int
    ocr_frame_timeout_sec: int
    parse_timeout_sec: int
    whisper_model: str
    audio_chunk_seconds: int
    probe_timeout_sec: int
    frame_extraction_timeout_sec: int
    audio_extraction_timeout_sec: int
    max_frame_pixels: int
    jpeg_quality: int
    temp_reservation_safety_multiplier: int


def resolve_media_parsing_config(config: ConfigProtocol) -> MediaParsingConfig:
    return MediaParsingConfig(
        video_ocr_frames_per_second=coerce_lenient_bounded_float(
            config.get("TOOLS.MEDIA_PARSING.VIDEO_OCR_FRAMES_PER_SECOND"),
            default=1.0,
            minimum=0.01,
            maximum=1.0,
        ),
        video_ocr_max_frames=coerce_lenient_positive_int(
            config.get("TOOLS.MEDIA_PARSING.VIDEO_OCR_MAX_FRAMES"),
            default=360,
            minimum=2,
        ),
        video_ocr_max_text_chars=coerce_lenient_positive_int(
            config.get("TOOLS.MEDIA_PARSING.VIDEO_OCR_MAX_TEXT_CHARS"),
            default=250_000,
            minimum=1,
        ),
        ocr_frame_timeout_sec=coerce_lenient_positive_int(
            config.get("TOOLS.MEDIA_PARSING.OCR_FRAME_TIMEOUT_SEC"),
            default=60,
            minimum=1,
        ),
        parse_timeout_sec=coerce_lenient_positive_int(
            config.get("TOOLS.MEDIA_PARSING.PARSE_TIMEOUT_SEC"),
            default=21_600,
            minimum=1,
        ),
        whisper_model=_whisper_model(config),
        audio_chunk_seconds=_positive_read_video_int(config, "AUDIO_CHUNK_SECONDS", 300),
        probe_timeout_sec=_positive_read_video_int(config, "PROBE_TIMEOUT_SEC", 60),
        frame_extraction_timeout_sec=_positive_read_video_int(
            config,
            "FRAME_EXTRACTION_TIMEOUT_SEC",
            900,
        ),
        audio_extraction_timeout_sec=_positive_read_video_int(
            config,
            "AUDIO_EXTRACTION_TIMEOUT_SEC",
            900,
        ),
        max_frame_pixels=_positive_read_video_int(config, "MAX_FRAME_PIXELS", 2_000_000),
        jpeg_quality=_positive_read_video_int(config, "JPEG_QUALITY", 85),
        temp_reservation_safety_multiplier=_positive_read_video_int(
            config,
            "TEMP_RESERVATION_SAFETY_MULTIPLIER",
            2,
        ),
    )


def _positive_read_video_int(config: ConfigProtocol, suffix: str, default: int) -> int:
    return coerce_lenient_positive_int(
        config.get(f"TOOLS.MCP.READ_VIDEO.{suffix}"),
        default=default,
        minimum=1,
    )


def _whisper_model(config: ConfigProtocol) -> str:
    value = config.get("TOOLS.MCP.READ_VIDEO.WHISPER_MODEL")
    return value.strip() if isinstance(value, str) and value.strip() else "base"


def resolve_media_parse_timeout(
    config: ConfigProtocol,
    *,
    filename: str,
    mime_type: str,
    default_timeout_seconds: float,
) -> float:
    extension = extract_extension(filename)
    media_type = mime_type.casefold()
    if (
        extension in AUDIO_EXTENSIONS
        or extension in VIDEO_EXTENSIONS
        or media_type.startswith("audio/")
        or media_type.startswith("video/")
    ):
        return float(resolve_media_parsing_config(config).parse_timeout_sec)
    return default_timeout_seconds
