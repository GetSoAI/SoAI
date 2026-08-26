"""SoAI - Metrics manager background queue and worker bootstrap [backend/metrics/manager/background_worker_bootstrap.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Coroutine
from typing import TYPE_CHECKING

from core.config.numeric import coerce_positive_int
from core.config.protocols import ConfigProtocol
from core.runtime.soai_identifiers import create_system_id
from core.tasks.asyncio_task_spawner import spawn_tracked_task

if TYPE_CHECKING:
    from core.logging.protocols import LoggerProtocol
    from core.tasks.protocols import (
        TaskCancellationBinderProtocol,
        TaskFinalizerTrackerProtocol,
    )
    from metrics.manager.types import MetricsWorkerQueueItem

__all__ = ("create_background_worker_runtime",)


def create_background_worker_runtime(
    *,
    config: ConfigProtocol,
    background_worker: Coroutine[None, None, None],
    cancellation_binder: TaskCancellationBinderProtocol,
    finalizer_tracker: TaskFinalizerTrackerProtocol,
    logger: LoggerProtocol,
) -> tuple[asyncio.Queue[MetricsWorkerQueueItem], asyncio.Task[None]]:
    max_queue_size = coerce_positive_int(
        config.get("OBSERVABILITY.METRICS.BACKGROUND_QUEUE_MAXSIZE", 100000),
        default=100000,
        minimum=1,
    )
    background_queue: asyncio.Queue[MetricsWorkerQueueItem] = asyncio.Queue(maxsize=max_queue_size)
    background_worker_task: asyncio.Task[None] = spawn_tracked_task(
        background_worker,
        cancellation_binder=cancellation_binder,
        finalizer_tracker=finalizer_tracker,
        cancellation_id=create_system_id(
            subsystem="metrics_manager",
            owner="background_worker",
            include_random_suffix=False,
        ),
        owner="metrics_background_worker",
        name="metrics-manager-background-worker",
        logger=logger,
    )
    return background_queue, background_worker_task
