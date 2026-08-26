"""SoAI - Canonical MCP catalog selection validation [backend/features/api/runtime/mcp_tool_selection_validation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.collections.ordered_uniqueness import unique_sequence
from core.mcp.tool_entries import SOAI_MCP_SERVER_ID
from features.api.runtime.errors import raise_invalid_request

if TYPE_CHECKING:
    from core.runtime.protocols import RequestProtocol
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "normalize_selected_mcp_tools",
    "resolve_mcp_tool_server_config_id",
)


def normalize_selected_mcp_tools(
    *,
    request: RequestProtocol,
    raw_tools: JSONValue,
    field_name: str,
    tool_map: dict[str, JSONDict],
    server_configs: JSONValue,
    reject_empty: bool,
) -> list[str]:
    if not isinstance(raw_tools, list):
        raise_invalid_request(request, f"{field_name} must be a list.")
    normalized_tools: list[str] = []
    for name in raw_tools:
        if not isinstance(name, str):
            raise_invalid_request(request, f"{field_name} entries must be strings.")
        normalized_name = name.strip()
        if not normalized_name:
            raise_invalid_request(request, f"{field_name} entries cannot be empty.")
        normalized_tools.append(normalized_name)
    deduped_tools = list(unique_sequence(normalized_tools))
    if reject_empty and not deduped_tools:
        raise_invalid_request(
            request,
            f"{field_name} cannot be empty. Select at least one tool.",
        )
    missing_tools = [name for name in deduped_tools if name not in tool_map]
    if missing_tools:
        raise_invalid_request(request, f"Unknown MCP tools: {', '.join(missing_tools)}")
    disabled_tools = _collect_disabled_tools(
        selected_tools=deduped_tools,
        tool_map=tool_map,
        server_configs=server_configs,
    )
    if disabled_tools:
        raise_invalid_request(
            request,
            f"Tools belong to disabled servers: {', '.join(disabled_tools)}",
        )
    return deduped_tools


def resolve_mcp_tool_server_config_id(entry: JSONDict | None) -> str:
    if not isinstance(entry, dict):
        return SOAI_MCP_SERVER_ID
    server_id = entry.get("server_id")
    if isinstance(server_id, str) and server_id.strip():
        return server_id.strip()
    return SOAI_MCP_SERVER_ID


def _collect_disabled_tools(
    *,
    selected_tools: list[str],
    tool_map: dict[str, JSONDict],
    server_configs: JSONValue,
) -> list[str]:
    if not isinstance(server_configs, dict):
        return []
    disabled_tools: list[str] = []
    for tool_name in selected_tools:
        tool_entry = tool_map.get(tool_name)
        server_id = resolve_mcp_tool_server_config_id(tool_entry)
        if server_configs.get(server_id) is False:
            disabled_tools.append(tool_name)
    return disabled_tools
