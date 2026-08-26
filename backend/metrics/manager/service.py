"""SoAI - Metrics collection aggregation and historical tracking service [backend/metrics/manager/service.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, override

from core.history.config_view import build_history_config_view
from core.logging.trace import get_logger
from core.runtime.protocols import Shutdownable
from core.tasks.action_queue import run_action_queue_processor_until_sentinel
from core.timing.epoch import epoch_ms
from core.timing.monotonic import monotonic_ms
from metrics.manager.background_worker_bootstrap import create_background_worker_runtime
from metrics.manager.configuration import (
    MAX_BILLING_CLIENT_CARDINALITY,
    build_history_config_from_raw,
    require_managed_task_group,
)
from metrics.manager.dependencies import MetricsManagerDependencies
from metrics.manager.genesis import load_genesis_data
from metrics.manager.history_tasks import (
    log_historical_metrics_if_enabled,
    prune_historical_metrics_if_enabled,
)
from metrics.manager.internal_protocols import TokenRateCalculatorProtocol
from metrics.manager.lifecycle import drain_background_queue, finalize_shutdown
from metrics.manager.operations import MetricsQueueFullThrottle
from metrics.manager.periodic_tasks import schedule_metrics_periodic_tasks
from metrics.manager.public_operations import MetricsManagerOperations
from metrics.manager.state_cleanup import (
    cleanup_metrics_state,
    prune_deleted_plugin_metrics,
)
from metrics.manager.structure_factory import create_metrics_structure
from metrics.manager.trackers import TokenRateTracker
from metrics.manager.worker import create_worker_handlers

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from metrics.manager.types import (
        MetricsTree,
        MetricsWorkerQueueItem,
    )

__all__ = ("MetricsManager",)

LOGGER_NAME = "SoAI.metrics.manager.service"


class MetricsManager(MetricsManagerOperations, Shutdownable):
    def __init__(self, deps: MetricsManagerDependencies) -> None:
        self._deps = deps
        self.config = deps.config
        self.database_metrics = deps.database_metrics
        self.database_hardware = deps.database_hardware
        self.database_plugins = deps.database_plugins
        self.event_bus = deps.event_bus
        self.lock = asyncio.Lock()
        self.lifecycle = deps.lifecycle
        self._shutdown_event = self.lifecycle.shutdown_event
        self.cancellation_binder = self.lifecycle.cancellation_binder
        self._periodic_tasks = require_managed_task_group(self.lifecycle)
        self.token_rate_calculator: TokenRateCalculatorProtocol = TokenRateTracker()
        self.background_queue: asyncio.Queue[MetricsWorkerQueueItem] | None = None
        self.background_worker_task: asyncio.Task[None] | None = None
        self.accepting_operations: bool = False
        self._started: bool = False
        self.session_start_time_ms: int = epoch_ms()
        self._session_start_time_monotonic_ms: int = monotonic_ms()
        self.genesis_requests_delta: list[int] = [0]
        self.genesis_tokens_delta: list[int] = [0]
        self.genesis_flush_lock: asyncio.Lock = asyncio.Lock()
        self.queue_full_throttle: MetricsQueueFullThrottle = MetricsQueueFullThrottle()
        self._capabilities_cache: JSONDict | None = None
        self._capabilities_cache_timestamp: float = 0.0
        self._metrics_ref: list[MetricsTree] = [
            create_metrics_structure(self.session_start_time_ms),
        ]
        self.history_config, self.history_enabled = build_history_config_from_raw(
            self.config.get("OBSERVABILITY.METRICS.METRICS_HISTORY", {}),
        )

    @property
    def interval(self) -> int | None:
        try:
            history_config = self.history_config
        except AttributeError:
            return None
        history_view = build_history_config_view(
            history_config,
            enabled_default=False,
            logging_interval_default=0,
            max_points_default=1,
            retention_hours_default=0,
            supported_intervals_default=(),
            supported_aggregations_default=(),
        )
        if history_view.logging_interval_ms <= 0:
            return None
        return history_view.logging_interval_ms

    @property
    def metrics_ref(self) -> list[MetricsTree]:
        return self._metrics_ref

    @property
    def capabilities_cache(self) -> JSONDict | None:
        return self._capabilities_cache

    @capabilities_cache.setter
    def capabilities_cache(self, value: JSONDict | None) -> None:
        self._capabilities_cache = value

    @property
    def capabilities_cache_timestamp(self) -> float:
        return self._capabilities_cache_timestamp

    @capabilities_cache_timestamp.setter
    def capabilities_cache_timestamp(self, value: float) -> None:
        self._capabilities_cache_timestamp = value

    @property
    def session_start_time_monotonic_ms(self) -> int:
        return self._session_start_time_monotonic_ms

    async def snapshot_metrics(self) -> MetricsTree:
        return await self._snapshot_metrics()

    async def start(self) -> None:
        logger = get_logger(LOGGER_NAME)
        if self._shutdown_event.is_set():
            logger.warning("MetricsManager cannot be started after shutdown.")
            return
        if self._started:
            logger.debug("MetricsManager start requested while already running; ignoring.")
            return
        if self.background_worker_task is None or self.background_worker_task.done():
            self.background_queue, self.background_worker_task = create_background_worker_runtime(
                config=self.config,
                background_worker=self.background_worker(),
                cancellation_binder=self.cancellation_binder,
                finalizer_tracker=self.lifecycle.finalizer_tracker,
                logger=logger,
            )
            logger.debug("MetricsManager background worker started.")
        await self.database_metrics.initialize_genesis(epoch_ms())
        await self._rehydrate_from_db()
        await load_genesis_data(self.lock, self._metrics_ref[0], self.database_metrics)
        await prune_deleted_plugin_metrics(
            lock=self.lock,
            metrics_ref=self._metrics_ref,
            database_plugins=self.database_plugins,
            logger=logger,
        )
        schedule_metrics_periodic_tasks(
            logger=logger,
            config=self.config,
            history_config=self.history_config,
            history_enabled=self.history_enabled,
            has_event_bus=self.event_bus is not None,
            cleanup_metrics_state=lambda: cleanup_metrics_state(
                lock=self.lock,
                metrics_ref=self._metrics_ref,
                database_plugins=self.database_plugins,
                logger=logger,
            ),
            flatten_and_flush_metrics=self._flatten_and_flush_metrics,
            flush_genesis_deltas=self._flush_genesis_deltas,
            log_historical_metrics=lambda: log_historical_metrics_if_enabled(
                history_enabled=self.history_enabled,
                snapshot_metrics=self._snapshot_metrics,
                history_config=self.history_config,
                database_metrics=self.database_metrics,
            ),
            prune_historical_metrics=lambda: prune_historical_metrics_if_enabled(
                history_enabled=self.history_enabled,
                history_config=self.history_config,
                database_metrics=self.database_metrics,
            ),
            broadcast_metrics=self._broadcast_metrics,
            shutdown_event=self._shutdown_event,
            cancellation_binder=self.cancellation_binder,
            finalizer_tracker=self.lifecycle.finalizer_tracker,
            periodic_tasks=self._periodic_tasks,
        )
        self.accepting_operations = True
        self._started = True
        logger.debug("MetricsManager background tasks started.")

    @override
    async def shutdown(self) -> None:
        logger = get_logger(LOGGER_NAME)
        if self._shutdown_event.is_set():
            return
        logger.debug("MetricsManager shutdown initiated.")
        self.accepting_operations = False
        await drain_background_queue(self.background_queue, self.background_worker_task)
        self._shutdown_event.set()
        await finalize_shutdown(
            self._periodic_tasks,
            self._session_start_time_monotonic_ms,
            self.database_metrics,
            self._flush_genesis_deltas,
            self._flatten_and_flush_metrics,
        )
        self._started = False

    async def background_worker(self) -> None:
        logger = get_logger(LOGGER_NAME)
        if not self.background_queue:
            logger.warning("Background queue not initialised; worker exiting.")
            return
        handlers = create_worker_handlers(
            lock=self.lock,
            metrics_ref=self._metrics_ref,
            genesis_flush_lock=self.genesis_flush_lock,
            genesis_requests_delta=self.genesis_requests_delta,
            genesis_tokens_delta=self.genesis_tokens_delta,
            database_hardware=self.database_hardware,
            database_metrics=self.database_metrics,
            max_billing_client_cardinality=MAX_BILLING_CLIENT_CARDINALITY,
        )
        await run_action_queue_processor_until_sentinel(
            self.background_queue,
            handlers=handlers,
            logger=logger,
            on_unknown_action=lambda action, _: logger.warning(
                "Received unknown metrics operation '%s'.",
                action,
            ),
        )
