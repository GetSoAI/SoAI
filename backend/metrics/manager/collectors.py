"""SoAI - Metrics collection operations [backend/metrics/manager/collectors.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import time
from collections import deque

from core.errors.exception_logging import log_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger
from core.metrics.keyspace_base import (
    METRIC_BLOCK_DOWNLOAD_SPEED,
    METRIC_KEY_COUNTERS,
    METRIC_METRIC_GAUGES,
)
from core.timing.epoch import epoch_ms
from core.validation.integers import is_strict_int
from metrics.manager.internal_protocols import DownloadSpeedDatabaseProtocol
from metrics.manager.path_updates import apply_metric_update
from metrics.manager.structure_constants import UNIQUE_ITEMS_MAX_CARDINALITY
from metrics.manager.type_guards import is_float_deque, is_timestamp_deque
from metrics.manager.types import MetricsTree, MetricValue

__all__ = (
    "increment_counter",
    "increment_genesis_request",
    "record_timing",
    "record_unique",
    "set_gauge",
    "update_download_speed",
)

LOGGER_NAME = "SoAI.metrics.manager.collectors"
OPERATION_METRICS_COLLECTORS_UPDATE_DOWNLOAD_SPEED = "metrics.collectors.update_download_speed"
OPERATION_METRICS_MANAGER_RECORD_UNIQUE = "metrics_manager.record_unique"


async def increment_counter(
    lock: asyncio.Lock,
    metrics: MetricsTree,
    keys: tuple[str, ...],
    value: int = 1,
) -> None:
    path = ".".join(keys)

    def _apply(parent: dict[str, MetricValue], leaf: str) -> None:
        current = parent.get(leaf, 0)
        if isinstance(current, int | float):
            parent[leaf] = current + value
        else:
            parent[leaf] = value

    await apply_metric_update(
        lock,
        metrics,
        keys,
        f"Invalid metrics path for counter: '{path}'.",
        _apply,
    )


async def set_gauge(
    lock: asyncio.Lock,
    metrics: MetricsTree,
    keys: tuple[str, ...],
    value: float,
) -> None:
    path = ".".join(keys)

    def _apply(parent: dict[str, MetricValue], leaf: str) -> None:
        parent[leaf] = value

    await apply_metric_update(
        lock,
        metrics,
        keys,
        f"Invalid metrics path for gauge: '{path}'.",
        _apply,
    )


async def record_timing(
    lock: asyncio.Lock,
    metrics: MetricsTree,
    keys: tuple[str, ...],
    duration_ms: float,
) -> None:
    path = ".".join(keys)
    warning_message = f"Timing metric not initialized correctly at '{path}'."

    def _apply(parent: dict[str, MetricValue], leaf: str) -> None:
        logger = get_logger(LOGGER_NAME)
        target = parent.get(leaf)
        if target is None or not is_float_deque(target):
            logger.warning(warning_message)
            return
        target.append(duration_ms)

    await apply_metric_update(lock, metrics, keys, warning_message, _apply)


async def record_unique(
    lock: asyncio.Lock,
    metrics: MetricsTree,
    keys: tuple[str, ...],
    item: str,
) -> None:
    logger = get_logger(LOGGER_NAME)
    path_str = ".".join(keys)
    async with lock:
        try:
            node: dict[str, MetricValue] = metrics
            for key in keys:
                node_value = node[key]
                if not isinstance(node_value, dict):
                    raise KeyError(key)
                node = node_value
        except KeyError as exception:
            log_exception(
                logger,
                exception,
                message="Invalid metrics path for unique item set",
                operation=OPERATION_METRICS_MANAGER_RECORD_UNIQUE,
                details={"path": path_str},
                level="warning",
            )
            return
        items_obj = node.get("items")
        timestamps_obj = node.get("timestamps")
        if not (isinstance(items_obj, set) and isinstance(timestamps_obj, deque)):
            logger.warning(
                "Unique metric structure at '%s' is not initialized correctly.",
                path_str,
            )
            return
        if not is_timestamp_deque(timestamps_obj):
            return
        items = items_obj
        timestamps = timestamps_obj
        counts_obj = node.get("counts")
        if isinstance(counts_obj, dict):
            counts = counts_obj
        else:
            counts = {}
            node["counts"] = counts
        now = time.monotonic()
        try:
            if not item:
                raise TypeError("Unique metric item must be a non-empty string")
            raw_count = counts.get(item, 0)
            current_count = int(raw_count) if is_strict_int(raw_count) else 0
            if current_count == 0 and len(items) >= UNIQUE_ITEMS_MAX_CARDINALITY:
                return
            counts[item] = current_count + 1
            items.add(item)
            timestamps.append((now, item))
        except TypeError as exception:
            log_exception(
                logger,
                exception,
                message="Unhashable unique metric item",
                operation=OPERATION_METRICS_MANAGER_RECORD_UNIQUE,
                details={"path": path_str},
                level="warning",
            )


async def update_download_speed(
    lock: asyncio.Lock,
    metrics: MetricsTree,
    database_hardware: DownloadSpeedDatabaseProtocol,
    bytes_per_second: float,
    source: str = "real_download",
) -> None:
    logger = get_logger(LOGGER_NAME)
    async with lock:
        download_speed_data = metrics.get(METRIC_BLOCK_DOWNLOAD_SPEED)
        if not isinstance(download_speed_data, dict):
            return
        gauges = download_speed_data.get(METRIC_METRIC_GAUGES)
        counters = download_speed_data.get(METRIC_KEY_COUNTERS)
        if not isinstance(gauges, dict) or not isinstance(counters, dict):
            return
        gauges["last_download_bps"] = bytes_per_second
        gauges["source"] = source
        gauges["last_updated_ms"] = int(epoch_ms())
        if source == "real_download":
            current_value = counters.get("total_downloads_tracked", 0)
            current_count = int(current_value) if is_strict_int(current_value) else 0
            counters["total_downloads_tracked"] = current_count + 1
    try:
        median_data = await database_hardware.get_median_real_download_speed()
        if median_data is None:
            return
        async with lock:
            download_speed_data = metrics.get(METRIC_BLOCK_DOWNLOAD_SPEED)
            if not isinstance(download_speed_data, dict):
                return
            gauges = download_speed_data.get(METRIC_METRIC_GAUGES)
            if not isinstance(gauges, dict):
                return
            bytes_per_second_obj = median_data.get("bytes_per_second")
            sample_count_obj = median_data.get("sample_count")
            gauges["current_median_bps"] = (
                float(bytes_per_second_obj)
                if isinstance(bytes_per_second_obj, int | float)
                and not isinstance(bytes_per_second_obj, bool)
                else 0.0
            )
            gauges["sample_count"] = int(sample_count_obj) if is_strict_int(sample_count_obj) else 0
    except RECOVERABLE_EXCEPTIONS as exception:
        log_exception(
            logger,
            exception,
            message="Failed to fetch median download speed for metrics",
            operation=OPERATION_METRICS_COLLECTORS_UPDATE_DOWNLOAD_SPEED,
            level="warning",
        )


async def increment_genesis_request(
    genesis_flush_lock: asyncio.Lock,
    genesis_requests_delta: list[int],
) -> None:
    async with genesis_flush_lock:
        genesis_requests_delta[0] += 1
