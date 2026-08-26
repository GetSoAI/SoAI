"""SoAI - Historical query normalization and resolution [backend/database/core/history_queries.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.history.config_view import build_history_config_view
from core.history.request.aggregation import normalize_history_aggregation_candidate
from core.history.request.models import HistoryRequestResolution
from core.history.request.resolution import resolve_history_request
from core.timing.durations import days_to_ms

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "build_history_resolution",
    "normalize_historical_query",
    "validate_historical_query_params",
)


def validate_historical_query_params(
    start_ts_ms: int,
    end_ts_ms: int,
    interval_ms: int,
    aggregation: str,
    max_points: int,
    valid_aggregations: set[str],
    default_aggregation: str = "avg",
) -> tuple[int, int, str]:
    requested_aggregation = normalize_history_aggregation_candidate(
        aggregation,
        default=default_aggregation,
    )
    if start_ts_ms >= end_ts_ms:
        raise ValidationError(
            f"start_ts_ms ({start_ts_ms}) must be less than end_ts_ms ({end_ts_ms})",
        )
    if (end_ts_ms - start_ts_ms) > days_to_ms(365):
        raise ValidationError("Time range cannot exceed 365 days")
    agg_lower = requested_aggregation.lower()
    if agg_lower not in valid_aggregations:
        raise ValidationError(
            f"Invalid aggregation '{aggregation}'. Must be one of: {', '.join(valid_aggregations)}",
        )
    try:
        sanitized_interval = max(1, int(interval_ms or 1))
    except (TypeError, ValueError) as exception:
        raise ValidationError(
            f"interval_ms must be a positive integer, got: {interval_ms}",
        ) from exception
    if sanitized_interval > (end_ts_ms - start_ts_ms):
        raise ValidationError(
            f"interval_ms ({sanitized_interval}) cannot exceed time range ({end_ts_ms - start_ts_ms} milliseconds)",
        )
    try:
        sanitized_max_points = max(1, int(max_points or 1))
    except (TypeError, ValueError) as exception:
        raise ValidationError(
            f"max_points must be a positive integer, got: {max_points}",
        ) from exception
    return sanitized_interval, sanitized_max_points, agg_lower


def normalize_historical_query(
    start_ts_ms: int,
    end_ts_ms: int,
    interval_ms: int,
    aggregation: str,
    max_points: int,
    valid_aggregations: set[str],
    default_aggregation: str = "avg",
) -> tuple[int, int, str, int]:
    sanitized_interval, sanitized_max_points, agg_lower = validate_historical_query_params(
        start_ts_ms,
        end_ts_ms,
        interval_ms,
        aggregation,
        max_points,
        valid_aggregations,
        default_aggregation=default_aggregation,
    )
    anchor_ts_ms = (
        int(start_ts_ms - start_ts_ms % sanitized_interval)
        if sanitized_interval > 0
        else int(start_ts_ms)
    )
    return sanitized_interval, sanitized_max_points, agg_lower, anchor_ts_ms


def build_history_resolution(
    start_ts_ms: int,
    end_ts_ms: int,
    interval_ms: int,
    requested_points: int,
    metrics_history_config: JSONDict | None,
) -> HistoryRequestResolution:
    requested_points_int = max(1, int(requested_points))
    history_view = build_history_config_view(
        metrics_history_config,
        enabled_default=False,
        logging_interval_default=interval_ms,
        max_points_default=requested_points_int,
        retention_hours_default=0,
        supported_intervals_default=(interval_ms,),
        supported_aggregations_default=(),
        default_interval_default=interval_ms,
    )
    return resolve_history_request(
        start_ts_ms=start_ts_ms,
        end_ts_ms=end_ts_ms,
        requested_points=requested_points_int,
        max_points_allowed=requested_points_int,
        supported_intervals=history_view.supported_intervals_ms,
        logging_interval_ms=history_view.logging_interval_ms,
        explicit_interval_ms=interval_ms,
        retention_hours=history_view.retention_hours,
    )
