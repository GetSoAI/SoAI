"""SoAI - Typed metrics manager payloads and tree aliases [backend/metrics/manager/types.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections import deque
from typing import TYPE_CHECKING, TypedDict

if TYPE_CHECKING:
    from core.types.json import JSONPrimitive

    type MetricScalar = JSONPrimitive
    type MetricLeaf = MetricScalar | list["MetricValue"] | dict[str, "MetricValue"]
    type MetricValue = MetricLeaf | deque[float] | set[str] | deque[tuple[float, str]]
    type MetricsTree = dict[str, MetricValue]
    type MetricsWorkerArg = str | int | float
    type MetricsWorkerOptionValue = str | int | float | bool | None
    type MetricsWorkerArgs = tuple[MetricsWorkerArg, ...]
    type MetricsWorkerQueueItem = tuple[str, MetricsWorkerPayload] | None
else:
    MetricScalar = str | int | float | bool | None
    MetricLeaf = MetricScalar | list["MetricValue"] | dict[str, "MetricValue"]
    MetricValue = MetricLeaf | deque[float] | set[str] | deque[tuple[float, str]]
    MetricsTree = dict[str, MetricValue]
    MetricsWorkerArg = str | int | float
    MetricsWorkerOptionValue = str | int | float | bool | None
    MetricsWorkerArgs = tuple[MetricsWorkerArg, ...]
    MetricsWorkerQueueItem = tuple[str, "MetricsWorkerPayload"] | None

__all__ = ("MetricsWorkerPayload",)


class MetricsWorkerPayload(TypedDict):
    args: MetricsWorkerArgs
    options: dict[str, MetricsWorkerOptionValue]
