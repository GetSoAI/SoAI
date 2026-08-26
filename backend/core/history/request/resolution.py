"""SoAI - History request resolution algorithm [backend/core/history/request/resolution.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import math
from collections.abc import Sequence

from core.errors.exceptions import ValidationError
from core.history.request.models import HistoryRequestResolution
from core.timing.durations import hours_to_ms

__all__ = ("resolve_history_request",)


def resolve_history_request(
    *,
    start_ts_ms: int,
    end_ts_ms: int,
    requested_points: int,
    max_points_allowed: int,
    supported_intervals: Sequence[int],
    logging_interval_ms: int,
    explicit_interval_ms: int | None,
    retention_hours: int,
) -> HistoryRequestResolution:
    try:
        start_int = int(start_ts_ms)
        end_int = int(end_ts_ms)
    except (TypeError, ValueError) as exception:
        raise ValidationError(
            "start_ts_ms and end_ts_ms must be valid integer epoch millisecond values",
        ) from exception
    if start_int < 0 or end_int < 0:
        raise ValidationError("start_ts_ms and end_ts_ms must be non-negative")
    if start_int >= end_int:
        raise ValidationError("start_ts_ms must be less than end_ts_ms")
    try:
        requested_points_int = int(requested_points)
    except (TypeError, ValueError) as exception:
        raise ValidationError("points must be a positive integer") from exception
    if requested_points_int <= 0:
        raise ValidationError("points must be a positive integer")
    try:
        max_points_allowed_int = max(1, int(max_points_allowed))
    except (TypeError, ValueError) as exception:
        raise ValidationError("max_points must be a positive integer") from exception
    try:
        logging_interval_int = max(1, int(logging_interval_ms))
    except (TypeError, ValueError) as exception:
        raise ValidationError("logging_interval_ms must be a positive integer") from exception
    try:
        retention_hours_int = max(0, int(retention_hours))
    except (TypeError, ValueError) as exception:
        raise ValidationError("retention_hours must be a non-negative integer") from exception
    retention_ms = hours_to_ms(retention_hours_int)
    retention_applied = False
    clamped_start = start_int
    if retention_ms > 0:
        retention_floor = end_int - retention_ms
        if retention_floor >= end_int:
            raise ValidationError("Time range exceeds retention window")
        if clamped_start < retention_floor:
            clamped_start = retention_floor
            retention_applied = True
            if clamped_start >= end_int:
                raise ValidationError("Time range exceeds retention window")
    else:
        retention_floor = None
    effective_points = min(requested_points_int, max_points_allowed_int)
    if effective_points <= 0:
        effective_points = 1
    normalised_intervals_set: set[int] = {logging_interval_int}
    for candidate in supported_intervals or ():
        try:
            numeric = int(float(candidate))
            if numeric > 0:
                normalised_intervals_set.add(numeric)
        except (TypeError, ValueError):
            continue
    normalised_intervals = tuple(sorted(normalised_intervals_set))
    explicit_interval_value: int | None = None
    if explicit_interval_ms is not None:
        try:
            explicit_interval_value = int(explicit_interval_ms)
        except (TypeError, ValueError) as exception:
            raise ValidationError("interval_ms must be a positive integer") from exception
        if explicit_interval_value <= 0:
            raise ValidationError("interval_ms must be a positive integer")
        if explicit_interval_value not in normalised_intervals_set:
            raise ValidationError(f"Unsupported interval_ms: {explicit_interval_value}")

    def _compute_bucket_details(interval: int) -> tuple[int, int, int]:
        aligned_start = clamped_start // interval * interval
        if aligned_start > clamped_start:
            aligned_start -= interval
        span = end_int - aligned_start
        bucket_count = (span + interval - 1) // interval if interval > 0 else 0
        if bucket_count <= 0:
            bucket_count = 1
        aligned_end = aligned_start + (bucket_count - 1) * interval
        return (bucket_count, aligned_start, aligned_end)

    selected_interval: int | None = None
    selected_bucket_count: int | None = None
    aligned_start_ts = clamped_start
    aligned_end_ts = end_int
    if explicit_interval_value is not None:
        selected_interval = explicit_interval_value
        selected_bucket_count, aligned_start_ts, aligned_end_ts = _compute_bucket_details(
            selected_interval,
        )
        if selected_bucket_count > max_points_allowed_int:
            raise ValidationError(
                f"Requested interval_ms {selected_interval} produces {selected_bucket_count} buckets which exceeds the limit of {max_points_allowed_int}",
            )
    else:
        for candidate in normalised_intervals:
            bucket_count, candidate_aligned_start, candidate_aligned_end = _compute_bucket_details(
                candidate,
            )
            if bucket_count <= effective_points:
                selected_interval = candidate
                selected_bucket_count = bucket_count
                aligned_start_ts = candidate_aligned_start
                aligned_end_ts = candidate_aligned_end
                break
        if selected_interval is None:
            selected_interval = normalised_intervals[-1]
            selected_bucket_count, aligned_start_ts, aligned_end_ts = _compute_bucket_details(
                selected_interval,
            )
    if selected_bucket_count is None:
        selected_bucket_count, aligned_start_ts, aligned_end_ts = _compute_bucket_details(
            selected_interval,
        )
    if selected_bucket_count > max_points_allowed_int:
        if explicit_interval_value is not None:
            raise ValidationError(
                f"interval_ms {selected_interval} with the requested window results in {selected_bucket_count} buckets, which exceeds the allowed maximum of {max_points_allowed_int}",
            )
        while selected_bucket_count > max_points_allowed_int:
            multiplier = math.ceil(selected_bucket_count / max_points_allowed_int)
            selected_interval *= multiplier
            selected_bucket_count, aligned_start_ts, aligned_end_ts = _compute_bucket_details(
                selected_interval,
            )
    effective_points = min(effective_points, selected_bucket_count)
    duration_ms = end_int - clamped_start
    if duration_ms <= 0:
        raise ValidationError("Resolved time range must be greater than zero milliseconds")
    return HistoryRequestResolution(
        original_start_ts_ms=start_int,
        start_ts_ms=clamped_start,
        end_ts_ms=end_int,
        interval_ms=selected_interval,
        requested_points=requested_points_int,
        effective_points=effective_points,
        max_points=max_points_allowed_int,
        bucket_count=selected_bucket_count,
        aligned_start_ts_ms=aligned_start_ts,
        aligned_end_ts_ms=aligned_end_ts,
        retention_applied=retention_applied,
        retention_start_ts_ms=retention_floor if retention_applied else None,
        requested_interval_ms=explicit_interval_value,
        supported_intervals_ms=normalised_intervals,
        duration_ms=duration_ms,
        interval_source="explicit" if explicit_interval_value is not None else "auto",
    )
