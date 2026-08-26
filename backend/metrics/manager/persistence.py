"""SoAI - Metrics persistence helpers [backend/metrics/manager/persistence.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections import defaultdict
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from core.metrics.keyspace_base import METRIC_BLOCK_GENESIS
from core.serialization.json import (
    normalize_for_json,
    serialize_json_compact_stable_strict,
)

if TYPE_CHECKING:
    from metrics.manager.types import MetricsTree, MetricValue

__all__ = (
    "flatten_metrics",
    "flush_metrics_to_database",
    "prepare_metrics_for_upsert",
)


def prepare_metrics_for_upsert(
    flat_metrics: dict[str, MetricValue],
    timestamp: int,
) -> list[tuple[str, str, int]]:
    return [
        (key, serialize_json_compact_stable_strict(normalize_for_json(value)), timestamp)
        for key, value in flat_metrics.items()
        if value is not None
    ]


async def flush_metrics_to_database(
    snapshot_fn: Callable[[], Awaitable[MetricsTree]],
    flatten_fn: Callable[[MetricsTree], dict[str, MetricValue]],
    upsert_fn: Callable[[list[tuple[str, str, int]]], Awaitable[None]],
    get_timestamp: Callable[[], int],
) -> None:
    metrics_copy = await snapshot_fn()
    metrics_copy.pop(METRIC_BLOCK_GENESIS, None)
    flat_metrics = flatten_fn(metrics_copy)
    metrics_to_upsert = prepare_metrics_for_upsert(flat_metrics, get_timestamp())
    await upsert_fn(metrics_to_upsert)


def flatten_metrics(metrics_dict: MetricsTree) -> dict[str, MetricValue]:
    flat_metrics: dict[str, MetricValue] = {}

    def flatten_recursive(metrics_node: dict[str, MetricValue], prefix: str = "") -> None:
        for key, value in metrics_node.items():
            new_key = f"{prefix}.{key}" if prefix else key
            if isinstance(value, dict | defaultdict):
                if key.endswith("_stats"):
                    flat_metrics[new_key] = value
                    for sub_key, sub_value in value.items():
                        sub_path = f"{new_key}.{sub_key}"
                        flat_metrics[sub_path] = sub_value
                else:
                    flatten_recursive(value, new_key)
            else:
                flat_metrics[new_key] = value

    flatten_recursive(metrics_dict)
    return flat_metrics
