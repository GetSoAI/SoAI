"""SoAI - Tail metrics structure block builders [backend/metrics/manager/structure_core_blocks_tail.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.metrics.keyspace_base import (
    METRIC_KEY_COUNTERS,
    METRIC_KEY_CURRENT_SESSION_MS,
    METRIC_KEY_CURRENT_SESSION_START_TS_MS,
    METRIC_KEY_FIRST_STARTUP_TS_MS,
    METRIC_KEY_REQUESTS_TOTAL,
    METRIC_KEY_TOKENS_TOTAL,
    METRIC_KEY_UPTIME_MS,
    METRIC_METRIC_GAUGES,
    METRIC_METRIC_TIMINGS,
)
from metrics.manager.structure_constants import create_counter_map, create_timing_map
from metrics.manager.types import MetricValue

__all__ = (
    "create_database_block",
    "create_download_speed_block",
    "create_genesis_block",
)


def create_database_block() -> dict[str, MetricValue]:
    database_gauges: dict[str, MetricValue] = {
        "db_read_kbps": 0.0,
        "db_write_kbps": 0.0,
        "write_queue_depth": 0,
        "process_read_kbps": 0.0,
        "process_write_kbps": 0.0,
        "db_file_write_kbps": 0.0,
        "db_file_truncate_kbps": 0.0,
        "db_file_size_kb": 0.0,
    }
    database_timings = create_timing_map("write_op_duration_ms")
    return {
        METRIC_METRIC_GAUGES: database_gauges,
        METRIC_METRIC_TIMINGS: database_timings,
    }


def create_download_speed_block() -> dict[str, MetricValue]:
    download_speed_gauges: dict[str, MetricValue] = {
        "current_median_bps": 0.0,
        "sample_count": 0,
        "last_download_bps": 0.0,
        "source": "none",
        "last_updated_ms": 0,
    }
    download_speed_counters = create_counter_map("total_downloads_tracked")
    return {
        METRIC_METRIC_GAUGES: download_speed_gauges,
        METRIC_KEY_COUNTERS: download_speed_counters,
    }


def create_genesis_block(session_start_time_ms: int) -> dict[str, MetricValue]:
    return {
        METRIC_KEY_UPTIME_MS: 0,
        METRIC_KEY_CURRENT_SESSION_MS: 0,
        METRIC_KEY_REQUESTS_TOTAL: 0,
        METRIC_KEY_TOKENS_TOTAL: 0,
        METRIC_KEY_FIRST_STARTUP_TS_MS: 0,
        METRIC_KEY_CURRENT_SESSION_START_TS_MS: int(session_start_time_ms),
    }
