"""SoAI - MCP configuration value application [backend/mcp/config.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from core.config.numeric import coerce_positive_float, coerce_positive_int
from core.config.numeric_lenient import coerce_lenient_positive_int
from core.config.protocols import ConfigProtocol
from core.errors.exceptions import ValidationError
from core.validation.boolean_coercion import coerce_bool
from core.validation.integers import is_strict_int
from mcp.config_spec import ConfigSpecEntry
from mcp.internal_protocols import MCPConfigApplicatorProtocol

if TYPE_CHECKING:
    from core.config.value_types import ConfigValue

__all__ = ("apply_config_spec",)


def apply_config_spec(
    target: MCPConfigApplicatorProtocol,
    config: ConfigProtocol,
    spec: tuple[ConfigSpecEntry, ...],
) -> None:
    for entry in spec:
        value = config.get(entry.key, entry.default)
        if entry.typ == "bool":
            if not isinstance(entry.default, bool):
                raise ValidationError(f"{entry.key} default must be a boolean.")
            if (
                not isinstance(value, str | int | float | bool | bytes | bytearray)
                and value is not None
            ):
                raise ValidationError(f"{entry.key} must be a boolean.")
            resolved_bool = bool(coerce_bool(value, default=entry.default))
            match entry.attr:
                case "enabled":
                    target.enabled = resolved_bool
                case "server_mode_enabled":
                    target.server_mode_enabled = resolved_bool
                case "host_mode_enabled":
                    target.host_mode_enabled = resolved_bool
                case "auto_connect_on_startup":
                    target.auto_connect_on_startup = resolved_bool
                case "host_roots_list_changed_enabled":
                    target.host_roots_list_changed_enabled = resolved_bool
                case "host_sampling_enabled":
                    target.host_sampling_enabled = resolved_bool
                case "host_elicitation_enabled":
                    target.host_elicitation_enabled = resolved_bool
                case "list_changed_enabled":
                    target.list_changed_enabled = resolved_bool
                case "tasks_enabled":
                    target.tasks_enabled = resolved_bool
                case "rag_enabled":
                    target.rag_enabled = resolved_bool
                case "rag_web_enabled":
                    target.rag_web_enabled = resolved_bool
                case _:
                    raise ValidationError(f"Unsupported MCP bool config attr: {entry.attr}")
            continue

        if entry.typ == "int":
            if not is_strict_int(entry.default):
                raise ValidationError(f"{entry.key} default must be an integer.")
            minimum = entry.minimum if entry.minimum is not None else 0
            if not is_strict_int(minimum):
                raise ValidationError(f"{entry.key} minimum must be an integer.")
            if entry.attr == "user_interaction_timeout_ms":
                resolved_int = coerce_lenient_positive_int(
                    value,
                    default=entry.default,
                    minimum=int(minimum),
                )
            else:
                resolved_int = int(
                    coerce_positive_int(value, default=entry.default, minimum=int(minimum)),
                )
            match entry.attr:
                case "oauth_state_token_ttl_ms":
                    target.oauth_state_token_ttl_ms = resolved_int
                case "oauth_refresh_skew_ms":
                    target.oauth_refresh_skew_ms = resolved_int
                case "max_reconnect_attempts":
                    target.max_reconnect_attempts = resolved_int
                case "tasks_default_ttl_sec":
                    target.tasks_default_ttl_sec = resolved_int
                case "user_interaction_timeout_ms":
                    target.user_interaction_timeout_ms = resolved_int
                case "tasks_max_concurrent_per_client":
                    target.tasks_max_concurrent_per_client = resolved_int
                case "rag_chroma_shard_count":
                    target.rag_chroma_shard_count = resolved_int
                case "rag_chroma_query_timeout_sec":
                    target.rag_chroma_query_timeout_sec = resolved_int
                case "rag_chroma_delete_timeout_sec":
                    target.rag_chroma_delete_timeout_sec = resolved_int
                case "rag_chroma_ipc_startup_timeout_sec":
                    target.rag_chroma_ipc_startup_timeout_sec = resolved_int
                case "rag_chroma_ipc_retry_count":
                    target.rag_chroma_ipc_retry_count = resolved_int
                case "rag_chroma_ipc_job_ttl_sec":
                    target.rag_chroma_ipc_job_ttl_sec = resolved_int
                case "rag_processing_workers":
                    target.rag_processing_workers = resolved_int
                case "rag_default_chunk_size":
                    target.rag_default_chunk_size = resolved_int
                case "rag_default_chunk_overlap":
                    target.rag_default_chunk_overlap = resolved_int
                case "rag_default_top_k":
                    target.rag_default_top_k = resolved_int
                case "rag_web_max_url_size_mb":
                    target.rag_web_max_url_size_mb = resolved_int
                case "rag_web_request_timeout":
                    target.rag_web_request_timeout = resolved_int
                case "rag_embedding_timeout":
                    target.rag_embedding_timeout = resolved_int
                case "client_sse_replay_buffer_size":
                    target.client_sse_replay_buffer_size = resolved_int
                case "client_notification_queue_size":
                    target.client_notification_queue_size = resolved_int
                case "session_ttl_sec":
                    target.session_ttl_sec = resolved_int
                case "session_sweep_interval_sec":
                    target.session_sweep_interval_sec = resolved_int
                case _:
                    raise ValidationError(f"Unsupported MCP int config attr: {entry.attr}")
            continue

        if entry.typ == "float":
            if not isinstance(entry.default, float):
                raise ValidationError(f"{entry.key} default must be a float.")
            minimum = entry.minimum if entry.minimum is not None else 0.0
            if not isinstance(minimum, float):
                raise ValidationError(f"{entry.key} minimum must be a float.")
            minimum_float = _coerce_mcp_float_config(entry.key, float(minimum))
            resolved_float = _coerce_mcp_float_config(
                entry.key,
                coerce_positive_float(value, default=entry.default, minimum=minimum_float),
            )
            match entry.attr:
                case "reconnect_delay":
                    target.reconnect_delay = resolved_float
                case "tasks_proxy_timeout_sec":
                    target.tasks_proxy_timeout_sec = resolved_float
                case "tasks_tool_timeout_sec":
                    target.tasks_tool_timeout_sec = resolved_float
                case _:
                    raise ValidationError(f"Unsupported MCP float config attr: {entry.attr}")
            continue

        if entry.typ == "float_capped":
            if not isinstance(entry.default, float):
                raise ValidationError(f"{entry.key} default must be a float.")
            minimum = entry.minimum if entry.minimum is not None else 0.0
            maximum = entry.maximum if entry.maximum is not None else 1.0
            if not isinstance(minimum, float) or not isinstance(maximum, float):
                raise ValidationError(f"{entry.key} minimum and maximum must be floats.")
            minimum_float = _coerce_mcp_float_config(entry.key, float(minimum))
            maximum_float = _coerce_mcp_float_config(
                entry.key,
                float(maximum),
            )
            configured_float = _coerce_mcp_float_config(
                entry.key,
                coerce_positive_float(value, default=entry.default, minimum=minimum_float),
            )
            resolved_float = min(
                maximum_float,
                configured_float,
            )
            if entry.attr != "rag_default_similarity_threshold":
                raise ValidationError(f"Unsupported MCP capped-float config attr: {entry.attr}")
            target.rag_default_similarity_threshold = resolved_float
            continue

        if entry.typ == "list":
            if value is None:
                resolved_list = []
            elif isinstance(value, list | tuple):
                if not all(isinstance(item, str) for item in value):
                    raise ValidationError(f"{entry.key} must be a list of strings.")
                resolved_list = [str(item) for item in value]
            else:
                raise ValidationError(f"{entry.key} must be a list")
            match entry.attr:
                case "host_roots":
                    target.host_roots = resolved_list
                case "allowed_origins":
                    target.allowed_origins = resolved_list
                case _:
                    raise ValidationError(f"Unsupported MCP list config attr: {entry.attr}")
            continue

        if entry.typ == "set":
            if value is None:
                resolved_str_set = None
            elif isinstance(value, set | list | tuple):
                if not all(isinstance(item, str) for item in value):
                    raise ValidationError(f"{entry.key} must contain only strings.")
                resolved_str_set = {str(item) for item in value}
            else:
                raise ValidationError(f"{entry.key} must be a set or list")
            match entry.attr:
                case "exposed_tools":
                    target.exposed_tools = resolved_str_set
                case "exposed_resources":
                    target.exposed_resources = resolved_str_set
                case "exposed_prompts":
                    target.exposed_prompts = resolved_str_set
                case _:
                    raise ValidationError(f"Unsupported MCP set config attr: {entry.attr}")
            continue

        match entry.attr:
            case "public_origin":
                if value is None:
                    target.public_origin = ""
                elif isinstance(value, str):
                    target.public_origin = value
                else:
                    raise ValidationError("SERVER.PUBLIC_ORIGIN must be a string.")
            case "host_sampling_default_model":
                target.host_sampling_default_model = _coerce_optional_mcp_string(
                    entry.key,
                    value,
                )
            case "rag_chroma_path":
                if value is None:
                    target.rag_chroma_path = None
                elif isinstance(value, str):
                    target.rag_chroma_path = value
                else:
                    raise ValidationError("TOOLS.RAG.CHROMA_PATH must be a string.")
            case "rag_default_embedding_model":
                target.rag_default_embedding_model = _coerce_optional_mcp_string(
                    entry.key,
                    value,
                )
            case "rag_web_user_agent":
                if value is None:
                    target.rag_web_user_agent = ""
                elif isinstance(value, str):
                    target.rag_web_user_agent = value
                else:
                    raise ValidationError("TOOLS.RAG.WEB.USER_AGENT must be a string.")
            case _:
                raise ValidationError(f"Unsupported MCP config spec attribute: {entry.attr}")


def _coerce_mcp_float_config(key: str, value: float) -> float:
    resolved_value = float(value)
    if not math.isfinite(resolved_value):
        raise ValidationError(f"{key} must be a finite number.")
    return resolved_value


def _coerce_optional_mcp_string(key: str, value: ConfigValue | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    raise ValidationError(f"{key} must be a string.")
