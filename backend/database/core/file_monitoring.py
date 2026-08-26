"""SoAI - Database file throughput monitoring [backend/database/core/file_monitoring.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio

from core.config.protocols import ConfigProtocol
from core.database.protocols import DatabaseMetricsRecorderProtocol
from core.formatting.bytes import format_bytes_per_second
from core.logging.trace import get_logger
from core.metrics.keyspace_base import METRIC_BLOCK_DATABASE, METRIC_METRIC_GAUGES
from database.core.file_monitoring_support import (
    is_io_logging_enabled,
    snapshot_db_file_sizes,
)
from database.core.monitoring import emit_gauge

__all__ = ("monitor_db_file_throughput",)

LOGGER_NAME = "SoAI.database.core.file_monitoring"


def monitor_db_file_throughput(
    now: float,
    db_file_paths: tuple[str, str, str],
    last_db_file_sizes: dict[str, int],
    last_db_file_sample_time: float,
    last_db_io_check_time: float,
    last_db_io_log_time: float,
    last_db_io_log_payload: str | None,
    last_process_read_rate_kbps: float,
    last_process_write_rate_kbps: float,
    metrics_recorder: DatabaseMetricsRecorderProtocol | None,
    bound_loop: asyncio.AbstractEventLoop | None,
    queue_size: int,
    config: ConfigProtocol,
) -> tuple[dict[str, int], float, float, str | None]:
    if metrics_recorder is None:
        return (
            last_db_file_sizes,
            last_db_file_sample_time,
            last_db_io_log_time,
            last_db_io_log_payload,
        )
    if not last_db_file_sizes:
        current_sizes = snapshot_db_file_sizes(db_file_paths)
        return current_sizes, now, last_db_io_log_time, last_db_io_log_payload
    previous_sample_time = last_db_file_sample_time or last_db_io_check_time
    if not previous_sample_time:
        return last_db_file_sizes, now, last_db_io_log_time, last_db_io_log_payload
    delta_time = now - previous_sample_time
    if delta_time <= 0.0:
        return (
            last_db_file_sizes,
            last_db_file_sample_time,
            last_db_io_log_time,
            last_db_io_log_payload,
        )
    current_sizes = snapshot_db_file_sizes(db_file_paths)
    write_bytes = 0
    truncate_bytes = 0
    for path, current_size in current_sizes.items():
        previous_size = last_db_file_sizes.get(path)
        if previous_size is None:
            write_bytes += current_size
            continue
        delta = current_size - previous_size
        if delta > 0:
            write_bytes += delta
        elif delta < 0:
            truncate_bytes += -delta
    total_bytes = sum(current_sizes.values())
    write_rate_kbps = (write_bytes / delta_time) / 1024 if delta_time else 0.0
    truncate_rate_kbps = (truncate_bytes / delta_time) / 1024 if delta_time else 0.0
    if write_rate_kbps <= 0.0 < last_process_write_rate_kbps:
        write_rate_kbps = last_process_write_rate_kbps
    emit_gauge(
        metrics_recorder,
        bound_loop,
        METRIC_BLOCK_DATABASE,
        METRIC_METRIC_GAUGES,
        "db_file_write_kbps",
        value=write_rate_kbps,
    )
    emit_gauge(
        metrics_recorder,
        bound_loop,
        METRIC_BLOCK_DATABASE,
        METRIC_METRIC_GAUGES,
        "db_file_truncate_kbps",
        value=truncate_rate_kbps,
    )
    emit_gauge(
        metrics_recorder,
        bound_loop,
        METRIC_BLOCK_DATABASE,
        METRIC_METRIC_GAUGES,
        "db_file_size_kb",
        value=(total_bytes / 1024) if total_bytes else 0.0,
    )
    emit_gauge(
        metrics_recorder,
        bound_loop,
        METRIC_BLOCK_DATABASE,
        METRIC_METRIC_GAUGES,
        "db_write_kbps",
        value=write_rate_kbps,
    )
    emit_gauge(
        metrics_recorder,
        bound_loop,
        METRIC_BLOCK_DATABASE,
        METRIC_METRIC_GAUGES,
        "db_read_kbps",
        value=last_process_read_rate_kbps,
    )
    new_log_time = last_db_io_log_time
    new_log_payload = last_db_io_log_payload
    if now - last_db_io_log_time > 60.0:
        write_display = format_bytes_per_second(write_rate_kbps * 1024)
        truncate_display = format_bytes_per_second(truncate_rate_kbps * 1024)
        total_display = total_bytes / 1024
        payload = f"{write_display}|{truncate_display}|{total_display:.2f}|{queue_size}"
        if payload != last_db_io_log_payload:
            if config is not None and is_io_logging_enabled(config):
                logger = get_logger(LOGGER_NAME)
                logger.debug(
                    "Database File I/O: Write=%s, Truncate=%s, TotalSize=%.2f KB, Queue Depth=%d",
                    write_display,
                    truncate_display,
                    total_display,
                    queue_size,
                )
            new_log_time = now
            new_log_payload = payload
    return current_sizes, now, new_log_time, new_log_payload
