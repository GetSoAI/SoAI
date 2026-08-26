"""SoAI - Metrics runtime block builders [backend/metrics/manager/structure_runtime_blocks.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING

from core.metrics.keyspace_base import (
    METRIC_KEY_ACTIONS_TRIGGERED,
    METRIC_KEY_BACKPRESSURE,
    METRIC_KEY_CHUNKS,
    METRIC_KEY_COALESCED_COUNT,
    METRIC_KEY_COMPACTION_COMPLETED_COUNT,
    METRIC_KEY_COMPACTION_TOKENS_SAVED_TOTAL,
    METRIC_KEY_DELIVERY,
    METRIC_KEY_DOUBLE_FINALIZATION_COUNT,
    METRIC_KEY_DROPPED_EVENTS,
    METRIC_KEY_EVICTION_TERMINAL_COUNT,
    METRIC_KEY_FAILED_COUNT,
    METRIC_KEY_GAUGE_INACTIVE_MS,
    METRIC_KEY_GAUGE_LAST_ACTIVITY_TIMESTAMP,
    METRIC_KEY_GAUGE_QUEUE_DEPTH,
    METRIC_KEY_LISTENER,
    METRIC_KEY_LOG_STREAM_DROPS,
    METRIC_KEY_PLUGIN_STATUS_CHANGES,
    METRIC_KEY_QUEUE,
    METRIC_KEY_REQUESTS_BY_MODEL,
    METRIC_KEY_REQUESTS_LATENCY_MS,
    METRIC_KEY_SHUTDOWN_COUNT,
    METRIC_KEY_STALE_REMOVED_COUNT,
    METRIC_KEY_TERMINAL_FAILED_COUNT,
    METRIC_KEY_TIMEOUT_COUNT,
    METRIC_KEY_TOKENS_BY_CLIENT,
    METRIC_KEY_TOKENS_BY_MODEL,
    METRIC_KEY_TOKENS_BY_PLUGIN,
    METRIC_KEY_TOTAL_TOKENS_GENERATED,
    METRIC_KEY_USAGE_BY_CLIENT,
    METRIC_KEY_USAGE_BY_MODEL,
    METRIC_KEY_USAGE_BY_PLUGIN,
    METRIC_KEY_USAGE_COMPACTION,
    METRIC_KEY_USAGE_TOTALS,
    METRIC_METRIC_GAUGES,
    METRIC_METRIC_TIMINGS,
)
from core.metrics.usage import create_modality_usage_counts
from metrics.manager.structure_constants import (
    create_dynamic_counter_map,
    create_timing_map,
    create_unique_tracker,
)

if TYPE_CHECKING:
    from metrics.manager.types import MetricValue

__all__ = (
    "create_api_block",
    "create_billing_block",
    "create_inactivity_block",
    "create_model_manager_block",
    "create_state_block",
    "create_streaming_block",
    "create_usage_block",
    "create_websocket_block",
)


def create_api_block() -> dict[str, MetricValue]:
    openai_timings = create_timing_map(METRIC_KEY_REQUESTS_LATENCY_MS)
    return {
        "openai": {
            "requests_total_chat_completions": 0,
            "requests_total_text_completions": 0,
            "requests_total_embedding": 0,
            "requests_total_image": 0,
            "requests_total_tts": 0,
            "requests_total_responses": 0,
            "requests_failed": 0,
            "list_models_requests": 0,
            "get_model_details_requests": 0,
            METRIC_KEY_REQUESTS_BY_MODEL: create_dynamic_counter_map(),
            "auth_failures": create_dynamic_counter_map(),
            "unique_clients": create_unique_tracker(),
            METRIC_METRIC_TIMINGS: openai_timings,
        },
        "system": {
            "status_stream_connections": 0,
            "list_models_requests": 0,
            "direct_requests_submitted": 0,
            "unique_clients": create_unique_tracker(),
        },
        "unknown": {"unique_clients": create_unique_tracker()},
        "webui": {
            "conversations_created": 0,
            "conversation_messages_updated": 0,
            "conversation_settings_updated": 0,
            "conversations_deleted": 0,
            "chat_messages_sent": 0,
        },
        "tasks": {
            "list_active": 0,
            "list": 0,
            "stream_reconnect": 0,
            "get": 0,
            "cancel": 0,
            "software_update_started": 0,
            "software_update_completed": 0,
            "software_update_failed": 0,
        },
    }


def create_streaming_block() -> dict[str, MetricValue]:
    return {
        METRIC_KEY_BACKPRESSURE: {METRIC_KEY_DROPPED_EVENTS: 0},
        "channel": {METRIC_KEY_EVICTION_TERMINAL_COUNT: 0},
        METRIC_KEY_DELIVERY: {
            METRIC_KEY_TIMEOUT_COUNT: 0,
            METRIC_KEY_SHUTDOWN_COUNT: 0,
            METRIC_KEY_FAILED_COUNT: 0,
            METRIC_KEY_TERMINAL_FAILED_COUNT: 0,
        },
        METRIC_KEY_LISTENER: {METRIC_KEY_STALE_REMOVED_COUNT: 0},
        METRIC_KEY_CHUNKS: {METRIC_KEY_COALESCED_COUNT: 0},
        METRIC_KEY_QUEUE: {METRIC_KEY_DOUBLE_FINALIZATION_COUNT: 0},
    }


def create_websocket_block() -> dict[str, MetricValue]:
    return {
        "log_stream": {METRIC_KEY_LOG_STREAM_DROPS: create_dynamic_counter_map()},
        METRIC_METRIC_GAUGES: {METRIC_KEY_GAUGE_QUEUE_DEPTH: create_dynamic_counter_map()},
    }


def create_model_manager_block() -> dict[str, MetricValue]:
    model_manager_timings = create_timing_map("discovery_duration_ms")
    return {
        "discoveries_run": 0,
        "models_updated": 0,
        "models_removed": 0,
        "param_updates_processed": 0,
        "param_deletes_processed": 0,
        "discoveries_failed": create_dynamic_counter_map(),
        METRIC_METRIC_TIMINGS: model_manager_timings,
    }


def create_state_block(plugin_status_changes: dict[str, MetricValue]) -> dict[str, MetricValue]:
    return {
        "events_emitted": create_dynamic_counter_map(),
        METRIC_KEY_PLUGIN_STATUS_CHANGES: plugin_status_changes,
        "inactivity_actions_triggered": create_dynamic_counter_map(),
        METRIC_METRIC_TIMINGS: create_timing_map(
            "write_lock_duration_ms",
            "read_lock_duration_ms",
        ),
    }


def create_billing_block() -> dict[str, MetricValue]:
    return {
        METRIC_KEY_TOTAL_TOKENS_GENERATED: 0,
        METRIC_KEY_TOKENS_BY_PLUGIN: create_dynamic_counter_map(),
        METRIC_KEY_TOKENS_BY_MODEL: create_dynamic_counter_map(),
        METRIC_KEY_TOKENS_BY_CLIENT: create_dynamic_counter_map(),
    }


def create_usage_block() -> dict[str, MetricValue]:
    return {
        METRIC_KEY_USAGE_TOTALS: _create_usage_counts(),
        METRIC_KEY_USAGE_BY_PLUGIN: create_dynamic_usage_map(),
        METRIC_KEY_USAGE_BY_MODEL: create_dynamic_usage_map(),
        METRIC_KEY_USAGE_BY_CLIENT: create_dynamic_usage_map(),
        METRIC_KEY_USAGE_COMPACTION: {
            METRIC_KEY_COMPACTION_COMPLETED_COUNT: 0,
            METRIC_KEY_COMPACTION_TOKENS_SAVED_TOTAL: 0,
        },
    }


def create_dynamic_usage_map() -> dict[str, MetricValue]:
    return defaultdict(_create_usage_counts)


def _create_usage_counts() -> dict[str, MetricValue]:
    return dict(create_modality_usage_counts())


def create_inactivity_block() -> dict[str, MetricValue]:
    return {
        METRIC_METRIC_GAUGES: {
            METRIC_KEY_GAUGE_LAST_ACTIVITY_TIMESTAMP: 0,
            METRIC_KEY_GAUGE_INACTIVE_MS: 0,
        },
        METRIC_KEY_ACTIONS_TRIGGERED: create_dynamic_counter_map(),
    }
