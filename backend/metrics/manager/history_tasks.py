"""SoAI - Metrics history periodic task execution [backend/metrics/manager/history_tasks.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from metrics.manager.history import log_historical_metrics, prune_historical_metrics

if TYPE_CHECKING:
    from core.metrics.protocols import DatabaseMetricsProtocol
    from core.types.json import JSONDict
    from metrics.manager.types import MetricsTree

__all__ = (
    "log_historical_metrics_if_enabled",
    "prune_historical_metrics_if_enabled",
)


async def log_historical_metrics_if_enabled(
    *,
    history_enabled: bool,
    snapshot_metrics: Callable[[], Awaitable[MetricsTree]],
    history_config: JSONDict,
    database_metrics: DatabaseMetricsProtocol,
) -> None:
    if not history_enabled:
        return
    snapshot = await snapshot_metrics()
    await log_historical_metrics(snapshot, history_config, database_metrics)


async def prune_historical_metrics_if_enabled(
    *,
    history_enabled: bool,
    history_config: JSONDict,
    database_metrics: DatabaseMetricsProtocol,
) -> None:
    if not history_enabled:
        return
    await prune_historical_metrics(history_config, database_metrics)
