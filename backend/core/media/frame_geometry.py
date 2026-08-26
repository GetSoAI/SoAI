"""SoAI - Shared video frame geometry primitives [backend/core/media/frame_geometry.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import math
from dataclasses import dataclass

from core.errors.exceptions import ValidationError

__all__ = (
    "FrameTarget",
    "compute_frame_target",
    "compute_frame_timestamps",
    "map_jpeg_quality_to_ffmpeg_qscale",
)

_TIMESTAMP_EPSILON = 1e-9


@dataclass(frozen=True, slots=True)
class FrameTarget:
    width: int
    height: int


def _force_even(value: int) -> int:
    return max(2, value - value % 2)


def compute_frame_target(source_width: int, source_height: int, max_pixels: int) -> FrameTarget:
    if source_width <= 0 or source_height <= 0 or max_pixels <= 0:
        raise ValidationError("Video frame geometry values must be positive.")
    if source_width * source_height <= max_pixels:
        return FrameTarget(source_width, source_height)
    factor = math.sqrt(max_pixels / (source_width * source_height))
    return FrameTarget(
        _force_even(math.floor(source_width * factor)),
        _force_even(math.floor(source_height * factor)),
    )


def compute_frame_timestamps(
    range_start_seconds: float,
    range_end_seconds: float,
    frames_per_second: float,
) -> tuple[float, ...]:
    if frames_per_second <= 0 or range_end_seconds <= range_start_seconds:
        raise ValidationError("Video frame timeline values are invalid.")
    span = range_end_seconds - range_start_seconds
    timestamps: list[float] = []
    index = 0
    while index / frames_per_second < span - _TIMESTAMP_EPSILON:
        timestamp = range_start_seconds + index / frames_per_second
        if timestamp >= range_end_seconds:
            break
        timestamps.append(timestamp)
        index += 1
    return tuple(timestamps) if timestamps else (range_start_seconds,)


def map_jpeg_quality_to_ffmpeg_qscale(jpeg_quality: int) -> int:
    return max(2, min(31, round((100 - jpeg_quality) * 31 / 100)))
