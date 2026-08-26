"""SoAI - Metrics manager periodic task scheduling [backend/metrics/manager/scheduling.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from core.config.numeric_lenient import coerce_lenient_positive_int
from core.timing.durations import ms_to_seconds_ceil
from metrics.manager.configuration import build_metrics_history_view

if TYPE_CHECKING:
    from core.config.protocols import ConfigProtocol
    from core.types.json import JSONDict

    type PeriodicTaskConfig = tuple[float, Callable[[], Awaitable[None]], str, bool]

__all__ = ("build_periodic_task_configs",)


def build_periodic_task_configs(
    config: ConfigProtocol,
    history_config: JSONDict,
    history_enabled: bool,
    has_event_bus: bool,
    prune_unique_items: Callable[[], Awaitable[None]],
    flatten_and_flush_metrics: Callable[[], Awaitable[None]],
    flush_genesis_deltas: Callable[[], Awaitable[None]],
    log_historical_metrics: Callable[[], Awaitable[None]],
    prune_historical_metrics: Callable[[], Awaitable[None]],
    broadcast_metrics: Callable[[], Awaitable[None]],
) -> list[PeriodicTaskConfig]:
    configs: list[PeriodicTaskConfig] = [
        (60, prune_unique_items, "cleanup", False),
        (30, flatten_and_flush_metrics, "db_flush", False),
        (60, flush_genesis_deltas, "genesis_flush", False),
    ]
    history_view = build_metrics_history_view(history_config, history_enabled)
    if history_enabled:
        configs.append(
            (
                ms_to_seconds_ceil(history_view.logging_interval_ms),
                log_historical_metrics,
                "metrics_history_log",
                True,
            ),
        )
        configs.append(
            (
                coerce_lenient_positive_int(
                    history_config.get("PRUNING_INTERVAL_SEC"),
                    default=300,
                ),
                prune_historical_metrics,
                "metrics_history_prune",
                False,
            ),
        )
    if has_event_bus:
        broadcast_interval_ms = coerce_lenient_positive_int(
            config.get("OBSERVABILITY.METRICS.BROADCAST_INTERVAL_MS"),
            default=1000,
        )
        broadcast_interval_seconds = max(0.001, float(broadcast_interval_ms) / 1000.0)
        configs.append(
            (
                broadcast_interval_seconds,
                broadcast_metrics,
                "metrics_broadcast",
                False,
            ),
        )
    return configs
