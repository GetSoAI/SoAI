"""SoAI - History configuration building utilities [backend/core/history/config.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING

from core.config.numeric import coerce_positive_int
from core.errors.exceptions import ValidationError
from core.history.intervals import (
    DEFAULT_HISTORY_INTERVALS_MS,
    normalize_history_intervals_and_aggregations,
    normalize_tracked_metrics,
)
from core.validation.booleans import parse_bool

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

    type IntervalRaw = int | float | str

__all__ = (
    "build_history_config",
    "build_metrics_history_config",
    "normalize_history_config",
    "normalize_interval_candidates",
    "normalize_str_candidates",
)


def normalize_interval_candidates(value: JSONValue) -> list[IntervalRaw] | None:
    if isinstance(value, int | float | str):
        return [value]
    if not isinstance(value, Sequence) or isinstance(value, str | bytes | bytearray):
        return None
    candidates: list[IntervalRaw] = []
    for item in value:
        if isinstance(item, int | float | str):
            candidates.append(item)
    return candidates


def normalize_str_candidates(value: JSONValue) -> list[str] | None:
    if isinstance(value, str):
        return [value]
    if not isinstance(value, Sequence) or isinstance(value, str | bytes | bytearray):
        return None
    candidates: list[str] = []
    for item in value:
        if isinstance(item, str):
            candidates.append(item)
    return candidates


def normalize_history_config(
    raw_config: Mapping[str, JSONValue] | None,
    *,
    logging_interval_default: int,
    max_points_default: int,
    retention_hours_default: int,
    intervals_defaults: Sequence[int],
    allow_empty_intervals: bool,
    default_aggregations: Sequence[str],
    mandatory_aggregations: Sequence[str],
    tracked_metrics_default: Sequence[str] | None = None,
) -> JSONDict:
    def _coerce_positive_int_field(
        value: JSONValue,
        *,
        default: int,
        minimum: int,
        field: str,
    ) -> int:
        if isinstance(value, bool):
            raise ValidationError(f"{field} must be a positive integer.")
        return coerce_positive_int(
            value,
            default=default,
            minimum=minimum,
            label=field,
        )

    config_mapping: Mapping[str, JSONValue] = raw_config or {}
    if not isinstance(config_mapping, Mapping):
        raise ValidationError("History configuration must be a mapping.")
    logging_interval = _coerce_positive_int_field(
        config_mapping.get("LOGGING_INTERVAL_MS"),
        default=logging_interval_default,
        minimum=1,
        field="LOGGING_INTERVAL_MS",
    )
    max_points = _coerce_positive_int_field(
        config_mapping.get("MAX_POINTS"),
        default=max_points_default,
        minimum=1,
        field="MAX_POINTS",
    )
    retention_hours = _coerce_positive_int_field(
        config_mapping.get("DB_RETENTION_HOURS"),
        default=retention_hours_default,
        minimum=1,
        field="DB_RETENTION_HOURS",
    )
    intervals_raw = normalize_interval_candidates(config_mapping.get("SUPPORTED_INTERVALS_MS"))
    aggregations_raw = normalize_str_candidates(config_mapping.get("SUPPORTED_AGGREGATIONS"))
    intervals, aggregations = normalize_history_intervals_and_aggregations(
        intervals_raw,
        logging_interval,
        extra_defaults=tuple(intervals_defaults),
        allow_empty_intervals=allow_empty_intervals,
        raw_aggregations=aggregations_raw,
        default_aggregations=default_aggregations,
        mandatory_aggregations=mandatory_aggregations,
    )
    result: JSONDict = {
        "LOGGING_INTERVAL_MS": logging_interval,
        "MAX_POINTS": max_points,
        "DB_RETENTION_HOURS": retention_hours,
        "SUPPORTED_INTERVALS_MS": intervals,
        "SUPPORTED_AGGREGATIONS": aggregations,
    }
    if tracked_metrics_default is not None:
        tracked_raw = normalize_str_candidates(config_mapping.get("TRACKED_METRICS"))
        result["TRACKED_METRICS"] = normalize_tracked_metrics(tracked_raw, tracked_metrics_default)
    return result


def build_history_config(
    raw_config: JSONValue,
    *,
    logging_interval_default: int,
    max_points_default: int,
    retention_hours_default: int,
    intervals_defaults: Sequence[int],
    allow_empty_intervals: bool,
    default_aggregations: Sequence[str],
    mandatory_aggregations: Sequence[str],
    tracked_metrics_default: Sequence[str] | None = None,
    enabled_default: bool = False,
) -> tuple[JSONDict, bool]:
    config_mapping: Mapping[str, JSONValue] = raw_config if isinstance(raw_config, Mapping) else {}
    if not isinstance(config_mapping, Mapping):
        config_mapping = {}
    history_defaults = normalize_history_config(
        config_mapping,
        logging_interval_default=logging_interval_default,
        max_points_default=max_points_default,
        retention_hours_default=retention_hours_default,
        intervals_defaults=intervals_defaults,
        allow_empty_intervals=allow_empty_intervals,
        default_aggregations=default_aggregations,
        mandatory_aggregations=mandatory_aggregations,
        tracked_metrics_default=tracked_metrics_default,
    )
    enabled = parse_bool(config_mapping.get("ENABLED", enabled_default), default=enabled_default)
    merged: JSONDict = {"ENABLED": enabled, **history_defaults}
    return (merged, enabled)


def build_metrics_history_config(
    raw_config: JSONValue,
    *,
    tracked_metrics_default: Sequence[str] | None = None,
    enabled_default: bool = False,
) -> tuple[JSONDict, bool]:
    default_aggregations = ["avg", "min", "max", "count", "delta", "ohlc", "delta_ohlc"]
    history_config, enabled = build_history_config(
        raw_config,
        logging_interval_default=3_000,
        max_points_default=50000,
        retention_hours_default=168,
        intervals_defaults=DEFAULT_HISTORY_INTERVALS_MS,
        allow_empty_intervals=True,
        default_aggregations=default_aggregations,
        mandatory_aggregations=tuple(default_aggregations),
        tracked_metrics_default=tracked_metrics_default,
        enabled_default=enabled_default,
    )
    config_mapping: Mapping[str, JSONValue] = raw_config if isinstance(raw_config, Mapping) else {}
    pruning_value = config_mapping.get("PRUNING_INTERVAL_SEC")
    if isinstance(pruning_value, bool):
        raise ValidationError("PRUNING_INTERVAL_SEC must be a positive integer.")
    pruning_interval = coerce_positive_int(
        pruning_value,
        default=300,
        minimum=1,
        label="PRUNING_INTERVAL_SEC",
    )
    history_config["PRUNING_INTERVAL_SEC"] = pruning_interval
    return (history_config, enabled)
