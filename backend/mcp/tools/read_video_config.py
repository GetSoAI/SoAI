"""SoAI - MCP read_video tool configuration resolution [backend/mcp/tools/read_video_config.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.config.numeric_lenient import (
    coerce_lenient_bounded_float,
    coerce_lenient_clamped_int,
    coerce_lenient_positive_int,
)
from core.errors.exceptions import ConfigurationError
from core.validation.booleans import parse_bool_flag_with_default

if TYPE_CHECKING:
    from core.config.protocols import ConfigProtocol

__all__ = ("ReadVideoConfig", "resolve_read_video_config")

_PREFIX = "TOOLS.MCP.READ_VIDEO"
_VALID_WHISPER_MODELS = frozenset(
    {"tiny", "base", "small", "medium", "large", "large-v2", "large-v3"},
)


@dataclass(frozen=True, slots=True)
class ReadVideoConfig:
    default_frames_per_second: float
    max_frames_per_second: float
    frame_page_size: int
    max_frame_pixels: int
    jpeg_quality: int
    include_audio_default: bool
    audio_chunk_seconds: int
    job_retention_hours: int
    max_active_jobs: int
    temp_reservation_safety_multiplier: int
    video_preview_seconds: int
    video_preview_max_pixels: int
    video_preview_crf: int
    video_preview_max_bytes: int
    probe_timeout_sec: int
    frame_extraction_timeout_sec: int
    audio_extraction_timeout_sec: int
    preview_extraction_timeout_sec: int
    live_progress_min_interval_ms: int
    whisper_model: str


def resolve_read_video_config(config: ConfigProtocol) -> ReadVideoConfig:
    try:
        return ReadVideoConfig(
            default_frames_per_second=coerce_lenient_bounded_float(
                config.get(f"{_PREFIX}.DEFAULT_FRAMES_PER_SECOND"),
                default=1.0,
                minimum=0.01,
                maximum=1.0,
            ),
            max_frames_per_second=coerce_lenient_bounded_float(
                config.get(f"{_PREFIX}.MAX_FRAMES_PER_SECOND"),
                default=1.0,
                minimum=0.01,
                maximum=1.0,
            ),
            frame_page_size=coerce_lenient_positive_int(
                config.get(f"{_PREFIX}.FRAME_PAGE_SIZE"),
                default=60,
                minimum=1,
            ),
            max_frame_pixels=coerce_lenient_positive_int(
                config.get(f"{_PREFIX}.MAX_FRAME_PIXELS"),
                default=2_000_000,
                minimum=1,
            ),
            jpeg_quality=coerce_lenient_clamped_int(
                config.get(f"{_PREFIX}.JPEG_QUALITY"),
                default=85,
                minimum=40,
                maximum=95,
            ),
            include_audio_default=parse_bool_flag_with_default(
                config.get(f"{_PREFIX}.INCLUDE_AUDIO_DEFAULT"),
                default=True,
            ),
            audio_chunk_seconds=coerce_lenient_positive_int(
                config.get(f"{_PREFIX}.AUDIO_CHUNK_SECONDS"),
                default=300,
                minimum=1,
            ),
            job_retention_hours=coerce_lenient_positive_int(
                config.get(f"{_PREFIX}.JOB_RETENTION_HOURS"),
                default=168,
                minimum=1,
            ),
            max_active_jobs=coerce_lenient_positive_int(
                config.get(f"{_PREFIX}.MAX_ACTIVE_JOBS"),
                default=2,
                minimum=1,
            ),
            temp_reservation_safety_multiplier=coerce_lenient_positive_int(
                config.get(f"{_PREFIX}.TEMP_RESERVATION_SAFETY_MULTIPLIER"),
                default=2,
                minimum=1,
            ),
            video_preview_seconds=coerce_lenient_positive_int(
                config.get(f"{_PREFIX}.VIDEO_PREVIEW_SECONDS"),
                default=8,
                minimum=1,
            ),
            video_preview_max_pixels=coerce_lenient_positive_int(
                config.get(f"{_PREFIX}.VIDEO_PREVIEW_MAX_PIXELS"),
                default=307_200,
                minimum=1,
            ),
            video_preview_crf=coerce_lenient_clamped_int(
                config.get(f"{_PREFIX}.VIDEO_PREVIEW_CRF"),
                default=28,
                minimum=0,
                maximum=51,
            ),
            video_preview_max_bytes=coerce_lenient_positive_int(
                config.get(f"{_PREFIX}.VIDEO_PREVIEW_MAX_BYTES"),
                default=8_388_608,
                minimum=1,
            ),
            probe_timeout_sec=coerce_lenient_positive_int(
                config.get(f"{_PREFIX}.PROBE_TIMEOUT_SEC"),
                default=60,
                minimum=1,
            ),
            frame_extraction_timeout_sec=coerce_lenient_positive_int(
                config.get(f"{_PREFIX}.FRAME_EXTRACTION_TIMEOUT_SEC"),
                default=900,
                minimum=1,
            ),
            audio_extraction_timeout_sec=coerce_lenient_positive_int(
                config.get(f"{_PREFIX}.AUDIO_EXTRACTION_TIMEOUT_SEC"),
                default=900,
                minimum=1,
            ),
            preview_extraction_timeout_sec=coerce_lenient_positive_int(
                config.get(f"{_PREFIX}.PREVIEW_EXTRACTION_TIMEOUT_SEC"),
                default=300,
                minimum=1,
            ),
            live_progress_min_interval_ms=coerce_lenient_clamped_int(
                config.get(f"{_PREFIX}.LIVE_PROGRESS_MIN_INTERVAL_MS"),
                default=1000,
                minimum=0,
            ),
            whisper_model=_read_whisper_model(config),
        )
    except AttributeError as exception:
        raise ConfigurationError(
            "read_video config requires a ConfigProtocol provider.",
        ) from exception


def _read_whisper_model(config: ConfigProtocol) -> str:
    raw_value = config.get(f"{_PREFIX}.WHISPER_MODEL")
    if isinstance(raw_value, str):
        model = raw_value.strip() or "base"
    else:
        model = "base"
    if model not in _VALID_WHISPER_MODELS:
        valid_list = ", ".join(sorted(_VALID_WHISPER_MODELS))
        raise ConfigurationError(
            f"{_PREFIX}.WHISPER_MODEL is invalid: {model}. Valid: {valid_list}",
        )
    return model
