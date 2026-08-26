"""SoAI - MCP internal protocols [backend/mcp/internal_protocols.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import Protocol

__all__ = ("MCPConfigApplicatorProtocol",)


class MCPConfigApplicatorProtocol(Protocol):
    enabled: bool
    public_origin: str
    oauth_state_token_ttl_ms: int
    oauth_refresh_skew_ms: int
    server_mode_enabled: bool
    host_mode_enabled: bool
    reconnect_delay: float
    max_reconnect_attempts: int
    auto_connect_on_startup: bool
    host_roots: list[str]
    host_roots_list_changed_enabled: bool
    host_sampling_enabled: bool
    host_sampling_default_model: str | None
    host_elicitation_enabled: bool
    exposed_tools: set[str] | None
    exposed_resources: set[str] | None
    exposed_prompts: set[str] | None
    allowed_origins: list[str]
    list_changed_enabled: bool
    tasks_enabled: bool
    user_interaction_timeout_ms: int
    tasks_default_ttl_sec: int
    tasks_max_concurrent_per_client: int
    tasks_proxy_timeout_sec: float
    tasks_tool_timeout_sec: float
    rag_enabled: bool
    rag_chroma_path: str | None
    rag_chroma_shard_count: int
    rag_chroma_query_timeout_sec: int
    rag_chroma_delete_timeout_sec: int
    rag_chroma_ipc_startup_timeout_sec: int
    rag_chroma_ipc_retry_count: int
    rag_chroma_ipc_job_ttl_sec: int
    rag_default_embedding_model: str | None
    rag_processing_workers: int
    rag_default_chunk_size: int
    rag_default_chunk_overlap: int
    rag_default_top_k: int
    rag_default_similarity_threshold: float
    rag_web_enabled: bool
    rag_web_max_url_size_mb: int
    rag_web_request_timeout: int
    rag_web_user_agent: str
    rag_embedding_timeout: int
    client_sse_replay_buffer_size: int
    client_notification_queue_size: int
    session_ttl_sec: int
    session_sweep_interval_sec: int
