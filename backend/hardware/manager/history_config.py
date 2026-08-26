"""SoAI - Hardware history configuration parsing [backend/hardware/manager/history_config.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING

from core.config.numeric import coerce_positive_int
from core.history.config import build_history_config
from core.history.config_view import build_history_config_view
from core.history.intervals import DEFAULT_HISTORY_INTERVALS_MS
from core.validation.booleans import parse_bool

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = ("initialize_history_config",)


def initialize_history_config(*, config_dict: JSONDict, monitoring_interval_ms: int) -> JSONDict:
    raw_config = config_dict.get("HARDWARE_HISTORY_CONFIG")
    retention_default: JSONValue = config_dict.get("DB_RETENTION_HOURS", 120)
    retention_hours_default = coerce_positive_int(retention_default, default=120, minimum=1)
    monitoring_interval_ms = int(monitoring_interval_ms)
    history_config, enabled_flag = build_history_config(
        raw_config,
        logging_interval_default=monitoring_interval_ms,
        max_points_default=50000,
        retention_hours_default=retention_hours_default,
        intervals_defaults=DEFAULT_HISTORY_INTERVALS_MS,
        allow_empty_intervals=False,
        default_aggregations=["avg", "min", "max", "ohlc"],
        mandatory_aggregations=("avg", "min", "max", "ohlc"),
    )
    config_enabled = parse_bool(config_dict.get("HARDWARE_HISTORY_ENABLED", False), default=False)
    view = build_history_config_view(
        {
            **history_config,
            "ENABLED": enabled_flag or config_enabled,
            "DEFAULT_INTERVAL_MS": (
                raw_config.get("DEFAULT_INTERVAL_MS") if isinstance(raw_config, Mapping) else None
            ),
        },
        enabled_default=False,
        logging_interval_default=int(monitoring_interval_ms),
        max_points_default=50000,
        retention_hours_default=retention_hours_default,
        supported_intervals_default=DEFAULT_HISTORY_INTERVALS_MS,
        supported_aggregations_default=("avg", "min", "max", "ohlc"),
        mandatory_aggregations=("avg", "min", "max", "ohlc"),
        retention_hours_minimum=1,
    )
    return view.to_json_dict()
