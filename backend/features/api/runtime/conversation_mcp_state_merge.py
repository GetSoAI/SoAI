"""SoAI - Conversation MCP state merge helpers [backend/features/api/runtime/conversation_mcp_state_merge.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.agent_mcp_config import normalize_conversation_mcp_config
from core.automation.automation_mcp_config import normalize_automation_mcp_settings
from core.collections.ordered_uniqueness import unique_sequence
from core.conversations.conversation_mcp_extensions import (
    normalize_conversation_mcp_extensions,
)
from core.errors.exceptions import ValidationError
from core.mcp.agent_config_normalization import (
    AGENT_MCP_TOOL_SELECTION_FIELDS,
    build_normalized_agent_mcp_config_payload,
)
from core.mcp.tool_entries import SOAI_MCP_SERVER_ID
from core.rag.knowledge_prompt_contract import KNOWLEDGE_ACCESS_TOOL_NAMES
from features.api.runtime.conversation_mcp_knowledge import (
    strip_knowledge_managed_mcp_overlay,
)
from features.api.runtime.errors import raise_invalid_request
from features.api.runtime.mcp_server_configs_validation import (
    normalize_server_configs,
)
from features.api.runtime.mcp_tool_selection_validation import (
    normalize_selected_mcp_tools,
    resolve_mcp_tool_server_config_id,
)

if TYPE_CHECKING:
    from core.mcp.agent_config_normalization import NormalizedAgentMCPConfig
    from core.runtime.protocols import RequestProtocol
    from core.types.json import JSONDict
    from features.api.runtime.internal_protocols import ConversationMCPStateProtocol
    from features.api.schemas.mcp_config import ConversationMCPConfigUpdate

__all__ = (
    "merge_conversation_mcp_config_update",
    "normalize_owner_mcp_config",
)


def merge_conversation_mcp_config_update(
    *,
    request: RequestProtocol,
    state: ConversationMCPStateProtocol,
    payload: ConversationMCPConfigUpdate,
    tool_map: dict[str, JSONDict],
    server_ids: set[str],
    disallowed_unqualified_tools: tuple[str, ...],
    extension_source: JSONDict | None = None,
) -> JSONDict:
    updates = payload.model_dump(exclude_unset=True)
    normalized_existing = state.effective_normalized_mcp
    merged_config_payload: JSONDict = {
        "default_tools": list(normalized_existing.default_tools),
        "plan_tools": list(normalized_existing.plan_tools),
        "execute_tools": list(normalized_existing.execute_tools),
        "server_configs": dict(normalized_existing.server_configs),
        "tools_enabled": normalized_existing.tools_enabled,
        "tool_approval_required": normalized_existing.tool_approval_required,
    }
    if "server_configs" in updates:
        server_configs_update = updates.get("server_configs")
        if server_configs_update is None:
            merged_config_payload["server_configs"] = {}
        else:
            merged_config_payload["server_configs"] = normalize_server_configs(
                request=request,
                server_configs=server_configs_update,
                server_ids=server_ids,
            )
    if "tools_enabled" in updates:
        merged_config_payload["tools_enabled"] = updates.get("tools_enabled")
    _apply_requested_tool_updates(
        request=request,
        merged_config=merged_config_payload,
        tool_map=tool_map,
        updates=updates,
    )
    if "tool_approval_required" in updates:
        merged_config_payload["tool_approval_required"] = updates.get("tool_approval_required")
    _reject_required_knowledge_disable_updates(
        request=request,
        state=state,
        updates=updates,
        merged_config=merged_config_payload,
    )
    normalized_config = normalize_owner_mcp_config(
        request,
        merged_config_payload,
        is_automation=state.is_automation,
        disallowed_unqualified_tools=disallowed_unqualified_tools,
    )
    final_config = build_normalized_agent_mcp_config_payload(normalized_config)
    _drop_disabled_server_tools(merged_config=final_config, tool_map=tool_map)
    final_config = strip_knowledge_managed_mcp_overlay(
        merged_payload=final_config,
        stored_normalized_mcp=state.stored_normalized_mcp,
        knowledge_state=state.knowledge_state,
        updates=updates,
    )
    _preserve_conversation_mcp_extensions(
        request=request,
        state=state,
        final_config=final_config,
        extension_source=extension_source,
    )
    return final_config


def normalize_owner_mcp_config(
    request: RequestProtocol,
    mcp_payload: JSONDict,
    *,
    is_automation: bool,
    disallowed_unqualified_tools: tuple[str, ...],
) -> NormalizedAgentMCPConfig:
    if is_automation:
        return normalize_automation_mcp_settings(
            mcp_payload,
            disallowed_unqualified_tools=disallowed_unqualified_tools,
        )
    try:
        return normalize_conversation_mcp_config(mcp_payload)
    except ValidationError as exception:
        raise_invalid_request(request, exception.message)


def _drop_disabled_server_tools(
    *,
    merged_config: JSONDict,
    tool_map: dict[str, JSONDict],
) -> None:
    server_configs_value = merged_config.get("server_configs")
    if not isinstance(server_configs_value, dict):
        return
    disabled_server_ids = {
        server_id for server_id, enabled in server_configs_value.items() if enabled is False
    }
    if not disabled_server_ids:
        return
    for field_name in AGENT_MCP_TOOL_SELECTION_FIELDS:
        selected_tools_value = merged_config.get(field_name)
        if not isinstance(selected_tools_value, list):
            continue
        filtered_tools: list[str] = []
        for tool_name in selected_tools_value:
            normalized_name = str(tool_name or "").strip()
            if not normalized_name:
                continue
            entry = tool_map.get(normalized_name)
            server_id = resolve_mcp_tool_server_config_id(entry)
            if server_id in disabled_server_ids:
                continue
            filtered_tools.append(normalized_name)
        merged_config[field_name] = list(unique_sequence(filtered_tools))


def _preserve_conversation_mcp_extensions(
    *,
    request: RequestProtocol,
    state: ConversationMCPStateProtocol,
    final_config: JSONDict,
    extension_source: JSONDict | None,
) -> None:
    if state.is_automation:
        return
    source = extension_source
    if source is None:
        source_value = state.settings.get("mcp")
        source = source_value if isinstance(source_value, dict) else None
    try:
        final_config.update(normalize_conversation_mcp_extensions(source))
    except ValidationError as exception:
        raise_invalid_request(request, exception.message)


def _apply_requested_tool_updates(
    *,
    request: RequestProtocol,
    merged_config: JSONDict,
    tool_map: dict[str, JSONDict],
    updates: JSONDict,
) -> None:
    for field_name in AGENT_MCP_TOOL_SELECTION_FIELDS:
        if field_name not in updates:
            continue
        raw_tools = updates.get(field_name)
        if raw_tools is None:
            merged_config[field_name] = None
            continue
        merged_config[field_name] = normalize_selected_mcp_tools(
            request=request,
            raw_tools=raw_tools,
            field_name=field_name,
            tool_map=tool_map,
            server_configs=merged_config.get("server_configs"),
            reject_empty=merged_config.get("tools_enabled") is True,
        )


def _reject_required_knowledge_disable_updates(
    *,
    request: RequestProtocol,
    state: ConversationMCPStateProtocol,
    updates: JSONDict,
    merged_config: JSONDict,
) -> None:
    if not state.knowledge_state.auto_managed:
        return
    if updates.get("tools_enabled") is False:
        raise_invalid_request(request, "Knowledge tools cannot be disabled while documents exist.")
    server_configs = merged_config.get("server_configs")
    if isinstance(server_configs, dict) and server_configs.get(SOAI_MCP_SERVER_ID) is False:
        raise_invalid_request(request, "The local SoAI MCP server is required for Knowledge.")
    for field_name in AGENT_MCP_TOOL_SELECTION_FIELDS:
        if field_name not in updates:
            continue
        raw_tools = merged_config.get(field_name)
        selected_tools = raw_tools if isinstance(raw_tools, list) else []
        missing_tools = [name for name in KNOWLEDGE_ACCESS_TOOL_NAMES if name not in selected_tools]
        if missing_tools:
            raise_invalid_request(
                request,
                f"Knowledge requires MCP tools: {', '.join(missing_tools)}",
            )
