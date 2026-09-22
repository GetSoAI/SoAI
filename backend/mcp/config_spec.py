"""SoAI - MCP config specification entries [backend/mcp/config_spec.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from core.config.user_interaction_timeout import DEFAULT_USER_INTERACTION_TIMEOUT_MS
from core.mcp.schema import AUTO_EMBEDDING_MODEL_SELECTOR
from core.network.outbound_http_profiles import DEFAULT_BROWSER_DOCUMENT_USER_AGENTS
from core.timing.constants import EXTENDED_TIMEOUT_SEC

if TYPE_CHECKING:
    from core.config.protocols import ConfigValue

    type ConfigSpecType = Literal[
        "bool",
        "int",
        "float",
        "float_capped",
        "list",
        "set",
        "raw",
    ]
    type ConfigDefault = ConfigValue | None

__all__ = (
    "ConfigSpecEntry",
    "build_mcp_config_spec",
)


@dataclass(frozen=True, slots=True)
class ConfigSpecEntry:
    attr: str
    key: str
    typ: ConfigSpecType
    default: ConfigDefault
    minimum: int | float | None = None
    maximum: float | None = None


def build_mcp_config_spec() -> tuple[ConfigSpecEntry, ...]:
    return (
        ConfigSpecEntry("enabled", "TOOLS.MCP.ENABLED", "bool", False),
        ConfigSpecEntry("public_origin", "SERVER.PUBLIC_ORIGIN", "raw", ""),
        ConfigSpecEntry(
            "oauth_state_token_ttl_ms",
            "TOOLS.MCP.OAUTH.STATE_TOKEN_TTL_MS",
            "int",
            600_000,
            minimum=60_000,
        ),
        ConfigSpecEntry(
            "oauth_refresh_skew_ms",
            "TOOLS.MCP.OAUTH.REFRESH_SKEW_MS",
            "int",
            60_000,
            minimum=0,
        ),
        ConfigSpecEntry("server_mode_enabled", "TOOLS.MCP.SERVER_MODE.ENABLED", "bool", False),
        ConfigSpecEntry("host_mode_enabled", "TOOLS.MCP.HOST_MODE.ENABLED", "bool", False),
        ConfigSpecEntry(
            "reconnect_delay",
            "TOOLS.MCP.HOST_MODE.RECONNECT_DELAY_SEC",
            "float",
            5.0,
            minimum=0.0,
        ),
        ConfigSpecEntry(
            "max_reconnect_attempts",
            "TOOLS.MCP.HOST_MODE.MAX_RECONNECT_ATTEMPTS",
            "int",
            3,
            minimum=0,
        ),
        ConfigSpecEntry(
            "auto_connect_on_startup",
            "TOOLS.MCP.HOST_MODE.AUTO_CONNECT_ON_STARTUP",
            "bool",
            True,
        ),
        ConfigSpecEntry("host_roots", "TOOLS.MCP.HOST_MODE.ROOTS", "list", None),
        ConfigSpecEntry(
            "host_roots_list_changed_enabled",
            "TOOLS.MCP.HOST_MODE.ROOTS_LIST_CHANGED",
            "bool",
            True,
        ),
        ConfigSpecEntry(
            "host_sampling_enabled",
            "TOOLS.MCP.HOST_MODE.SAMPLING.ENABLED",
            "bool",
            False,
        ),
        ConfigSpecEntry(
            "host_sampling_default_model",
            "TOOLS.MCP.HOST_MODE.SAMPLING.DEFAULT_MODEL",
            "raw",
            None,
        ),
        ConfigSpecEntry(
            "host_elicitation_enabled",
            "TOOLS.MCP.HOST_MODE.ELICITATION.ENABLED",
            "bool",
            False,
        ),
        ConfigSpecEntry("exposed_tools", "TOOLS.MCP.SERVER_MODE.EXPOSED_TOOLS", "set", None),
        ConfigSpecEntry(
            "exposed_resources",
            "TOOLS.MCP.SERVER_MODE.EXPOSED_RESOURCES",
            "set",
            None,
        ),
        ConfigSpecEntry("exposed_prompts", "TOOLS.MCP.SERVER_MODE.EXPOSED_PROMPTS", "set", None),
        ConfigSpecEntry("allowed_origins", "TOOLS.MCP.SERVER_MODE.ALLOWED_ORIGINS", "list", None),
        ConfigSpecEntry(
            "list_changed_enabled",
            "TOOLS.MCP.SERVER_MODE.LIST_CHANGED_NOTIFICATIONS",
            "bool",
            False,
        ),
        ConfigSpecEntry("tasks_enabled", "TOOLS.MCP.TASKS.ENABLED", "bool", False),
        ConfigSpecEntry(
            "user_interaction_timeout_ms",
            "TOOLS.MCP.ELICITATION.WAIT_TIMEOUT_MS",
            "int",
            DEFAULT_USER_INTERACTION_TIMEOUT_MS,
            minimum=1,
        ),
        ConfigSpecEntry(
            "tasks_default_ttl_sec",
            "TOOLS.MCP.TASKS.DEFAULT_TTL_SEC",
            "int",
            3600,
            minimum=60,
        ),
        ConfigSpecEntry(
            "tasks_max_concurrent_per_client",
            "TOOLS.MCP.TASKS.MAX_CONCURRENT_PER_CLIENT",
            "int",
            100,
            minimum=1,
        ),
        ConfigSpecEntry(
            "tasks_proxy_timeout_sec",
            "TOOLS.MCP.TASKS.PROXY_TIMEOUT_SEC",
            "float",
            3600.0,
            minimum=60.0,
        ),
        ConfigSpecEntry(
            "tasks_tool_timeout_sec",
            "TOOLS.MCP.TASKS.TOOL_TIMEOUT_SEC",
            "float",
            600.0,
            minimum=5.0,
        ),
        ConfigSpecEntry("rag_enabled", "TOOLS.RAG.ENABLED", "bool", True),
        ConfigSpecEntry("rag_chroma_path", "TOOLS.RAG.CHROMA_PATH", "raw", None),
        ConfigSpecEntry(
            "rag_chroma_shard_count",
            "TOOLS.RAG.CHROMA_SHARD_COUNT",
            "int",
            1,
            minimum=1,
        ),
        ConfigSpecEntry(
            "rag_chroma_query_timeout_sec",
            "TOOLS.RAG.CHROMA_QUERY_TIMEOUT_SEC",
            "int",
            30,
            minimum=1,
        ),
        ConfigSpecEntry(
            "rag_chroma_delete_timeout_sec",
            "TOOLS.RAG.CHROMA_DELETE_TIMEOUT_SEC",
            "int",
            30,
            minimum=1,
        ),
        ConfigSpecEntry(
            "rag_chroma_ipc_startup_timeout_sec",
            "TOOLS.RAG.CHROMA_IPC_STARTUP_TIMEOUT_SEC",
            "int",
            EXTENDED_TIMEOUT_SEC,
            minimum=1,
        ),
        ConfigSpecEntry(
            "rag_chroma_ipc_retry_count",
            "TOOLS.RAG.CHROMA_IPC_RETRY_COUNT",
            "int",
            1,
            minimum=0,
        ),
        ConfigSpecEntry(
            "rag_chroma_ipc_job_ttl_sec",
            "TOOLS.RAG.CHROMA_IPC_JOB_TTL_SEC",
            "int",
            3600,
            minimum=60,
        ),
        ConfigSpecEntry(
            "rag_default_embedding_model",
            "TOOLS.RAG.DEFAULT_EMBEDDING_MODEL",
            "raw",
            AUTO_EMBEDDING_MODEL_SELECTOR,
        ),
        ConfigSpecEntry(
            "rag_processing_workers",
            "TOOLS.RAG.PROCESSING_WORKERS",
            "int",
            3,
            minimum=1,
        ),
        ConfigSpecEntry(
            "rag_default_chunk_size",
            "TOOLS.RAG.DEFAULT_CHUNK_SIZE",
            "int",
            500,
            minimum=100,
        ),
        ConfigSpecEntry(
            "rag_default_chunk_overlap",
            "TOOLS.RAG.DEFAULT_CHUNK_OVERLAP",
            "int",
            100,
            minimum=0,
        ),
        ConfigSpecEntry("rag_default_top_k", "TOOLS.RAG.DEFAULT_TOP_K", "int", 5, minimum=1),
        ConfigSpecEntry(
            "rag_default_similarity_threshold",
            "TOOLS.RAG.DEFAULT_SIMILARITY_THRESHOLD",
            "float_capped",
            0.3,
            minimum=0.0,
            maximum=1.0,
        ),
        ConfigSpecEntry("rag_web_enabled", "TOOLS.RAG.WEB.ENABLED", "bool", True),
        ConfigSpecEntry(
            "rag_web_max_url_size_mb",
            "TOOLS.RAG.WEB.MAX_URL_SIZE_MB",
            "int",
            10,
            minimum=1,
        ),
        ConfigSpecEntry(
            "rag_web_request_timeout",
            "TOOLS.RAG.WEB.REQUEST_TIMEOUT",
            "int",
            30,
            minimum=5,
        ),
        ConfigSpecEntry(
            "rag_web_user_agent",
            "TOOLS.RAG.WEB.USER_AGENT",
            "raw",
            DEFAULT_BROWSER_DOCUMENT_USER_AGENTS[0],
        ),
        ConfigSpecEntry(
            "rag_embedding_timeout",
            "TOOLS.RAG.EMBEDDING_TIMEOUT",
            "int",
            300,
            minimum=10,
        ),
        ConfigSpecEntry(
            "client_sse_replay_buffer_size",
            "TOOLS.MCP.SERVER_MODE.SSE_REPLAY_BUFFER_SIZE",
            "int",
            256,
            minimum=0,
        ),
        ConfigSpecEntry(
            "client_notification_queue_size",
            "TOOLS.MCP.CLIENT_NOTIFICATION_QUEUE_SIZE",
            "int",
            1024,
            minimum=1,
        ),
        ConfigSpecEntry("session_ttl_sec", "TOOLS.MCP.SESSION_TTL_SEC", "int", 3600, minimum=60),
        ConfigSpecEntry(
            "session_sweep_interval_sec",
            "TOOLS.MCP.SESSION_SWEEP_INTERVAL_SEC",
            "int",
            300,
            minimum=30,
        ),
    )
