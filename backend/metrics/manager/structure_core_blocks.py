"""SoAI - Metrics structure core block builders [backend/metrics/manager/structure_core_blocks.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING

from core.metrics.keyspace_base import (
    METRIC_KEY_CALLBACKS,
    METRIC_KEY_CANCELLED,
    METRIC_KEY_COMPLETED,
    METRIC_KEY_DEDUPLICATED,
    METRIC_KEY_DISPATCH_TIME_MS,
    METRIC_KEY_DISPATCHED_CALLBACK_COUNT,
    METRIC_KEY_DOUBLE_FINALIZATION_COUNT,
    METRIC_KEY_EVENTS_DROPPED,
    METRIC_KEY_EXECUTION,
    METRIC_KEY_EXPRESS_PATH,
    METRIC_KEY_FAILED,
    METRIC_KEY_FAST_PATH,
    METRIC_KEY_GAUGE_CONCURRENCY_ACTIVE,
    METRIC_KEY_GAUGE_CONCURRENCY_LIMIT,
    METRIC_KEY_GAUGE_CONCURRENCY_WAITERS,
    METRIC_KEY_GAUGE_HEALTH,
    METRIC_KEY_GAUGE_PENDING_LOADS,
    METRIC_KEY_GAUGE_QUEUE_DEPTH,
    METRIC_KEY_GAUGE_QUEUE_SIZE,
    METRIC_KEY_HEALTH_CHECK_RECOVERIES,
    METRIC_KEY_HEALTH_PING_FAILURES,
    METRIC_KEY_INVARIANT_VIOLATION_COUNT,
    METRIC_KEY_INVARIANTS,
    METRIC_KEY_MODEL_LOADS,
    METRIC_KEY_OPEN_CYCLES,
    METRIC_KEY_PERSISTENT_PLUGIN_REQUEST_TIMEOUTS,
    METRIC_KEY_PLUGIN_ACTIVE_DELTA,
    METRIC_KEY_PROMPT_QUEUING,
    METRIC_KEY_PROMPT_SLOT_HELD_DELTA,
    METRIC_KEY_QUEUE,
    METRIC_KEY_QUEUE_TIME_MS,
    METRIC_KEY_QUEUED,
    METRIC_KEY_REFUSED_CANCELLATION,
    METRIC_KEY_REQUESTS,
    METRIC_KEY_REQUESTS_BY_MODEL,
    METRIC_KEY_REQUESTS_LATENCY_MS,
    METRIC_KEY_REQUESTS_TOTAL,
    METRIC_KEY_RETRIES_BY_EXCEPTION,
    METRIC_KEY_RETRIES_BY_PLUGIN,
    METRIC_KEY_RETRIES_TOTAL,
    METRIC_KEY_SLOT_LIMIT,
    METRIC_KEY_SLOTS_HELD,
    METRIC_KEY_SUCCESSFUL,
    METRIC_KEY_TOTAL,
    METRIC_METRIC_GAUGES,
    METRIC_METRIC_TIMINGS,
)
from metrics.manager.structure_constants import (
    create_counter_map,
    create_dynamic_counter_map,
    create_timing_deque,
    create_timing_map,
)
from metrics.manager.structure_core_blocks_tail import (
    create_database_block,
    create_download_speed_block,
    create_genesis_block,
)
from metrics.manager.structure_runtime_blocks import (
    create_api_block,
    create_billing_block,
    create_inactivity_block,
    create_model_manager_block,
    create_state_block,
    create_streaming_block,
    create_usage_block,
    create_websocket_block,
)

if TYPE_CHECKING:
    from metrics.manager.types import MetricValue

__all__ = (
    "create_api_block",
    "create_billing_block",
    "create_database_block",
    "create_director_block",
    "create_download_speed_block",
    "create_event_bus_block",
    "create_genesis_block",
    "create_global_block",
    "create_inactivity_block",
    "create_model_manager_block",
    "create_orchestrator_block",
    "create_plugin_status_changes",
    "create_plugins_metrics",
    "create_state_block",
    "create_streaming_block",
    "create_usage_block",
    "create_websocket_block",
)


def create_plugin_status_changes() -> dict[str, MetricValue]:
    def _new_status_counts() -> dict[str, MetricValue]:
        return create_dynamic_counter_map()

    status_changes: dict[str, MetricValue] = defaultdict(_new_status_counts)
    return status_changes


def create_plugins_metrics() -> dict[str, MetricValue]:
    def _new_plugin_metrics() -> dict[str, MetricValue]:
        plugin_timings = create_timing_map(METRIC_KEY_REQUESTS_LATENCY_MS)
        return {
            METRIC_KEY_REQUESTS_TOTAL: 0,
            "requests_failed": 0,
            "requests_succeeded": 0,
            METRIC_METRIC_TIMINGS: plugin_timings,
        }

    plugin_metrics: dict[str, MetricValue] = defaultdict(_new_plugin_metrics)
    return plugin_metrics


def create_global_block(session_start_time_ms: int) -> dict[str, MetricValue]:
    global_timings = create_timing_map("startup_duration_ms", maxlen=1)
    return {
        "start_time_ms": int(session_start_time_ms),
        "restarts_triggered": 0,
        "updates_triggered": 0,
        METRIC_METRIC_TIMINGS: global_timings,
    }


def create_event_bus_block() -> dict[str, MetricValue]:
    event_bus_gauges = create_counter_map(
        METRIC_KEY_GAUGE_QUEUE_DEPTH,
        METRIC_KEY_DISPATCHED_CALLBACK_COUNT,
    )
    event_bus_timings = create_timing_map(
        METRIC_KEY_QUEUE_TIME_MS,
        METRIC_KEY_DISPATCH_TIME_MS,
    )
    event_bus_callbacks = create_counter_map(METRIC_KEY_REFUSED_CANCELLATION)
    return {
        METRIC_KEY_EVENTS_DROPPED: 0,
        METRIC_KEY_CALLBACKS: event_bus_callbacks,
        METRIC_METRIC_GAUGES: event_bus_gauges,
        METRIC_METRIC_TIMINGS: event_bus_timings,
    }


def create_director_block() -> dict[str, MetricValue]:
    director_requests = create_counter_map(
        METRIC_KEY_TOTAL,
        METRIC_KEY_QUEUED,
        METRIC_KEY_COMPLETED,
        METRIC_KEY_FAILED,
        METRIC_KEY_CANCELLED,
        METRIC_KEY_FAST_PATH,
        METRIC_KEY_EXPRESS_PATH,
        METRIC_KEY_DEDUPLICATED,
    )
    director_gauges: dict[str, MetricValue] = {
        METRIC_KEY_GAUGE_QUEUE_SIZE: 0,
        METRIC_KEY_REQUESTS_LATENCY_MS: 0,
        METRIC_KEY_GAUGE_PENDING_LOADS: 0,
        METRIC_KEY_GAUGE_HEALTH: create_dynamic_counter_map(),
        METRIC_KEY_GAUGE_CONCURRENCY_LIMIT: create_dynamic_counter_map(),
        METRIC_KEY_GAUGE_CONCURRENCY_ACTIVE: create_dynamic_counter_map(),
        METRIC_KEY_GAUGE_CONCURRENCY_WAITERS: create_dynamic_counter_map(),
    }
    director_model_loads = create_counter_map(METRIC_KEY_SUCCESSFUL, METRIC_KEY_FAILED)
    director_timings: dict[str, MetricValue] = {
        target: create_timing_deque()
        for target in (
            "model_load_latency_ms",
            "request_wait_time_ms",
            "state_lock_wait_ms",
            "dedup_lock_wait_ms",
            "routing_config_lock_wait_ms",
            "active_inferences_lock_wait_ms",
        )
    }
    return {
        METRIC_KEY_REQUESTS: director_requests,
        "evictions_triggered": 0,
        METRIC_KEY_HEALTH_CHECK_RECOVERIES: create_dynamic_counter_map(),
        METRIC_KEY_HEALTH_PING_FAILURES: create_dynamic_counter_map(),
        METRIC_KEY_REQUESTS_BY_MODEL: create_dynamic_counter_map(),
        "requests_by_virtual_model": create_dynamic_counter_map(),
        "failovers_applied": create_dynamic_counter_map(),
        METRIC_KEY_PERSISTENT_PLUGIN_REQUEST_TIMEOUTS: create_dynamic_counter_map(),
        METRIC_METRIC_GAUGES: director_gauges,
        METRIC_KEY_MODEL_LOADS: director_model_loads,
        METRIC_METRIC_TIMINGS: director_timings,
    }


def create_orchestrator_block() -> dict[str, MetricValue]:
    orchestrator_prompt_queuing_gauges = create_counter_map(
        METRIC_KEY_SLOTS_HELD,
        METRIC_KEY_SLOT_LIMIT,
    )
    orchestrator_queue_counters = create_counter_map(METRIC_KEY_DOUBLE_FINALIZATION_COUNT)
    orchestrator_invariants_counters = create_counter_map(METRIC_KEY_INVARIANT_VIOLATION_COUNT)
    orchestrator_invariants_gauges: dict[str, MetricValue] = {
        METRIC_KEY_PROMPT_SLOT_HELD_DELTA: 0,
        METRIC_KEY_PLUGIN_ACTIVE_DELTA: create_dynamic_counter_map(),
    }
    orchestrator_queue_gauges: dict[str, MetricValue] = {
        METRIC_KEY_OPEN_CYCLES: create_dynamic_counter_map(),
    }
    orchestrator_gauges: dict[str, MetricValue] = {
        METRIC_KEY_INVARIANTS: orchestrator_invariants_gauges,
        METRIC_KEY_QUEUE: orchestrator_queue_gauges,
    }
    orchestrator_execution_counters: dict[str, MetricValue] = {
        METRIC_KEY_RETRIES_TOTAL: 0,
        METRIC_KEY_RETRIES_BY_PLUGIN: create_dynamic_counter_map(),
        METRIC_KEY_RETRIES_BY_EXCEPTION: create_dynamic_counter_map(),
    }
    return {
        METRIC_KEY_PROMPT_QUEUING: orchestrator_prompt_queuing_gauges,
        METRIC_KEY_QUEUE: orchestrator_queue_counters,
        METRIC_KEY_INVARIANTS: orchestrator_invariants_counters,
        METRIC_KEY_EXECUTION: orchestrator_execution_counters,
        METRIC_METRIC_GAUGES: orchestrator_gauges,
    }
