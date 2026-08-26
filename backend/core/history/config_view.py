"""SoAI - Shared normalized history configuration view [backend/core/history/config_view.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.history.config import normalize_interval_candidates, normalize_str_candidates
from core.history.intervals import normalize_aggregations, sanitize_supported_intervals
from core.validation.booleans import parse_bool
from core.validation.coercion import coerce_int_from_numberish

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "HistoryConfigView",
    "build_history_config_view",
)


@dataclass(frozen=True, slots=True)
class HistoryConfigView:
    enabled: bool
    logging_interval_ms: int
    max_points: int
    retention_hours: int
    supported_intervals_ms: tuple[int, ...]
    supported_aggregations: tuple[str, ...]
    default_interval_ms: int

    def to_json_dict(self) -> JSONDict:
        return {
            "ENABLED": self.enabled,
            "LOGGING_INTERVAL_MS": self.logging_interval_ms,
            "MAX_POINTS": self.max_points,
            "DB_RETENTION_HOURS": self.retention_hours,
            "SUPPORTED_INTERVALS_MS": list(self.supported_intervals_ms),
            "SUPPORTED_AGGREGATIONS": list(self.supported_aggregations),
            "DEFAULT_INTERVAL_MS": self.default_interval_ms,
        }


def _coerce_int_field(value: JSONValue | None, *, default: int, minimum: int) -> int:
    parsed = coerce_int_from_numberish(value)
    if parsed is None or parsed < minimum:
        return default
    return parsed


def _resolve_default_interval_ms(
    config_mapping: Mapping[str, JSONValue],
    *,
    supported_intervals_ms: tuple[int, ...],
    logging_interval_ms: int,
    default_interval_default: int | None,
) -> int:
    if not supported_intervals_ms:
        return logging_interval_ms
    default_interval_value = config_mapping.get("DEFAULT_INTERVAL_MS")
    default_interval_ms = _coerce_int_field(
        default_interval_value,
        default=(
            default_interval_default
            if default_interval_default is not None
            else supported_intervals_ms[0]
        ),
        minimum=supported_intervals_ms[0],
    )
    if default_interval_ms in supported_intervals_ms:
        return default_interval_ms
    for supported_interval_ms in supported_intervals_ms:
        if supported_interval_ms >= logging_interval_ms:
            return supported_interval_ms
    return supported_intervals_ms[-1]


def build_history_config_view(
    history_config: Mapping[str, JSONValue] | None,
    *,
    enabled_default: bool,
    logging_interval_default: int,
    max_points_default: int,
    retention_hours_default: int,
    supported_intervals_default: Sequence[int],
    supported_aggregations_default: Sequence[str],
    mandatory_aggregations: Sequence[str] = (),
    logging_interval_minimum: int = 1,
    max_points_minimum: int = 1,
    retention_hours_minimum: int = 0,
    default_interval_default: int | None = None,
    include_logging_interval_in_supported_intervals: bool = True,
    allow_empty_intervals: bool = False,
) -> HistoryConfigView:
    config_mapping: Mapping[str, JSONValue] = history_config if history_config is not None else {}
    logging_interval_ms = _coerce_int_field(
        config_mapping.get("LOGGING_INTERVAL_MS"),
        default=logging_interval_default,
        minimum=logging_interval_minimum,
    )
    max_points = _coerce_int_field(
        config_mapping.get("MAX_POINTS"),
        default=max_points_default,
        minimum=max_points_minimum,
    )
    retention_hours = _coerce_int_field(
        config_mapping.get("DB_RETENTION_HOURS"),
        default=retention_hours_default,
        minimum=retention_hours_minimum,
    )
    interval_candidates = normalize_interval_candidates(
        config_mapping.get("SUPPORTED_INTERVALS_MS"),
    )
    supported_intervals = sanitize_supported_intervals(
        interval_candidates,
        (
            logging_interval_ms
            if include_logging_interval_in_supported_intervals and logging_interval_ms > 0
            else None
        ),
        extra_defaults=tuple(int(value) for value in supported_intervals_default),
        allow_empty=allow_empty_intervals or logging_interval_ms <= 0,
    )
    aggregation_candidates = normalize_str_candidates(config_mapping.get("SUPPORTED_AGGREGATIONS"))
    supported_aggregations = normalize_aggregations(
        (
            aggregation_candidates
            if aggregation_candidates is not None
            else supported_aggregations_default
        ),
        mandatory=tuple(str(value) for value in mandatory_aggregations),
    )
    default_interval_ms = _resolve_default_interval_ms(
        config_mapping,
        supported_intervals_ms=tuple(supported_intervals),
        logging_interval_ms=logging_interval_ms,
        default_interval_default=default_interval_default,
    )
    return HistoryConfigView(
        enabled=parse_bool(config_mapping.get("ENABLED", enabled_default), default=enabled_default),
        logging_interval_ms=logging_interval_ms,
        max_points=max_points,
        retention_hours=retention_hours,
        supported_intervals_ms=tuple(supported_intervals),
        supported_aggregations=tuple(supported_aggregations),
        default_interval_ms=default_interval_ms,
    )
