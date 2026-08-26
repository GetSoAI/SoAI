"""SoAI - Bounded video frame timestamp sampling [backend/core/media/video_frame_sampling.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import math

from core.errors.exceptions import ValidationError
from core.media.uniform_sampling import select_uniform_indices

__all__ = ("generate_bounded_video_frame_timestamps",)

_TIMESTAMP_EPSILON = 1e-9


def _candidate_count(duration_seconds: float, frames_per_second: float) -> int:
    candidate_limit = duration_seconds - _TIMESTAMP_EPSILON
    if candidate_limit <= 0.0:
        return 1
    limit_numerator, limit_denominator = candidate_limit.as_integer_ratio()
    cadence_numerator, cadence_denominator = frames_per_second.as_integer_ratio()
    numerator = limit_numerator * cadence_numerator
    denominator = limit_denominator * cadence_denominator
    return max(1, (numerator + denominator - 1) // denominator)


def generate_bounded_video_frame_timestamps(
    *,
    duration_seconds: float,
    frames_per_second: float,
    maximum_frames: int,
) -> tuple[float, ...]:
    if not math.isfinite(duration_seconds) or duration_seconds <= 0.0:
        raise ValidationError("Video duration must be a finite positive number.")
    if not math.isfinite(frames_per_second) or frames_per_second <= 0.0:
        raise ValidationError("Video frame cadence must be a finite positive number.")
    if maximum_frames <= 0:
        raise ValidationError("Video frame maximum must be positive.")
    candidate_count = _candidate_count(duration_seconds, frames_per_second)
    indices = select_uniform_indices(candidate_count, min(candidate_count, maximum_frames))
    cadence_numerator, cadence_denominator = frames_per_second.as_integer_ratio()
    return tuple((index * cadence_denominator) / cadence_numerator for index in indices)
