"""SoAI - Metrics periodic task scheduling [backend/metrics/manager/periodic_tasks.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from core.concurrency.task_groups import ManagedTaskGroup
from core.logging.protocols import LoggerProtocol
from core.runtime.soai_identifiers import create_system_id
from core.tasks.progress import schedule_periodic_task
from metrics.manager.scheduling import build_periodic_task_configs

if TYPE_CHECKING:
    from core.config.protocols import ConfigProtocol
    from core.tasks.protocols import (
        TaskCancellationBinderProtocol,
        TaskFinalizerTrackerProtocol,
    )
    from core.types.json import JSONDict

__all__ = ("schedule_metrics_periodic_tasks",)


def schedule_metrics_periodic_tasks(
    *,
    logger: LoggerProtocol,
    config: ConfigProtocol,
    history_config: JSONDict,
    history_enabled: bool,
    has_event_bus: bool,
    cleanup_metrics_state: Callable[[], Awaitable[None]],
    flatten_and_flush_metrics: Callable[[], Awaitable[None]],
    flush_genesis_deltas: Callable[[], Awaitable[None]],
    log_historical_metrics: Callable[[], Awaitable[None]],
    prune_historical_metrics: Callable[[], Awaitable[None]],
    broadcast_metrics: Callable[[], Awaitable[None]],
    shutdown_event: asyncio.Event,
    cancellation_binder: TaskCancellationBinderProtocol,
    finalizer_tracker: TaskFinalizerTrackerProtocol,
    periodic_tasks: ManagedTaskGroup,
) -> None:
    configs = build_periodic_task_configs(
        config=config,
        history_config=history_config,
        history_enabled=history_enabled,
        has_event_bus=has_event_bus,
        prune_unique_items=cleanup_metrics_state,
        flatten_and_flush_metrics=flatten_and_flush_metrics,
        flush_genesis_deltas=flush_genesis_deltas,
        log_historical_metrics=log_historical_metrics,
        prune_historical_metrics=prune_historical_metrics,
        broadcast_metrics=broadcast_metrics,
    )
    for interval, task_func, name, run_immediately in configs:
        periodic_task = schedule_periodic_task(
            shutdown_event=shutdown_event,
            interval_seconds=interval,
            task=task_func,
            cancellation_binder=cancellation_binder,
            finalizer_tracker=finalizer_tracker,
            cancellation_id=create_system_id(
                subsystem="metrics_manager",
                owner=name,
                include_random_suffix=False,
            ),
            owner="metrics_periodic_task",
            name=f"metrics-manager-periodic-{name}",
            logger=logger,
            metadata={"interval_ms": int(max(0.0, float(interval)) * 1000.0)},
            task_name=name,
            run_immediately=run_immediately,
        )
        _ = periodic_tasks.track(periodic_task)
