"""SoAI - History request query parsing [backend/core/history/request/query.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import math
from collections.abc import Mapping
from decimal import Decimal, InvalidOperation
from typing import TYPE_CHECKING

from core.config.numeric import coerce_positive_int
from core.errors.exceptions import ValidationError
from core.history.request.aggregation import normalize_history_aggregation_candidate
from core.history.request.models import PreparedHistoryRequest
from core.history.request.preparation import (
    HistoryRequestDefaults,
    prepare_history_request_with_defaults,
)
from core.timing.epoch import epoch_ms

if TYPE_CHECKING:
    from core.types.json import JSONValue

__all__ = ("build_history_query",)


def build_history_query(
    params: Mapping[str, JSONValue],
    history_config: Mapping[str, JSONValue],
    *,
    default_points: int = 300,
    default_aggregation: str = "avg",
    default_window_ms: int = 3_600_000,
) -> PreparedHistoryRequest:
    allowed_keys = {"start_ts_ms", "end_ts_ms", "points", "interval_ms", "aggregation"}
    for key in params:
        if not isinstance(key, str) or key not in allowed_keys:
            raise ValidationError("History query contains unsupported fields.")
    now_ts_ms = int(epoch_ms())
    aggregation = normalize_history_aggregation_candidate(
        params.get("aggregation"),
        default=default_aggregation,
    )
    start_ts_ms = _coerce_int_param(
        params.get("start_ts_ms"),
        default=now_ts_ms - default_window_ms,
        label="start_ts_ms",
    )
    end_ts_ms = _coerce_int_param(
        params.get("end_ts_ms"),
        default=now_ts_ms,
        label="end_ts_ms",
    )
    points = coerce_positive_int(
        _coerce_int_param(params.get("points"), default=default_points, label="points"),
        default=default_points,
        minimum=1,
    )
    interval_ms = _coerce_optional_positive_int(params.get("interval_ms"), label="interval_ms")
    return prepare_history_request_with_defaults(
        start_ts_ms=start_ts_ms,
        end_ts_ms=end_ts_ms,
        points=points,
        interval_ms=interval_ms,
        aggregation=aggregation,
        history_config=history_config,
        defaults=HistoryRequestDefaults(
            max_points_default=10000,
            logging_interval_default=60_000,
            retention_hours_default=0,
        ),
    )


def _coerce_int_param(value: JSONValue, *, default: int, label: str) -> int:
    if value is None:
        return default
    if isinstance(value, str) and not value.strip():
        return default
    if isinstance(value, bool):
        raise ValidationError(f"{label} must be an integer.")
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if not math.isfinite(value) or not value.is_integer():
            raise ValidationError(f"{label} must be an integer.")
        try:
            return int(value)
        except (TypeError, ValueError, OverflowError) as exception:
            raise ValidationError(f"{label} must be an integer.") from exception
    if isinstance(value, str):
        try:
            parsed = Decimal(value.strip())
        except (InvalidOperation, ValueError) as exception:
            raise ValidationError(f"{label} must be an integer.") from exception
        if not parsed.is_finite():
            raise ValidationError(f"{label} must be an integer.")
        if parsed != parsed.to_integral_value():
            raise ValidationError(f"{label} must be an integer.")
        try:
            return int(parsed)
        except (TypeError, ValueError, OverflowError) as exception:
            raise ValidationError(f"{label} must be an integer.") from exception
    raise ValidationError(f"{label} must be an integer.")


def _coerce_optional_positive_int(value: JSONValue, *, label: str) -> int | None:
    if value is None:
        return None
    if isinstance(value, str) and not value.strip():
        return None
    candidate = _coerce_int_param(value, default=1, label=label)
    if candidate < 1:
        raise ValidationError(f"{label} must be >= 1.")
    return candidate
