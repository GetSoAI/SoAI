"""SoAI - Database I/O metrics monitor [backend/database/io/metrics_monitor.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field

from core.config.protocols import ConfigProtocol
from core.database.protocols import DatabaseMetricsRecorderProtocol
from core.metrics.keyspace_base import METRIC_BLOCK_DATABASE, METRIC_METRIC_GAUGES
from database.core.file_monitoring import monitor_db_file_throughput
from database.core.monitoring import (
    emit_gauge,
    monitor_process_io,
    record_write_duration,
)
from database.internal_protocols import ProcessHandleProtocol, ProcessIOCountersProtocol

__all__ = ("DatabaseIOMetricsMonitor",)


@dataclass(slots=True)
class DatabaseIOMetricsMonitor:
    db_file_paths: tuple[str, str, str]
    config: ConfigProtocol
    metrics_enabled: bool
    metrics_recorder: DatabaseMetricsRecorderProtocol | None = None
    process_handle: ProcessHandleProtocol | None = None
    last_process_io_check_time: float = 0.0
    last_process_io_counters: ProcessIOCountersProtocol | None = None
    last_process_read_rate_kbps: float = 0.0
    last_process_write_rate_kbps: float = 0.0
    last_db_file_sizes: dict[str, int] = field(default_factory=dict[str, int])
    last_db_io_check_time: float = 0.0
    last_db_file_sample_time: float = 0.0
    last_db_io_log_payload: str | None = None
    last_db_io_log_time: float = 0.0

    def set_metrics_recorder(self, recorder: DatabaseMetricsRecorderProtocol | None) -> None:
        self.metrics_recorder = recorder

    def record_write_duration(
        self,
        op_start_time_ms: int,
        *,
        bound_loop: asyncio.AbstractEventLoop | None,
    ) -> None:
        if not self.metrics_enabled:
            return
        if not self.metrics_recorder:
            return
        record_write_duration(self.metrics_recorder, bound_loop, op_start_time_ms)

    def monitor_io_throughput(
        self,
        *,
        queue_size: int,
        bound_loop: asyncio.AbstractEventLoop | None,
    ) -> None:
        if not self.metrics_enabled:
            return
        if self.metrics_recorder is None:
            return
        now = time.monotonic()
        last_check = self.last_db_io_check_time
        if last_check and (now - last_check) < 1.0:
            return
        queue_size_float = float(queue_size)
        emit_gauge(
            self.metrics_recorder,
            bound_loop,
            METRIC_BLOCK_DATABASE,
            METRIC_METRIC_GAUGES,
            "write_queue_depth",
            value=queue_size_float,
        )
        (
            self.process_handle,
            self.last_process_io_check_time,
            self.last_process_io_counters,
            self.last_process_read_rate_kbps,
            self.last_process_write_rate_kbps,
        ) = monitor_process_io(
            now,
            self.process_handle,
            self.last_process_io_check_time,
            self.last_process_io_counters,
            self.metrics_recorder,
            bound_loop,
        )
        (
            self.last_db_file_sizes,
            self.last_db_file_sample_time,
            self.last_db_io_log_time,
            self.last_db_io_log_payload,
        ) = monitor_db_file_throughput(
            now,
            self.db_file_paths,
            self.last_db_file_sizes,
            self.last_db_file_sample_time,
            self.last_db_io_check_time,
            self.last_db_io_log_time,
            self.last_db_io_log_payload,
            self.last_process_read_rate_kbps,
            self.last_process_write_rate_kbps,
            self.metrics_recorder,
            bound_loop,
            queue_size,
            self.config,
        )
        self.last_db_io_check_time = now
