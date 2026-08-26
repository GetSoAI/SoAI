"""SoAI - Metrics structure MCP block builders [backend/metrics/manager/structure_mcp_blocks.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.metrics.keyspace_base import (
    METRIC_KEY_BACKPRESSURE,
    METRIC_KEY_BY_PROVIDER,
    METRIC_KEY_CALLS,
    METRIC_KEY_CALLS_TOTAL,
    METRIC_KEY_CANCELLED,
    METRIC_KEY_CHUNKING,
    METRIC_KEY_CHUNKS_CREATED,
    METRIC_KEY_COMPLETED,
    METRIC_KEY_CONNECTIONS,
    METRIC_KEY_CREATED,
    METRIC_KEY_DEDUPLICATED,
    METRIC_KEY_DELETIONS,
    METRIC_KEY_DISCONNECTIONS,
    METRIC_KEY_DOCUMENT_PROCESSING_MS,
    METRIC_KEY_DOCUMENTS,
    METRIC_KEY_DROPPED,
    METRIC_KEY_EMBEDDING_LATENCY_MS,
    METRIC_KEY_EMBEDDINGS,
    METRIC_KEY_FAILED,
    METRIC_KEY_FAILURES,
    METRIC_KEY_FETCH_LATENCY_MS,
    METRIC_KEY_FETCHES,
    METRIC_KEY_HANDLED,
    METRIC_KEY_HYBRID,
    METRIC_KEY_MMR,
    METRIC_KEY_NOTIFICATIONS,
    METRIC_KEY_PROCESSING_QUEUE_SIZE,
    METRIC_KEY_READS,
    METRIC_KEY_REQUESTS,
    METRIC_KEY_REQUESTS_LATENCY_MS,
    METRIC_KEY_RESOURCE_READ_MS,
    METRIC_KEY_RESOURCES,
    METRIC_KEY_RETRIES,
    METRIC_KEY_SEARCH_LATENCY_MS,
    METRIC_KEY_SEARCHES,
    METRIC_KEY_SENT,
    METRIC_KEY_SIMILARITY,
    METRIC_KEY_SUBSCRIPTIONS,
    METRIC_KEY_SUCCEEDED,
    METRIC_KEY_SUCCESSFUL,
    METRIC_KEY_TASKS,
    METRIC_KEY_TOOL_EXECUTION_MS,
    METRIC_KEY_TOOLS,
    METRIC_KEY_TOTAL,
    METRIC_KEY_UNSUBSCRIPTIONS,
    METRIC_KEY_UPLOADS_COMPLETED,
    METRIC_KEY_UPLOADS_FAILED,
    METRIC_KEY_UPLOADS_QUEUED,
    METRIC_KEY_WEB_FETCH_INGESTS_COMPLETED,
    METRIC_KEY_WEB_FETCH_INGESTS_FAILED,
    METRIC_KEY_WEB_FETCH_INGESTS_QUEUED,
    METRIC_METRIC_GAUGES,
    METRIC_METRIC_TIMINGS,
)
from metrics.manager.structure_constants import (
    create_dynamic_counter_map,
    create_timing_map,
)

if TYPE_CHECKING:
    from metrics.manager.types import MetricValue

__all__ = (
    "create_mcp_rag_block",
    "create_mcp_remote_block",
    "create_mcp_search_block",
    "create_mcp_server_block",
)


def create_mcp_server_block() -> dict[str, MetricValue]:
    mcp_server_notifications: dict[str, MetricValue] = {
        METRIC_KEY_DROPPED: 0,
        METRIC_KEY_FAILURES: 0,
        METRIC_KEY_SENT: 0,
    }
    mcp_server_requests: dict[str, MetricValue] = {
        METRIC_KEY_TOTAL: 0,
        METRIC_KEY_HANDLED: 0,
        METRIC_KEY_FAILED: 0,
    }
    mcp_server_tools_calls: dict[str, MetricValue] = {
        METRIC_KEY_SUCCEEDED: 0,
        METRIC_KEY_FAILED: 0,
    }
    mcp_server_tools: dict[str, MetricValue] = {
        METRIC_KEY_CALLS_TOTAL: 0,
        METRIC_KEY_CALLS: mcp_server_tools_calls,
    }
    mcp_server_resource_reads: dict[str, MetricValue] = {
        METRIC_KEY_TOTAL: 0,
        METRIC_KEY_FAILED: 0,
        METRIC_KEY_SUCCEEDED: 0,
    }
    mcp_server_resources: dict[str, MetricValue] = {
        METRIC_KEY_READS: mcp_server_resource_reads,
        METRIC_KEY_SUBSCRIPTIONS: 0,
        METRIC_KEY_UNSUBSCRIPTIONS: 0,
    }
    mcp_server_tasks: dict[str, MetricValue] = {
        METRIC_KEY_CREATED: 0,
        METRIC_KEY_COMPLETED: 0,
        METRIC_KEY_FAILED: 0,
        METRIC_KEY_CANCELLED: 0,
    }
    mcp_server_timings = create_timing_map(
        METRIC_KEY_REQUESTS_LATENCY_MS,
        METRIC_KEY_TOOL_EXECUTION_MS,
        METRIC_KEY_RESOURCE_READ_MS,
    )
    return {
        METRIC_KEY_NOTIFICATIONS: mcp_server_notifications,
        METRIC_KEY_REQUESTS: mcp_server_requests,
        METRIC_KEY_TOOLS: mcp_server_tools,
        METRIC_KEY_RESOURCES: mcp_server_resources,
        METRIC_KEY_TASKS: mcp_server_tasks,
        METRIC_METRIC_TIMINGS: mcp_server_timings,
    }


def create_mcp_remote_block() -> dict[str, MetricValue]:
    mcp_remote_connections: dict[str, MetricValue] = {
        METRIC_KEY_TOTAL: 0,
        METRIC_KEY_SUCCESSFUL: 0,
        METRIC_KEY_FAILED: 0,
        METRIC_KEY_DISCONNECTIONS: 0,
    }
    return {METRIC_KEY_CONNECTIONS: mcp_remote_connections}


def create_mcp_search_block() -> dict[str, MetricValue]:
    mcp_search_searches: dict[str, MetricValue] = {
        METRIC_KEY_TOTAL: 0,
        METRIC_KEY_BY_PROVIDER: create_dynamic_counter_map(),
        METRIC_KEY_SUCCEEDED: 0,
        METRIC_KEY_FAILED: 0,
    }
    mcp_search_fetches: dict[str, MetricValue] = {
        METRIC_KEY_TOTAL: 0,
        METRIC_KEY_SUCCEEDED: 0,
        METRIC_KEY_FAILED: 0,
    }
    mcp_search_retries: dict[str, MetricValue] = {
        METRIC_KEY_TOTAL: 0,
        METRIC_KEY_BY_PROVIDER: create_dynamic_counter_map(),
    }
    mcp_search_timings = create_timing_map(
        METRIC_KEY_SEARCH_LATENCY_MS,
        METRIC_KEY_FETCH_LATENCY_MS,
    )
    return {
        METRIC_KEY_SEARCHES: mcp_search_searches,
        METRIC_KEY_FETCHES: mcp_search_fetches,
        METRIC_KEY_RETRIES: mcp_search_retries,
        METRIC_METRIC_TIMINGS: mcp_search_timings,
    }


def create_mcp_rag_block() -> dict[str, MetricValue]:
    mcp_rag_backpressure: dict[str, MetricValue] = {
        METRIC_KEY_DROPPED: 0,
    }
    mcp_rag_documents: dict[str, MetricValue] = {
        METRIC_KEY_UPLOADS_QUEUED: 0,
        METRIC_KEY_UPLOADS_COMPLETED: 0,
        METRIC_KEY_UPLOADS_FAILED: 0,
        METRIC_KEY_DELETIONS: 0,
        METRIC_KEY_WEB_FETCH_INGESTS_QUEUED: 0,
        METRIC_KEY_WEB_FETCH_INGESTS_COMPLETED: 0,
        METRIC_KEY_WEB_FETCH_INGESTS_FAILED: 0,
    }
    mcp_rag_parsing: dict[str, MetricValue] = {
        METRIC_KEY_TOTAL: 0,
        METRIC_KEY_SUCCEEDED: 0,
        METRIC_KEY_FAILED: 0,
        "by_type": create_dynamic_counter_map(),
    }
    mcp_rag_chunking: dict[str, MetricValue] = {METRIC_KEY_CHUNKS_CREATED: 0}
    mcp_rag_embeddings: dict[str, MetricValue] = {
        METRIC_KEY_REQUESTS: 0,
        "batches": 0,
        METRIC_KEY_DEDUPLICATED: 0,
        METRIC_KEY_FAILED: 0,
    }
    mcp_rag_searches: dict[str, MetricValue] = {
        METRIC_KEY_TOTAL: 0,
        METRIC_KEY_SIMILARITY: 0,
        METRIC_KEY_MMR: 0,
        METRIC_KEY_HYBRID: 0,
        METRIC_KEY_FAILED: 0,
    }
    mcp_rag_gauges: dict[str, MetricValue] = {
        METRIC_KEY_PROCESSING_QUEUE_SIZE: 0,
        "active_workers": 0,
    }
    mcp_rag_timings = create_timing_map(
        METRIC_KEY_DOCUMENT_PROCESSING_MS,
        METRIC_KEY_SEARCH_LATENCY_MS,
        METRIC_KEY_EMBEDDING_LATENCY_MS,
    )
    return {
        METRIC_KEY_BACKPRESSURE: mcp_rag_backpressure,
        METRIC_KEY_DOCUMENTS: mcp_rag_documents,
        "parsing": mcp_rag_parsing,
        METRIC_KEY_CHUNKING: mcp_rag_chunking,
        METRIC_KEY_EMBEDDINGS: mcp_rag_embeddings,
        METRIC_KEY_SEARCHES: mcp_rag_searches,
        METRIC_METRIC_GAUGES: mcp_rag_gauges,
        METRIC_METRIC_TIMINGS: mcp_rag_timings,
    }
