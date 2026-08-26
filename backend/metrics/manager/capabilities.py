"""SoAI - Metrics catalog generation from the metrics tree [backend/metrics/manager/capabilities.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections import defaultdict, deque
from collections.abc import Sequence
from typing import TYPE_CHECKING

from metrics.manager.configuration import build_metrics_history_view

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from metrics.manager.types import MetricsTree, MetricValue

__all__ = (
    "build_capabilities_response",
    "generate_metrics_catalog",
    "infer_scalar_unit",
    "infer_timing_unit",
)


def infer_timing_unit(name: str) -> str:
    _ = name
    return "ms"


def infer_scalar_unit(path: str) -> str:
    parts = [segment for segment in path.split(".") if segment and segment != "*"]
    if not parts:
        return "count"
    name = parts[-1].lower()
    if name.endswith("_ms") or "latency" in name or "duration" in name:
        return "ms"
    if "token" in name:
        return "tokens"
    if "bytes" in name:
        return "bytes"
    return "count"


def generate_metrics_catalog(
    metrics_tree: MetricsTree,
    history_aggregations: Sequence[str],
) -> dict[str, JSONDict]:
    catalog: dict[str, JSONDict] = {}
    timing_stats: tuple[str, ...] = ("avg", "min", "max", "p95", "count")
    bounded_defaultdict_children: dict[str, tuple[str, ...]] = {
        "director.requests": (
            "queued",
            "completed",
            "failed",
            "cancelled",
            "fast_path",
            "express_path",
            "deduplicated",
        ),
    }

    def _add_timing_entries(path: str, *, unit: str) -> None:
        catalog[path] = {
            "type": "timing",
            "unit": unit,
            "aggregations": list(timing_stats),
        }
        for stat_name in timing_stats:
            derived_key = f"{path}_stats.{stat_name}"
            derived_unit = unit if stat_name != "count" else "count"
            catalog[derived_key] = {
                "type": "gauge_or_counter",
                "unit": derived_unit,
                "aggregations": list(history_aggregations),
            }

    def _add_unique_cardinality_entry(path: str) -> None:
        catalog[f"{path}.cardinality_1h"] = {
            "type": "gauge_or_counter",
            "unit": "count",
            "aggregations": list(history_aggregations),
        }

    def _add_string_entry(path: str) -> None:
        catalog[path] = {
            "type": "label",
            "unit": "text",
            "aggregations": [],
        }

    def _add_boolean_entry(path: str) -> None:
        catalog[path] = {
            "type": "state",
            "unit": "boolean",
            "aggregations": [],
        }

    def traverse(node: MetricValue, prefix: str = "") -> None:
        if isinstance(node, deque):
            _add_timing_entries(prefix, unit=infer_timing_unit(prefix))
            return
        if isinstance(node, bool):
            _add_boolean_entry(prefix)
            return
        if isinstance(node, str):
            _add_string_entry(prefix)
            return
        if isinstance(node, int | float):
            catalog[prefix] = {
                "type": "gauge_or_counter",
                "unit": infer_scalar_unit(prefix),
                "aggregations": list(history_aggregations),
            }
            return
        if isinstance(node, dict) and {"items", "timestamps", "counts"}.issubset(node.keys()):
            _add_unique_cardinality_entry(prefix)
            return
        if isinstance(node, defaultdict):
            bounded = bounded_defaultdict_children.get(prefix)
            if bounded:
                for child_key in bounded:
                    traverse(
                        node.default_factory() if node.default_factory else 0,
                        f"{prefix}.{child_key}" if prefix else child_key,
                    )
                return
            default_factory = node.default_factory
            if default_factory is None:
                return
            template_value = default_factory()
            wildcard_prefix = f"{prefix}.*" if prefix else "*"
            if isinstance(template_value, dict | defaultdict | deque):
                traverse(template_value, wildcard_prefix)
                return
            if isinstance(template_value, bool):
                _add_boolean_entry(wildcard_prefix)
                return
            if isinstance(template_value, str):
                _add_string_entry(wildcard_prefix)
                return
            if isinstance(template_value, int | float):
                catalog[wildcard_prefix] = {
                    "type": "gauge_or_counter",
                    "unit": infer_scalar_unit(prefix),
                    "aggregations": list(history_aggregations),
                }
            return
        if isinstance(node, dict):
            for key, value in node.items():
                if key in (
                    "items",
                    "timestamps",
                    "counts",
                    "token_rates",
                ):
                    continue
                full_key = f"{prefix}.{key}" if prefix else key
                if key.endswith("_stats") and isinstance(value, dict | defaultdict):
                    continue
                traverse(value, full_key)

    traverse(metrics_tree)
    return catalog


def build_capabilities_response(
    metrics_snapshot: MetricsTree,
    history_config: JSONDict,
    history_enabled: bool,
) -> JSONDict:
    history_view = build_metrics_history_view(
        history_config,
        history_enabled,
        include_logging_interval_in_supported_intervals=False,
        allow_empty_intervals=True,
    )
    history_aggs: Sequence[str] = list(history_view.supported_aggregations)
    if history_enabled:
        intervals_payload = list(history_view.supported_intervals_ms)
    else:
        intervals_payload = []
    aggs_payload = list(history_view.supported_aggregations) if history_enabled else []
    default_interval_ms = (
        intervals_payload[0] if intervals_payload else history_view.logging_interval_ms
    )
    history_meta: JSONDict = {
        "enabled": history_enabled,
        "retention_hours": history_view.retention_hours,
        "logging_interval_ms": history_view.logging_interval_ms,
        "max_points": history_view.max_points,
        "supported_intervals_ms": [int(item) for item in intervals_payload],
        "default_interval_ms": int(default_interval_ms),
        "supported_aggregations": [str(item) for item in aggs_payload],
        "supports_ohlc": history_enabled and "ohlc" in history_view.supported_aggregations,
    }
    return {
        "metrics_catalog": generate_metrics_catalog(metrics_snapshot, history_aggs),
        "history_config": history_meta,
    }
