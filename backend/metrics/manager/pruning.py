"""SoAI - Metrics pruning and statistics [backend/metrics/manager/pruning.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import time
from collections import deque
from typing import TYPE_CHECKING

from core.validation.integers import is_strict_int
from metrics.manager.aggregation import compute_statistics
from metrics.manager.structure_constants import UNIQUE_ITEMS_WINDOW_SEC

if TYPE_CHECKING:
    from metrics.manager.types import MetricsTree, MetricValue

__all__ = (
    "calculate_stats_recursive",
    "prune_unique_items",
)


async def prune_unique_items(
    lock: asyncio.Lock,
    metrics: MetricsTree,
) -> None:
    cutoff = time.monotonic() - UNIQUE_ITEMS_WINDOW_SEC

    async def prune_recursive(
        node: dict[str, MetricValue],
    ) -> None:
        items = node.get("items")
        timestamps = node.get("timestamps")
        counts = node.get("counts")
        if isinstance(items, set) and isinstance(timestamps, deque) and isinstance(counts, dict):
            counts_typed: dict[str, MetricValue] = {}
            for key, value in counts.items():
                if not isinstance(key, str):
                    continue
                if not is_strict_int(value):
                    continue
                counts_typed[key] = value
            node["counts"] = counts_typed
            while timestamps:
                head = timestamps[0]
                if not isinstance(head, tuple) or len(head) != 2:
                    timestamps.popleft()
                    continue
                ts_raw, label_raw = head
                if not isinstance(ts_raw, int | float):
                    timestamps.popleft()
                    continue
                ts_float: float = float(ts_raw)
                label: str = str(label_raw)
                if ts_float >= cutoff:
                    break
                timestamps.popleft()
                current_value = counts_typed.get(label, 0)
                current = int(current_value) if is_strict_int(current_value) else 0
                if current <= 1:
                    counts_typed.pop(label, None)
                    items.discard(label)
                else:
                    counts_typed[label] = current - 1
            return

        for value in node.values():
            if isinstance(value, dict):
                await prune_recursive(value)
            elif isinstance(value, list):
                for entry in value:
                    if isinstance(entry, dict):
                        await prune_recursive(entry)

    async with lock:
        await prune_recursive(metrics)


def calculate_stats_recursive(
    node: MetricValue,
) -> None:
    if isinstance(node, dict):
        items = node.get("items")
        timestamps = node.get("timestamps")
        counts = node.get("counts")
        if isinstance(items, set) and isinstance(timestamps, deque) and isinstance(counts, dict):
            node["cardinality_1h"] = sum(
                1 for value in counts.values() if isinstance(value, int) and value > 0
            )
            node.pop("items", None)
            node.pop("timestamps", None)
            node.pop("counts", None)
            return
        metric_node: dict[str, MetricValue] = node
        for key, value in list(metric_node.items()):
            if isinstance(value, deque):
                numeric_values: list[float] = []
                valid_timing_values = True
                for entry in value:
                    if not isinstance(entry, int | float):
                        valid_timing_values = False
                        break
                    numeric_values.append(float(entry))
                if valid_timing_values:
                    stats = compute_statistics(numeric_values)
                    metric_node[f"{key}_stats"] = stats.to_payload()
            elif isinstance(value, dict):
                calculate_stats_recursive(value)
