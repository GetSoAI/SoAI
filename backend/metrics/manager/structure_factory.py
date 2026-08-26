"""SoAI - Metrics structure factory [backend/metrics/manager/structure_factory.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.metrics.keyspace_base import (
    METRIC_BLOCK_API,
    METRIC_BLOCK_BILLING,
    METRIC_BLOCK_DATABASE,
    METRIC_BLOCK_DIRECTOR,
    METRIC_BLOCK_DOWNLOAD_SPEED,
    METRIC_BLOCK_EVENT_BUS,
    METRIC_BLOCK_GENESIS,
    METRIC_BLOCK_GLOBAL,
    METRIC_BLOCK_INACTIVITY_MONITOR,
    METRIC_BLOCK_MCP_RAG,
    METRIC_BLOCK_MCP_REMOTE,
    METRIC_BLOCK_MCP_SEARCH,
    METRIC_BLOCK_MCP_SERVER,
    METRIC_BLOCK_MODEL_MANAGER,
    METRIC_BLOCK_ORCHESTRATOR,
    METRIC_BLOCK_PLUGINS,
    METRIC_BLOCK_STATE,
    METRIC_BLOCK_STREAMING,
    METRIC_BLOCK_USAGE,
    METRIC_BLOCK_WEBSOCKET,
)
from metrics.manager.structure_core_blocks import (
    create_api_block,
    create_billing_block,
    create_database_block,
    create_director_block,
    create_download_speed_block,
    create_event_bus_block,
    create_genesis_block,
    create_global_block,
    create_inactivity_block,
    create_model_manager_block,
    create_orchestrator_block,
    create_plugin_status_changes,
    create_plugins_metrics,
    create_state_block,
    create_streaming_block,
    create_usage_block,
    create_websocket_block,
)
from metrics.manager.structure_mcp_blocks import (
    create_mcp_rag_block,
    create_mcp_remote_block,
    create_mcp_search_block,
    create_mcp_server_block,
)

if TYPE_CHECKING:
    from metrics.manager.types import MetricsTree

__all__ = ("create_metrics_structure",)


def create_metrics_structure(session_start_time_ms: int) -> MetricsTree:
    plugin_status_changes = create_plugin_status_changes()
    metrics: MetricsTree = {
        METRIC_BLOCK_GLOBAL: create_global_block(session_start_time_ms),
        METRIC_BLOCK_EVENT_BUS: create_event_bus_block(),
        METRIC_BLOCK_DIRECTOR: create_director_block(),
        METRIC_BLOCK_ORCHESTRATOR: create_orchestrator_block(),
        METRIC_BLOCK_API: create_api_block(),
        METRIC_BLOCK_STREAMING: create_streaming_block(),
        METRIC_BLOCK_WEBSOCKET: create_websocket_block(),
        METRIC_BLOCK_MODEL_MANAGER: create_model_manager_block(),
        METRIC_BLOCK_STATE: create_state_block(plugin_status_changes),
        METRIC_BLOCK_PLUGINS: create_plugins_metrics(),
        METRIC_BLOCK_BILLING: create_billing_block(),
        METRIC_BLOCK_USAGE: create_usage_block(),
        METRIC_BLOCK_INACTIVITY_MONITOR: create_inactivity_block(),
        METRIC_BLOCK_DATABASE: create_database_block(),
        METRIC_BLOCK_DOWNLOAD_SPEED: create_download_speed_block(),
        METRIC_BLOCK_GENESIS: create_genesis_block(session_start_time_ms),
        METRIC_BLOCK_MCP_SERVER: create_mcp_server_block(),
        METRIC_BLOCK_MCP_REMOTE: create_mcp_remote_block(),
        METRIC_BLOCK_MCP_SEARCH: create_mcp_search_block(),
        METRIC_BLOCK_MCP_RAG: create_mcp_rag_block(),
    }
    return metrics
