"""SoAI - History request preparation and validation [backend/core/history/request/preparation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.history.intervals import sanitize_supported_intervals
from core.history.request.coercion import (
    coerce_numeric_input,
    coerce_numeric_sequence,
    coerce_str_sequence,
)
from core.history.request.models import PreparedHistoryRequest
from core.history.request.resolution import resolve_history_request
from core.validation.requirements import require_positive_int

if TYPE_CHECKING:
    from core.history.request.models import NumericInput
    from core.types.json import JSONValue

__all__ = (
    "HistoryRequestDefaults",
    "prepare_history_request",
    "prepare_history_request_from_config",
    "prepare_history_request_with_defaults",
)


@dataclass(frozen=True, slots=True)
class HistoryRequestDefaults:
    max_points_default: int
    logging_interval_default: int
    retention_hours_default: int


def prepare_history_request(
    *,
    start_ts_ms: NumericInput,
    end_ts_ms: NumericInput,
    points: NumericInput,
    interval_ms: NumericInput | None,
    aggregation: str,
    supported_aggregations: Sequence[str],
    max_points_allowed: NumericInput,
    logging_interval_ms: NumericInput,
    supported_intervals: Sequence[NumericInput] | None,
    retention_hours: NumericInput,
) -> PreparedHistoryRequest:
    try:
        start_ts_int = int(start_ts_ms)
        end_ts_int = int(end_ts_ms)
    except (TypeError, ValueError) as exception:
        raise ValidationError(
            "start_ts_ms and end_ts_ms must be valid integer epoch millisecond values",
        ) from exception
    if start_ts_int >= end_ts_int:
        raise ValidationError("start_ts_ms must be less than end_ts_ms")
    supported_display = [
        agg.strip() for agg in supported_aggregations if isinstance(agg, str) and agg.strip()
    ]
    if not supported_display:
        raise ValidationError("No supported aggregations configured.")
    supported_set = {supported_type.lower() for supported_type in supported_display}
    normalized_aggregation = (aggregation or "").strip().lower()
    if normalized_aggregation not in supported_set:
        readable = ", ".join(supported_display)
        raise ValidationError(
            f"Unsupported aggregation type: {aggregation}. Must be one of {readable}.",
        )
    requested_points = require_positive_int(points, name="points")
    try:
        max_points_allowed_int = max(1, int(max_points_allowed))
    except (TypeError, ValueError) as exception:
        raise ValidationError("MAX_POINTS must be a positive integer") from exception
    try:
        logging_interval_int = max(1, int(logging_interval_ms))
    except (TypeError, ValueError) as exception:
        raise ValidationError("LOGGING_INTERVAL_MS must be a positive integer") from exception
    normalized_intervals = sanitize_supported_intervals(
        supported_intervals,
        logging_interval_int,
        extra_defaults=(),
        allow_empty=False,
    )
    explicit_interval = None
    if interval_ms is not None:
        explicit_interval = require_positive_int(interval_ms, name="interval_ms")
    try:
        retention_hours_value = int(retention_hours)
    except (TypeError, ValueError) as exception:
        raise ValidationError("DB_RETENTION_HOURS must be a non-negative integer") from exception
    resolution = resolve_history_request(
        start_ts_ms=start_ts_int,
        end_ts_ms=end_ts_int,
        requested_points=requested_points,
        max_points_allowed=max_points_allowed_int,
        supported_intervals=normalized_intervals,
        logging_interval_ms=logging_interval_int,
        explicit_interval_ms=explicit_interval,
        retention_hours=retention_hours_value,
    )
    return PreparedHistoryRequest(
        start_ts_ms=start_ts_int,
        end_ts_ms=end_ts_int,
        requested_points=requested_points,
        aggregation=normalized_aggregation,
        logging_interval_ms=logging_interval_int,
        resolution=resolution,
    )


def prepare_history_request_from_config(
    *,
    start_ts_ms: int,
    end_ts_ms: int,
    points: int,
    interval_ms: int | None,
    aggregation: str,
    history_config: Mapping[str, JSONValue],
    max_points_default: int,
    logging_interval_default: int,
    retention_hours_default: int,
) -> PreparedHistoryRequest:
    supported_aggregations = coerce_str_sequence(
        history_config.get("SUPPORTED_AGGREGATIONS"),
        field="SUPPORTED_AGGREGATIONS",
    )
    max_points_allowed = coerce_numeric_input(
        history_config.get("MAX_POINTS", max_points_default),
        field="MAX_POINTS",
    )
    logging_interval = coerce_numeric_input(
        history_config.get("LOGGING_INTERVAL_MS", logging_interval_default),
        field="LOGGING_INTERVAL_MS",
    )
    supported_intervals = coerce_numeric_sequence(
        history_config.get("SUPPORTED_INTERVALS_MS"),
        field="SUPPORTED_INTERVALS_MS",
    )
    retention_hours = coerce_numeric_input(
        history_config.get("DB_RETENTION_HOURS", retention_hours_default),
        field="DB_RETENTION_HOURS",
    )
    return prepare_history_request(
        start_ts_ms=start_ts_ms,
        end_ts_ms=end_ts_ms,
        points=points,
        interval_ms=interval_ms,
        aggregation=aggregation,
        supported_aggregations=supported_aggregations,
        max_points_allowed=max_points_allowed,
        logging_interval_ms=logging_interval,
        supported_intervals=supported_intervals,
        retention_hours=retention_hours,
    )


def prepare_history_request_with_defaults(
    *,
    start_ts_ms: int,
    end_ts_ms: int,
    points: int,
    interval_ms: int | None,
    aggregation: str,
    history_config: Mapping[str, JSONValue],
    defaults: HistoryRequestDefaults,
) -> PreparedHistoryRequest:
    return prepare_history_request_from_config(
        start_ts_ms=start_ts_ms,
        end_ts_ms=end_ts_ms,
        points=points,
        interval_ms=interval_ms,
        aggregation=aggregation,
        history_config=history_config,
        max_points_default=defaults.max_points_default,
        logging_interval_default=defaults.logging_interval_default,
        retention_hours_default=defaults.retention_hours_default,
    )
