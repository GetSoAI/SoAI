"""SoAI - Shared metrics keyspace constants [backend/core/metrics/keyspace_base.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import Final

__all__ = ()

METRIC_BLOCK_DIRECTOR: Final[str] = "director"
METRIC_BLOCK_DATABASE: Final[str] = "database"
METRIC_BLOCK_DOWNLOAD_SPEED: Final[str] = "download_speed"
METRIC_BLOCK_GENESIS: Final[str] = "genesis"
METRIC_BLOCK_EVENT_BUS: Final[str] = "event_bus"
METRIC_BLOCK_MODEL_MANAGER: Final[str] = "model_manager"
METRIC_BLOCK_STREAMING: Final[str] = "streaming"
METRIC_BLOCK_STATE: Final[str] = "state"
METRIC_BLOCK_BILLING: Final[str] = "billing"
METRIC_BLOCK_USAGE: Final[str] = "usage"
METRIC_BLOCK_PLUGINS: Final[str] = "plugins"
METRIC_BLOCK_INACTIVITY_MONITOR: Final[str] = "inactivity_monitor"
METRIC_BLOCK_WEBSOCKET: Final[str] = "websocket"
METRIC_BLOCK_WEBSOCKET_LOG_STREAM: Final[str] = "log_stream"
METRIC_BLOCK_REPLY_QUEUE: Final[str] = "reply_queue"
METRIC_BLOCK_GLOBAL: Final[str] = "global"
METRIC_BLOCK_ORCHESTRATOR: Final[str] = "orchestrator"
METRIC_BLOCK_API: Final[str] = "api"
METRIC_BLOCK_MCP_SERVER: Final[str] = "mcp_server"
METRIC_BLOCK_MCP_REMOTE: Final[str] = "mcp_remote"
METRIC_BLOCK_MCP_SEARCH: Final[str] = "mcp_search"
METRIC_BLOCK_MCP_RAG: Final[str] = "mcp_rag"

METRIC_METRIC_TIMINGS: Final[str] = "timings"
METRIC_METRIC_GAUGES: Final[str] = "gauges"
METRIC_KEY_COUNTERS: Final[str] = "counters"

METRIC_KEY_ACTIONS_TRIGGERED: Final[str] = "actions_triggered"
METRIC_KEY_CANCELLED: Final[str] = "cancelled"
METRIC_KEY_COMPLETED: Final[str] = "completed"
METRIC_KEY_DISPATCHED_CALLBACK_COUNT: Final[str] = "dispatched_callback_count"
METRIC_KEY_DISPATCH_TIME_MS: Final[str] = "dispatch_time_ms"
METRIC_KEY_EVENTS_DROPPED: Final[str] = "events_dropped"
METRIC_KEY_FAST_PATH: Final[str] = "fast_path"
METRIC_KEY_EXPRESS_PATH: Final[str] = "express_path"
METRIC_KEY_FAILED: Final[str] = "failed"
METRIC_KEY_GAUGE_CONCURRENCY_ACTIVE: Final[str] = "plugin_concurrency_active"
METRIC_KEY_GAUGE_CONCURRENCY_LIMIT: Final[str] = "plugin_concurrency_limit"
METRIC_KEY_GAUGE_CONCURRENCY_WAITERS: Final[str] = "plugin_concurrency_waiters"
METRIC_KEY_GAUGE_HEALTH: Final[str] = "plugin_health"
METRIC_KEY_GAUGE_INACTIVE_MS: Final[str] = "inactive_ms"
METRIC_KEY_GAUGE_LAST_ACTIVITY_TIMESTAMP: Final[str] = "last_activity_timestamp"
METRIC_KEY_GAUGE_PENDING_LOADS: Final[str] = "pending_loads"
METRIC_KEY_GAUGE_QUEUE_SIZE: Final[str] = "queue_size"
METRIC_KEY_GAUGE_QUEUE_DEPTH: Final[str] = "queue_depth"
METRIC_KEY_HEALTH_CHECK_RECOVERIES: Final[str] = "health_check_recoveries"
METRIC_KEY_HEALTH_PING_FAILURES: Final[str] = "health_ping_failures"
METRIC_KEY_PLUGIN_STATUS_CHANGES: Final[str] = "plugin_status_changes"
METRIC_KEY_CURRENT_SESSION_MS: Final[str] = "current_session_ms"
METRIC_KEY_CURRENT_SESSION_START_TS_MS: Final[str] = "current_session_start_ts_ms"
METRIC_KEY_FIRST_STARTUP_TS_MS: Final[str] = "first_startup_ts_ms"
METRIC_KEY_TOKENS_BY_CLIENT: Final[str] = "tokens_by_client"
METRIC_KEY_TOKENS_BY_MODEL: Final[str] = "tokens_by_model"
METRIC_KEY_TOKENS_BY_PLUGIN: Final[str] = "tokens_by_plugin"
METRIC_KEY_TOTAL_TOKENS_GENERATED: Final[str] = "total_tokens_generated"
METRIC_KEY_USAGE_TOTALS: Final[str] = "totals"
METRIC_KEY_USAGE_BY_CLIENT: Final[str] = "by_client"
METRIC_KEY_USAGE_BY_MODEL: Final[str] = "by_model"
METRIC_KEY_USAGE_BY_PLUGIN: Final[str] = "by_plugin"
METRIC_KEY_USAGE_COMPACTION: Final[str] = "compaction"
METRIC_KEY_COMPACTION_COMPLETED_COUNT: Final[str] = "completed_count"
METRIC_KEY_COMPACTION_TOKENS_SAVED_TOTAL: Final[str] = "tokens_saved_total"
METRIC_KEY_REQUESTS_TOTAL: Final[str] = "requests_total"
METRIC_KEY_TOTAL: Final[str] = "total"
METRIC_KEY_TOKENS_TOTAL: Final[str] = "tokens_total"
METRIC_KEY_UPTIME_MS: Final[str] = "uptime_ms"
METRIC_KEY_CHUNKING: Final[str] = "chunking"
METRIC_KEY_CHUNKS_CREATED: Final[str] = "chunks_created"
METRIC_KEY_EMBEDDINGS: Final[str] = "embeddings"
METRIC_KEY_REQUESTS_LATENCY_MS: Final[str] = "request_latency_ms"
METRIC_KEY_SEARCH_LATENCY_MS: Final[str] = "search_latency_ms"
METRIC_KEY_FETCH_LATENCY_MS: Final[str] = "fetch_latency_ms"
METRIC_KEY_EMBEDDING_LATENCY_MS: Final[str] = "embedding_latency_ms"
METRIC_KEY_DOCUMENT_PROCESSING_MS: Final[str] = "document_processing_ms"
METRIC_KEY_RESOURCE_READ_MS: Final[str] = "resource_read_ms"
METRIC_KEY_TOOL_EXECUTION_MS: Final[str] = "tool_execution_ms"
METRIC_KEY_SEARCHES: Final[str] = "searches"
METRIC_KEY_FETCHES: Final[str] = "fetches"
METRIC_KEY_BY_PROVIDER: Final[str] = "by_provider"
METRIC_KEY_SUCCEEDED: Final[str] = "succeeded"
METRIC_KEY_LOG_STREAM_DROPS: Final[str] = "drops"
METRIC_KEY_DISCOVERIES_FAILED: Final[str] = "discoveries_failed"
METRIC_KEY_BACKPRESSURE: Final[str] = "backpressure"
METRIC_KEY_QUEUE_TIME_MS: Final[str] = "queue_time_ms"
METRIC_KEY_DROPPED_EVENTS: Final[str] = "dropped_events"
METRIC_KEY_DROPPED: Final[str] = "dropped"
METRIC_KEY_PERSISTENT_PLUGIN_REQUEST_TIMEOUTS: Final[str] = "persistent_plugin_request_timeouts"
METRIC_KEY_DOCUMENTS: Final[str] = "documents"
METRIC_KEY_CONNECTIONS: Final[str] = "connections"
METRIC_KEY_DISCONNECTIONS: Final[str] = "disconnections"
METRIC_KEY_SUCCESSFUL: Final[str] = "successful"
METRIC_KEY_TOOLS: Final[str] = "tools"
METRIC_KEY_CALLS: Final[str] = "calls"
METRIC_KEY_CALLS_TOTAL: Final[str] = "calls_total"
METRIC_KEY_TASKS: Final[str] = "tasks"
METRIC_KEY_CREATED: Final[str] = "created"
METRIC_KEY_RESOURCES: Final[str] = "resources"
METRIC_KEY_READS: Final[str] = "reads"
METRIC_KEY_SUBSCRIPTIONS: Final[str] = "subscriptions"
METRIC_KEY_UNSUBSCRIPTIONS: Final[str] = "unsubscriptions"
METRIC_KEY_CALLBACKS: Final[str] = "callbacks"
METRIC_KEY_REFUSED_CANCELLATION: Final[str] = "refused_cancellation"
METRIC_KEY_MMR: Final[str] = "mmr"
METRIC_KEY_HYBRID: Final[str] = "hybrid"
METRIC_KEY_SIMILARITY: Final[str] = "similarity"
METRIC_KEY_UPLOADS_COMPLETED: Final[str] = "uploads_completed"
METRIC_KEY_UPLOADS_FAILED: Final[str] = "uploads_failed"
METRIC_KEY_WEB_FETCH_INGESTS_COMPLETED: Final[str] = "web_fetch_ingests_completed"
METRIC_KEY_WEB_FETCH_INGESTS_FAILED: Final[str] = "web_fetch_ingests_failed"
METRIC_KEY_DELETIONS: Final[str] = "deletions"
METRIC_KEY_HANDLED: Final[str] = "handled"
METRIC_KEY_FAILURES: Final[str] = "failures"
METRIC_KEY_SENT: Final[str] = "sent"
METRIC_KEY_NOTIFICATIONS: Final[str] = "notifications"
METRIC_KEY_WEB_FETCH_INGESTS_QUEUED: Final[str] = "web_fetch_ingests_queued"
METRIC_KEY_UPLOADS_QUEUED: Final[str] = "uploads_queued"
METRIC_KEY_PROCESSING_QUEUE_SIZE: Final[str] = "processing_queue_size"
METRIC_KEY_QUEUE: Final[str] = "queue"
METRIC_KEY_PROMPT_QUEUING: Final[str] = "prompt_queuing"
METRIC_KEY_SLOTS_HELD: Final[str] = "slots_held"
METRIC_KEY_SLOT_LIMIT: Final[str] = "slot_limit"
METRIC_KEY_INVARIANTS: Final[str] = "invariants"
METRIC_KEY_INVARIANT_VIOLATION_COUNT: Final[str] = "invariant_violation_count"
METRIC_KEY_PROMPT_SLOT_HELD_DELTA: Final[str] = "prompt_slot_held_delta"
METRIC_KEY_PLUGIN_ACTIVE_DELTA: Final[str] = "plugin_active_delta"
METRIC_KEY_OPEN_CYCLES: Final[str] = "open_cycles"
METRIC_KEY_EXECUTION: Final[str] = "execution"
METRIC_KEY_RETRIES: Final[str] = "retries"
METRIC_KEY_RETRIES_TOTAL: Final[str] = "retries_total"
METRIC_KEY_RETRIES_BY_PLUGIN: Final[str] = "retries_by_plugin"
METRIC_KEY_RETRIES_BY_EXCEPTION: Final[str] = "retries_by_exception"
METRIC_KEY_DOUBLE_FINALIZATION_COUNT: Final[str] = "double_finalization_count"
METRIC_KEY_REQUESTS: Final[str] = "requests"
METRIC_KEY_REQUESTS_BY_MODEL: Final[str] = "requests_by_model"
METRIC_KEY_REQUESTS_BY_VIRTUAL_MODEL: Final[str] = "requests_by_virtual_model"
METRIC_KEY_MODEL_LOADS: Final[str] = "model_loads"
METRIC_KEY_DEDUPLICATED: Final[str] = "deduplicated"
METRIC_KEY_QUEUED: Final[str] = "queued"
METRIC_KEY_DELIVERY: Final[str] = "delivery"
METRIC_KEY_LISTENER: Final[str] = "listener"
METRIC_KEY_CHUNKS: Final[str] = "chunks"
METRIC_KEY_CHANNEL: Final[str] = "channel"
METRIC_KEY_COALESCED_COUNT: Final[str] = "coalesced_count"
METRIC_KEY_FAILED_COUNT: Final[str] = "failed_count"
METRIC_KEY_SHUTDOWN_COUNT: Final[str] = "shutdown_count"
METRIC_KEY_TIMEOUT_COUNT: Final[str] = "timeout_count"
METRIC_KEY_TERMINAL_FAILED_COUNT: Final[str] = "terminal_failed_count"
METRIC_KEY_STALE_REMOVED_COUNT: Final[str] = "stale_removed_count"
METRIC_KEY_EVICTION_TERMINAL_COUNT: Final[str] = "eviction_terminal_count"
DIRECTOR_GAUGE_CONCURRENCY_LIMIT: tuple[str, ...] = (
    METRIC_BLOCK_DIRECTOR,
    METRIC_METRIC_GAUGES,
    METRIC_KEY_GAUGE_CONCURRENCY_LIMIT,
)
DIRECTOR_GAUGE_CONCURRENCY_ACTIVE: tuple[str, ...] = (
    METRIC_BLOCK_DIRECTOR,
    METRIC_METRIC_GAUGES,
    METRIC_KEY_GAUGE_CONCURRENCY_ACTIVE,
)
DIRECTOR_GAUGE_CONCURRENCY_WAITERS: tuple[str, ...] = (
    METRIC_BLOCK_DIRECTOR,
    METRIC_METRIC_GAUGES,
    METRIC_KEY_GAUGE_CONCURRENCY_WAITERS,
)
DIRECTOR_GAUGE_PENDING_LOADS: tuple[str, ...] = (
    METRIC_BLOCK_DIRECTOR,
    METRIC_METRIC_GAUGES,
    METRIC_KEY_GAUGE_PENDING_LOADS,
)
DIRECTOR_GAUGE_PLUGIN_HEALTH: tuple[str, ...] = (
    METRIC_BLOCK_DIRECTOR,
    METRIC_METRIC_GAUGES,
    METRIC_KEY_GAUGE_HEALTH,
)
DIRECTOR_GAUGE_QUEUE_SIZE: tuple[str, ...] = (
    METRIC_BLOCK_DIRECTOR,
    METRIC_METRIC_GAUGES,
    METRIC_KEY_GAUGE_QUEUE_SIZE,
)
DIRECTOR_GAUGE_REQUEST_LATENCY_MS: tuple[str, ...] = (
    METRIC_BLOCK_DIRECTOR,
    METRIC_METRIC_GAUGES,
    METRIC_KEY_REQUESTS_LATENCY_MS,
)
DIRECTOR_REQUESTS: tuple[str, ...] = (METRIC_BLOCK_DIRECTOR, METRIC_KEY_REQUESTS)
DIRECTOR_REQUESTS_TOTAL: tuple[str, ...] = (
    METRIC_BLOCK_DIRECTOR,
    METRIC_KEY_REQUESTS,
    METRIC_KEY_TOTAL,
)
DIRECTOR_REQUESTS_BY_MODEL: tuple[str, ...] = (
    METRIC_BLOCK_DIRECTOR,
    METRIC_KEY_REQUESTS_BY_MODEL,
)
DIRECTOR_REQUESTS_BY_VIRTUAL_MODEL: tuple[str, ...] = (
    METRIC_BLOCK_DIRECTOR,
    METRIC_KEY_REQUESTS_BY_VIRTUAL_MODEL,
)
DIRECTOR_REQUESTS_COMPLETED: tuple[str, ...] = (
    METRIC_BLOCK_DIRECTOR,
    METRIC_KEY_REQUESTS,
    METRIC_KEY_COMPLETED,
)
DIRECTOR_REQUESTS_DEDUPLICATED: tuple[str, ...] = (
    METRIC_BLOCK_DIRECTOR,
    METRIC_KEY_REQUESTS,
    METRIC_KEY_DEDUPLICATED,
)
DIRECTOR_REQUESTS_EXPRESS_PATH: tuple[str, ...] = (
    METRIC_BLOCK_DIRECTOR,
    METRIC_KEY_REQUESTS,
    METRIC_KEY_EXPRESS_PATH,
)
DIRECTOR_REQUESTS_FAST_PATH: tuple[str, ...] = (
    METRIC_BLOCK_DIRECTOR,
    METRIC_KEY_REQUESTS,
    METRIC_KEY_FAST_PATH,
)
DIRECTOR_REQUESTS_CANCELLED: tuple[str, ...] = (
    METRIC_BLOCK_DIRECTOR,
    METRIC_KEY_REQUESTS,
    METRIC_KEY_CANCELLED,
)
DIRECTOR_REQUESTS_FAILED: tuple[str, ...] = (
    METRIC_BLOCK_DIRECTOR,
    METRIC_KEY_REQUESTS,
    METRIC_KEY_FAILED,
)
DIRECTOR_REQUESTS_HEALTH_CHECK_RECOVERIES: tuple[str, ...] = (
    METRIC_BLOCK_DIRECTOR,
    METRIC_KEY_HEALTH_CHECK_RECOVERIES,
)
DIRECTOR_REQUESTS_PERSISTENT_PLUGIN_TIMEOUTS: tuple[str, ...] = (
    METRIC_BLOCK_DIRECTOR,
    METRIC_KEY_PERSISTENT_PLUGIN_REQUEST_TIMEOUTS,
)
DIRECTOR_REQUESTS_QUEUED: tuple[str, ...] = (
    METRIC_BLOCK_DIRECTOR,
    METRIC_KEY_REQUESTS,
    METRIC_KEY_QUEUED,
)
DIRECTOR_MODEL_LOADS_SUCCESSFUL: tuple[str, ...] = (
    METRIC_BLOCK_DIRECTOR,
    METRIC_KEY_MODEL_LOADS,
    METRIC_KEY_SUCCESSFUL,
)

INACTIVITY_MONITOR_GAUGE_INACTIVE_MS: tuple[str, ...] = (
    METRIC_BLOCK_INACTIVITY_MONITOR,
    METRIC_METRIC_GAUGES,
    METRIC_KEY_GAUGE_INACTIVE_MS,
)
INACTIVITY_MONITOR_GAUGE_LAST_ACTIVITY: tuple[str, ...] = (
    METRIC_BLOCK_INACTIVITY_MONITOR,
    METRIC_METRIC_GAUGES,
    METRIC_KEY_GAUGE_LAST_ACTIVITY_TIMESTAMP,
)
INACTIVITY_MONITOR_COUNTER_ACTIONS_TRIGGERED: tuple[str, ...] = (
    METRIC_BLOCK_INACTIVITY_MONITOR,
    METRIC_KEY_ACTIONS_TRIGGERED,
)

EVENT_BUS_COUNTER_EVENTS_DROPPED: tuple[str, ...] = (
    METRIC_BLOCK_EVENT_BUS,
    METRIC_KEY_EVENTS_DROPPED,
)
