"""SoAI - Shared MCP tool context preparation helpers [backend/core/mcp/tool_context_preparation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from core.automation.automation_tool_blocklist import (
    load_automation_disallowed_unqualified_tools,
)
from core.automation.automation_tool_validation import (
    build_automation_tool_name_validator,
)
from core.config.protocols import ConfigProtocol
from core.config.user_interaction_timeout import resolve_user_interaction_timeout_ms
from core.mcp.tool_catalog_scope import MCPToolCatalogScope
from core.mcp.tool_context_builder import build_mcp_tool_context

if TYPE_CHECKING:
    from core.mcp.agent_config_normalization import NormalizedAgentMCPConfig
    from core.mcp.protocols import MCPToolCatalogSourcesProtocol
    from core.orchestrator.types import MCPToolContext
    from core.types.json import JSONDict

__all__ = ("prepare_mcp_tool_context",)


async def prepare_mcp_tool_context(
    *,
    request_json: JSONDict,
    agent_mode: str,
    normalized_mcp: NormalizedAgentMCPConfig,
    conv_id: str,
    user_id: int,
    message_index: int,
    assistant_at_ms: int,
    assistant_turn_at_ms: int,
    model_variant_index: int,
    model_id: str,
    is_automation: bool,
    config: ConfigProtocol,
    force_tool_approval_required: bool | None,
    supports_tool_calling: Callable[[str], Awaitable[bool]],
    sources: MCPToolCatalogSourcesProtocol,
    local_tool_catalog_scope: MCPToolCatalogScope,
    forced_tool_names: tuple[str, ...] = (),
    force_tool_choice_auto: bool = False,
) -> MCPToolContext:
    if is_automation:
        disallowed_unqualified_tools = load_automation_disallowed_unqualified_tools(config)
        tool_name_validator = build_automation_tool_name_validator(disallowed_unqualified_tools)
    else:
        tool_name_validator = None
    return await build_mcp_tool_context(
        request_json=request_json,
        agent_mode=agent_mode,
        normalized_mcp=normalized_mcp,
        conv_id=conv_id,
        user_id=user_id,
        message_index=message_index,
        assistant_at_ms=assistant_at_ms,
        assistant_turn_at_ms=assistant_turn_at_ms,
        model_variant_index=model_variant_index,
        model_id=model_id,
        tool_name_validator=tool_name_validator,
        force_tool_approval_required=force_tool_approval_required,
        forced_tool_names=forced_tool_names,
        force_tool_choice_auto=force_tool_choice_auto,
        supports_tool_calling=supports_tool_calling,
        sources=sources,
        local_tool_catalog_scope=local_tool_catalog_scope,
        user_interaction_timeout_ms=resolve_user_interaction_timeout_ms(config),
    )
