"""SoAI - Database I/O throughput monitoring [backend/database/core/monitoring.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Callable

import psutil

from core.database.protocols import DatabaseMetricsRecorderProtocol
from core.errors.exception_logging import log_exception, log_handled_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger
from core.metrics.keyspace_base import (
    METRIC_BLOCK_DATABASE,
    METRIC_METRIC_GAUGES,
    METRIC_METRIC_TIMINGS,
)
from core.timing.monotonic import monotonic_ms
from database.internal_protocols import ProcessHandleProtocol, ProcessIOCountersProtocol

__all__ = (
    "emit_gauge",
    "monitor_process_io",
    "record_write_duration",
    "schedule_metrics_action",
)

LOGGER_NAME = "SoAI.database.core.monitoring"
OPERATION_DATABASE_MONITORING_METRICS_ACTION = "database.monitoring.metrics_action"
OPERATION_DATABASE_MONITORING_PROCESS_HANDLE = "database.monitoring.process_handle"
OPERATION_DATABASE_MONITORING_PROCESS_IO_COUNTERS = "database.monitoring.process_io_counters"


def schedule_metrics_action[R](
    metrics_recorder: DatabaseMetricsRecorderProtocol | None,
    bound_loop: asyncio.AbstractEventLoop | None,
    action: Callable[..., R],
    *args: str | float,
    **named_values: float,
) -> None:
    logger = get_logger(LOGGER_NAME)
    if metrics_recorder is None:
        return
    if bound_loop is None or bound_loop.is_closed():
        return

    def _invoke() -> None:
        logger = get_logger(LOGGER_NAME)
        try:
            action(*args, **named_values)
        except RECOVERABLE_EXCEPTIONS as exception:
            log_exception(
                logger,
                exception,
                message="Metrics action failed.",
                operation=OPERATION_DATABASE_MONITORING_METRICS_ACTION,
                level="warning",
            )

    try:
        bound_loop.call_soon_threadsafe(_invoke)
    except RuntimeError:
        logger.debug("Event loop unavailable for metrics action, skipping.")


def emit_gauge(
    metrics_recorder: DatabaseMetricsRecorderProtocol | None,
    bound_loop: asyncio.AbstractEventLoop | None,
    *keys: str,
    value: float,
) -> None:
    if not metrics_recorder:
        return
    schedule_metrics_action(
        metrics_recorder,
        bound_loop,
        metrics_recorder.set_gauge,
        *keys,
        value=value,
    )


def record_write_duration(
    metrics_recorder: DatabaseMetricsRecorderProtocol | None,
    bound_loop: asyncio.AbstractEventLoop | None,
    op_start_time_ms: int,
) -> None:
    if not metrics_recorder:
        return
    duration_ms = max(0, monotonic_ms() - int(op_start_time_ms))
    schedule_metrics_action(
        metrics_recorder,
        bound_loop,
        metrics_recorder.record_timing,
        METRIC_BLOCK_DATABASE,
        METRIC_METRIC_TIMINGS,
        "write_op_duration_ms",
        duration_ms=float(duration_ms),
    )


def monitor_process_io(
    now: float,
    process_handle: ProcessHandleProtocol | None,
    last_process_io_check_time: float,
    last_process_io_counters: ProcessIOCountersProtocol | None,
    metrics_recorder: DatabaseMetricsRecorderProtocol | None,
    bound_loop: asyncio.AbstractEventLoop | None,
) -> tuple[
    ProcessHandleProtocol | None,
    float,
    ProcessIOCountersProtocol | None,
    float,
    float,
]:
    logger = get_logger(LOGGER_NAME)
    if not process_handle:
        try:
            process_handle = psutil.Process()
        except RECOVERABLE_EXCEPTIONS as exception:
            log_handled_exception(
                logger,
                exception,
                message="Failed to obtain process handle for IO monitoring (non-critical).",
                operation=OPERATION_DATABASE_MONITORING_PROCESS_HANDLE,
                level="debug",
            )
            return None, last_process_io_check_time, last_process_io_counters, 0.0, 0.0
    if process_handle is None:
        return (
            process_handle,
            last_process_io_check_time,
            last_process_io_counters,
            0.0,
            0.0,
        )
    try:
        counters = process_handle.io_counters()
    except RECOVERABLE_EXCEPTIONS as exception:
        log_handled_exception(
            logger,
            exception,
            message="Unable to retrieve process IO counters (non-critical).",
            operation=OPERATION_DATABASE_MONITORING_PROCESS_IO_COUNTERS,
            level="debug",
        )
        return (
            process_handle,
            last_process_io_check_time,
            last_process_io_counters,
            0.0,
            0.0,
        )
    read_rate_kbps = 0.0
    write_rate_kbps = 0.0
    if last_process_io_counters:
        elapsed = max(now - last_process_io_check_time, 1e-6)
        read_delta = counters.read_bytes - last_process_io_counters.read_bytes
        write_delta = counters.write_bytes - last_process_io_counters.write_bytes
        read_rate = read_delta / elapsed
        write_rate = write_delta / elapsed
        read_rate_kbps = read_rate / 1024
        write_rate_kbps = write_rate / 1024
        emit_gauge(
            metrics_recorder,
            bound_loop,
            METRIC_BLOCK_DATABASE,
            METRIC_METRIC_GAUGES,
            "process_read_kbps",
            value=read_rate_kbps,
        )
        emit_gauge(
            metrics_recorder,
            bound_loop,
            METRIC_BLOCK_DATABASE,
            METRIC_METRIC_GAUGES,
            "process_write_kbps",
            value=write_rate_kbps,
        )
    return process_handle, now, counters, read_rate_kbps, write_rate_kbps
