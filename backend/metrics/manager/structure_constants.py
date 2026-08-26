"""SoAI - Metrics structure constants and shared builders [backend/metrics/manager/structure_constants.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections import defaultdict, deque
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from metrics.manager.types import MetricValue

__all__ = (
    "create_counter_map",
    "create_dynamic_counter_map",
    "create_timing_deque",
    "create_timing_map",
    "create_unique_tracker",
)

TIMING_DEQUE_SIZE = 100
UNIQUE_ITEMS_WINDOW_SEC = 3600
UNIQUE_ITEMS_MAX_CARDINALITY = 10000


def create_unique_tracker() -> dict[str, MetricValue]:
    items: set[str] = set()
    timestamps: deque[tuple[float, str]] = deque()
    counts: dict[str, MetricValue] = {}
    return {"items": items, "timestamps": timestamps, "counts": counts}


def create_timing_deque(maxlen: int = TIMING_DEQUE_SIZE) -> deque[float]:
    return deque[float](maxlen=maxlen)


def create_timing_map(*keys: str, maxlen: int = TIMING_DEQUE_SIZE) -> dict[str, MetricValue]:
    return {key: create_timing_deque(maxlen) for key in keys}


def create_counter_map(*keys: str) -> dict[str, MetricValue]:
    return dict.fromkeys(keys, 0)


def create_dynamic_counter_map() -> dict[str, MetricValue]:
    counters: dict[str, MetricValue] = defaultdict(int)
    return counters
