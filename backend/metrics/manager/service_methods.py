"""SoAI - Metrics manager bound method implementations [backend/metrics/manager/service_methods.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.events.types_system import MetricsUpdatedEvent
from core.logging.trace import get_logger
from core.timing.epoch import epoch_ms
from metrics.manager.background_worker_bootstrap import create_background_worker_runtime
from metrics.manager.context_compaction import refresh_context_compaction_usage_metrics
from metrics.manager.genesis import flush_genesis_deltas
from metrics.manager.lifecycle import drain_background_queue
from metrics.manager.operation_surface import (
    increment_counter,
    increment_genesis_request,
    purge_plugin_metrics,
    record_historical_metric,
    record_modality_usage,
    record_timing,
    record_unique,
    set_gauge,
    update_download_speed_metrics,
)
from metrics.manager.operations import MetricsQueueFullThrottle
from metrics.manager.persistence import flatten_metrics, flush_metrics_to_database
from metrics.manager.query import snapshot_metrics_locked
from metrics.manager.rehydration.database import rehydrate_from_database
from metrics.manager.reset import reset_metrics_state
from metrics.manager.structure_factory import create_metrics_structure

if TYPE_CHECKING:
    from core.metrics.usage import ModalityUsageRecord
    from metrics.manager.internal_protocols import (
        MetricsOperationSurfaceOwnerProtocol,
        MetricsQuerySurfaceProtocol,
        MetricsServiceMethodSurfaceProtocol,
    )
    from metrics.manager.types import MetricsTree, MetricsWorkerArg

__all__ = (
    "broadcast_metrics_method",
    "flatten_and_flush_metrics_method",
    "flush_genesis_deltas_method",
    "increment_counter_method",
    "increment_genesis_request_method",
    "purge_plugin_metrics_method",
    "record_historical_metric_method",
    "record_modality_usage_method",
    "record_timing_method",
    "record_unique_method",
    "rehydrate_from_db_method",
    "reset_metrics_method",
    "set_gauge_method",
    "snapshot_metrics_method",
    "update_download_speed_metrics_method",
)

LOGGER_NAME = "SoAI.metrics.manager.service_methods"


def increment_counter_method(
    self: MetricsOperationSurfaceOwnerProtocol,
    *keys: str,
    value: int = 1,
) -> None:
    increment_counter(self, *keys, value=value)


def set_gauge_method(
    self: MetricsOperationSurfaceOwnerProtocol,
    *keys: str,
    value: float,
) -> None:
    set_gauge(self, *keys, value=value)


def record_timing_method(
    self: MetricsOperationSurfaceOwnerProtocol,
    *keys: str,
    duration_ms: float,
) -> None:
    record_timing(self, *keys, duration_ms=duration_ms)


def record_historical_metric_method(
    self: MetricsOperationSurfaceOwnerProtocol,
    metric_key: str,
    value: float,
    observed_at_ms: int | None = None,
) -> None:
    record_historical_metric(self, metric_key, value, observed_at_ms=observed_at_ms)


def record_unique_method(
    self: MetricsOperationSurfaceOwnerProtocol,
    *keys: str,
    item: MetricsWorkerArg,
) -> None:
    record_unique(self, *keys, item=item)


def record_modality_usage_method(
    self: MetricsOperationSurfaceOwnerProtocol,
    record: ModalityUsageRecord,
) -> None:
    record_modality_usage(self, record)


def update_download_speed_metrics_method(
    self: MetricsOperationSurfaceOwnerProtocol,
    bytes_per_second: float,
    source: str = "real_download",
) -> None:
    update_download_speed_metrics(self, bytes_per_second, source=source)


def increment_genesis_request_method(self: MetricsOperationSurfaceOwnerProtocol) -> None:
    increment_genesis_request(self)


def purge_plugin_metrics_method(
    self: MetricsOperationSurfaceOwnerProtocol,
    plugin_name: str,
) -> None:
    purge_plugin_metrics(self, plugin_name)


async def snapshot_metrics_method(self: MetricsQuerySurfaceProtocol) -> MetricsTree:
    metrics_ref = self.metrics_ref
    await refresh_context_compaction_usage_metrics(
        self.lock,
        metrics_ref[0],
        self.database_metrics,
    )
    return await snapshot_metrics_locked(self.lock, metrics_ref[0])


async def flush_genesis_deltas_method(self: MetricsServiceMethodSurfaceProtocol) -> None:
    metrics_ref = self.metrics_ref
    await flush_genesis_deltas(
        self.lock,
        metrics_ref[0],
        self.genesis_flush_lock,
        self.genesis_requests_delta,
        self.genesis_tokens_delta,
        self.database_metrics,
    )


async def flatten_and_flush_metrics_method(self: MetricsServiceMethodSurfaceProtocol) -> None:
    await flush_metrics_to_database(
        self.snapshot_metrics,
        flatten_metrics,
        self.database_metrics.upsert_live_metrics,
        epoch_ms,
    )


async def rehydrate_from_db_method(self: MetricsServiceMethodSurfaceProtocol) -> None:
    metrics_ref = self.metrics_ref
    await rehydrate_from_database(
        lock=self.lock,
        metrics_ref=metrics_ref,
        session_start_time_ms=self.session_start_time_ms,
        database_metrics=self.database_metrics,
        create_structure_fn=create_metrics_structure,
    )


async def reset_metrics_method(self: MetricsServiceMethodSurfaceProtocol) -> None:
    logger = get_logger(LOGGER_NAME)
    self.accepting_operations = False
    await drain_background_queue(
        self.background_queue,
        self.background_worker_task,
    )
    background_worker = self.background_worker
    cancellation_binder = self.cancellation_binder
    queue, worker_task = create_background_worker_runtime(
        config=self.config,
        background_worker=background_worker(),
        cancellation_binder=cancellation_binder,
        finalizer_tracker=self.lifecycle.finalizer_tracker,
        logger=logger,
    )
    self.background_queue = queue
    self.background_worker_task = worker_task
    self.token_rate_calculator.reset()
    self.queue_full_throttle = MetricsQueueFullThrottle()
    self.capabilities_cache = None
    self.capabilities_cache_timestamp = 0.0
    metrics_ref = self.metrics_ref
    await reset_metrics_state(
        lock=self.lock,
        genesis_flush_lock=self.genesis_flush_lock,
        genesis_requests_delta=self.genesis_requests_delta,
        genesis_tokens_delta=self.genesis_tokens_delta,
        metrics_ref=metrics_ref,
        session_start_time_ms=self.session_start_time_ms,
        config=self.config,
        database_metrics=self.database_metrics,
    )
    self.accepting_operations = True


async def broadcast_metrics_method(self: MetricsServiceMethodSurfaceProtocol) -> None:
    if not self.event_bus:
        return
    if not self.event_bus.has_subscribers(MetricsUpdatedEvent):
        return
    metrics = await self.get_all_metrics()
    self.event_bus.try_publish_nowait(MetricsUpdatedEvent(metrics=metrics))
