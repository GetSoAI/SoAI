"""SoAI - Conversation MCP config normalization [backend/core/agent_mcp_config.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING

from core.conversations.conversation_mcp_extensions import (
    CONVERSATION_MCP_EXTENSION_FIELDS,
    normalize_conversation_mcp_extensions,
)
from core.mcp.agent_config_normalization import (
    NormalizedAgentMCPConfig,
    normalize_agent_mcp_config,
)
from core.mcp.default_tool_names import (
    DEFAULT_CONVERSATION_MCP_EXECUTE_TOOLS,
    DEFAULT_CONVERSATION_MCP_PLAN_TOOLS,
    DEFAULT_CONVERSATION_MCP_TOOLS,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "NormalizedAgentMCPConfig",
    "normalize_conversation_mcp_config",
)


def normalize_conversation_mcp_config(
    raw: Mapping[str, JSONValue] | None,
    *,
    allow_extensions: bool = True,
) -> NormalizedAgentMCPConfig:
    if allow_extensions:
        normalize_conversation_mcp_extensions(raw)
    base_raw = _conversation_mcp_base_fields(raw) if allow_extensions else raw
    normalized = normalize_agent_mcp_config(
        base_raw,
        field_prefix="Conversation MCP",
        default_tools=DEFAULT_CONVERSATION_MCP_TOOLS,
        default_plan_tools=DEFAULT_CONVERSATION_MCP_PLAN_TOOLS,
        default_execute_tools=DEFAULT_CONVERSATION_MCP_EXECUTE_TOOLS,
        default_tools_enabled=True,
        default_tool_approval_required=True,
        tool_name_validator=None,
    )
    return NormalizedAgentMCPConfig(
        default_tools=list(normalized.default_tools),
        plan_tools=list(normalized.plan_tools),
        execute_tools=list(normalized.execute_tools),
        server_configs=dict(normalized.server_configs),
        tools_enabled=normalized.tools_enabled,
        tool_approval_required=normalized.tool_approval_required,
    )


def _conversation_mcp_base_fields(raw: Mapping[str, JSONValue] | None) -> JSONDict | None:
    if raw is None:
        return None
    return {
        field_name: value
        for field_name, value in raw.items()
        if field_name not in CONVERSATION_MCP_EXTENSION_FIELDS
    }
