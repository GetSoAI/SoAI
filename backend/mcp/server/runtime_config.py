"""SoAI - MCP server runtime configuration holder [backend/mcp/server/runtime_config.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass, field

from core.config.protocols import ConfigProtocol
from core.config.user_interaction_timeout import DEFAULT_USER_INTERACTION_TIMEOUT_MS
from core.timing.constants import EXTENDED_TIMEOUT_SEC
from mcp.config import apply_config_spec
from mcp.config_spec import build_mcp_config_spec

__all__ = (
    "MCPRuntimeConfig",
    "build_runtime_config",
)


@dataclass(slots=True)
class MCPRuntimeConfig:
    enabled: bool = False
    public_origin: str = ""
    oauth_state_token_ttl_ms: int = 600_000
    oauth_refresh_skew_ms: int = 60_000
    server_mode_enabled: bool = False
    host_mode_enabled: bool = False
    reconnect_delay: float = 5.0
    max_reconnect_attempts: int = 3
    auto_connect_on_startup: bool = True
    host_roots: list[str] = field(default_factory=list[str])
    host_roots_list_changed_enabled: bool = True
    host_sampling_enabled: bool = False
    host_sampling_default_model: str | None = None
    host_elicitation_enabled: bool = False
    exposed_tools: set[str] | None = None
    exposed_resources: set[str] | None = None
    exposed_prompts: set[str] | None = None
    allowed_origins: list[str] = field(default_factory=list[str])
    list_changed_enabled: bool = False
    tasks_enabled: bool = False
    user_interaction_timeout_ms: int = DEFAULT_USER_INTERACTION_TIMEOUT_MS
    tasks_default_ttl_sec: int = 3600
    tasks_max_concurrent_per_client: int = 100
    tasks_proxy_timeout_sec: float = 3600.0
    tasks_tool_timeout_sec: float = 600.0
    rag_enabled: bool = True
    rag_chroma_path: str | None = None
    rag_chroma_shard_count: int = 1
    rag_chroma_query_timeout_sec: int = 30
    rag_chroma_delete_timeout_sec: int = 30
    rag_chroma_ipc_startup_timeout_sec: int = EXTENDED_TIMEOUT_SEC
    rag_chroma_ipc_retry_count: int = 1
    rag_chroma_ipc_job_ttl_sec: int = 3600
    rag_default_embedding_model: str | None = None
    rag_processing_workers: int = 3
    rag_default_chunk_size: int = 500
    rag_default_chunk_overlap: int = 100
    rag_default_top_k: int = 5
    rag_default_similarity_threshold: float = 0.3
    rag_web_enabled: bool = True
    rag_web_max_url_size_mb: int = 10
    rag_web_request_timeout: int = 30
    rag_web_user_agent: str = "SoAI-RAG/1.0"
    rag_embedding_timeout: int = 300
    client_sse_replay_buffer_size: int = 256
    client_notification_queue_size: int = 1024
    session_ttl_sec: int = 3600
    session_sweep_interval_sec: int = 300


def build_runtime_config(config: ConfigProtocol) -> MCPRuntimeConfig:
    runtime = MCPRuntimeConfig()
    apply_config_spec(runtime, config, build_mcp_config_spec())
    return runtime
