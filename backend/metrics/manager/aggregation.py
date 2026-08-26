"""SoAI - Metrics aggregation helpers [backend/metrics/manager/aggregation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.errors.exception_logging import log_exception
from core.errors.exceptions import ProcessError
from core.logging.trace import get_logger
from core.metrics.keyspace_base import DIRECTOR_GAUGE_REQUEST_LATENCY_MS
from metrics.manager.type_guards import is_float_deque

if TYPE_CHECKING:
    from metrics.manager.types import MetricValue

__all__ = (
    "StatisticsSnapshot",
    "compute_statistics",
    "extract_tracked_metrics",
    "get_metric_by_dotted_path",
)

LOGGER_NAME = "SoAI.metrics.manager.aggregation"
OPERATION = "metrics_manager.compute_statistics"


@dataclass(frozen=True, slots=True)
class StatisticsSnapshot:
    count: int
    avg: float
    min: float
    max: float
    p95: float

    def to_payload(self) -> dict[str, MetricValue]:
        return {
            "count": self.count,
            "avg": self.avg,
            "min": self.min,
            "max": self.max,
            "p95": self.p95,
        }


def compute_statistics(data: list[float]) -> StatisticsSnapshot:
    logger = get_logger(LOGGER_NAME)
    if not data:
        return StatisticsSnapshot(count=0, avg=0.0, min=0.0, max=0.0, p95=0.0)
    try:
        count = len(data)
        if count == 1:
            value = round(data[0], 4)
            return StatisticsSnapshot(count=1, avg=value, min=value, max=value, p95=value)
        sorted_data = sorted(data)
        p95_index = min(count - 1, max(0, math.ceil(count * 0.95) - 1))
        return StatisticsSnapshot(
            count=count,
            avg=round(statistics.mean(data), 4),
            min=round(sorted_data[0], 4),
            max=round(sorted_data[-1], 4),
            p95=round(sorted_data[p95_index], 4),
        )
    except TypeError as exception:
        log_exception(
            logger,
            exception,
            message="Non-numeric data found in timing deque",
            operation=OPERATION,
            level="warning",
        )
        raise ProcessError(
            "Metrics statistics computation failed due to non-numeric data.",
            details={"reason": str(exception)},
        ) from exception


def get_metric_by_dotted_path(metrics_root: MetricValue, path: str) -> MetricValue | None:
    parts = path.split(".")
    stats_index = None
    stat_key = None
    for index, part in enumerate(parts):
        if part.endswith("_stats"):
            stats_index = index
            stat_key = parts[index + 1] if index + 1 < len(parts) else None
            break
    if stats_index is not None:
        stats_segment = parts[stats_index]
        if not stats_segment.endswith("_stats"):
            return None
        metric_name = stats_segment[: -len("_stats")]
        if not metric_name:
            return None
        deque_path_parts = parts[:stats_index] + [metric_name]
        current: MetricValue = metrics_root
        for part in deque_path_parts:
            if not isinstance(current, dict):
                return None
            next_value = current.get(part)
            if next_value is None:
                return None
            current = next_value
        if not is_float_deque(current):
            return None
        stats = compute_statistics(list(current))
        if stat_key is None:
            return stats.to_payload()
        match stat_key:
            case "count":
                return stats.count
            case "avg":
                return stats.avg
            case "min":
                return stats.min
            case "max":
                return stats.max
            case "p95":
                return stats.p95
            case _:
                return None
    current = metrics_root
    for part in parts:
        if not isinstance(current, dict):
            return None
        next_value = current.get(part)
        if next_value is None:
            return None
        current = next_value
    return current


def extract_tracked_metrics(
    metrics_root: MetricValue,
    tracked_keys: list[str],
) -> dict[str, int | float]:
    result: dict[str, int | float] = {}
    for key in tracked_keys:
        if "_stats." in key:
            stat_suffix_index = key.rfind("_stats.")
            deque_path = key[:stat_suffix_index]
            stat_name = key[stat_suffix_index + len("_stats.") :]
            deque_value = get_metric_by_dotted_path(metrics_root, deque_path)
            if deque_value is not None and is_float_deque(deque_value):
                computed_stats = compute_statistics(list(deque_value))
                stat_value: int | float | None
                match stat_name:
                    case "count":
                        stat_value = computed_stats.count
                    case "avg":
                        stat_value = computed_stats.avg
                    case "min":
                        stat_value = computed_stats.min
                    case "max":
                        stat_value = computed_stats.max
                    case "p95":
                        stat_value = computed_stats.p95
                    case _:
                        stat_value = None
                if stat_value is not None and (
                    not isinstance(stat_value, float) or math.isfinite(stat_value)
                ):
                    result[key] = stat_value
            continue
        value = get_metric_by_dotted_path(metrics_root, key)
        if isinstance(value, int | float) and (
            not isinstance(value, float) or math.isfinite(value)
        ):
            if value <= 0 and key == ".".join(DIRECTOR_GAUGE_REQUEST_LATENCY_MS):
                continue
            result[key] = value
    return result
