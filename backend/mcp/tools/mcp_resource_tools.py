"""SoAI - MCP utility tools: MCP resource listing/read [backend/mcp/tools/mcp_resource_tools.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from mcp.protocol.types import MCPJSONRPCError
from mcp.tools.argument_fields import reject_unexpected_parameters
from mcp.tools.error import MCPToolError, get_arg
from mcp.tools.files_access import normalize_str
from mcp.tools.internal_protocols import MCPUtilityToolsProtocol
from mcp.tools.offline_policy import (
    is_offline_mode_enabled,
    require_url_allowed_when_offline,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "tool_mcp_resource_read",
    "tool_mcp_resource_templates_list",
    "tool_mcp_resources_list",
)

_ALLOWED_LIST_KEYS: frozenset[str] = frozenset({"server", "cursor"})
_ALLOWED_READ_KEYS: frozenset[str] = frozenset({"server", "uri"})


def _cursor_rule(server: str | None, cursor: str | None) -> None:
    if server is None and cursor is not None:
        raise MCPToolError(
            -32602,
            "cursor is only valid when server is provided. Provide both server and cursor, or omit cursor.",
        )


async def _require_offline_allows_server(
    utility_tools: MCPUtilityToolsProtocol,
    *,
    tool_name: str,
    capability: str,
    server_id: str,
) -> None:
    if not is_offline_mode_enabled(utility_tools.runtime_flags):
        return
    connected = await utility_tools.mcp_remote.list_connected_servers()
    for entry in connected:
        entry_id = entry.get("id")
        if not isinstance(entry_id, str) or entry_id.strip() != server_id:
            continue
        status = entry.get("status")
        if status != "connected":
            return
        transport_type = entry.get("transport_type")
        if transport_type != "streamable_http":
            return
        endpoint = entry.get("endpoint")
        if not isinstance(endpoint, str) or not endpoint.strip():
            return
        await require_url_allowed_when_offline(
            utility_tools.runtime_flags,
            tool_name=tool_name,
            url=endpoint.strip(),
            capability=capability,
        )
        return


async def tool_mcp_resources_list(
    utility_tools: MCPUtilityToolsProtocol,
    arguments: JSONDict,
) -> JSONDict:
    reject_unexpected_parameters(arguments, _ALLOWED_LIST_KEYS)
    server = normalize_str(arguments.get("server"), field="server", required=False)
    cursor = normalize_str(arguments.get("cursor"), field="cursor", required=False)
    _cursor_rule(server, cursor)

    if server is None:
        resources = await utility_tools.mcp_remote.list_all_resources()
        return {"resources": resources}

    await _require_offline_allows_server(
        utility_tools,
        tool_name="mcp_resources_list",
        capability="mcp remote resources",
        server_id=server,
    )
    try:
        result = await utility_tools.mcp_remote.send_host_mode_request(
            server,
            "resources/list",
            {"cursor": cursor} if cursor else {},
        )
    except MCPJSONRPCError as exception:
        raise MCPToolError(
            int(exception.code),
            exception.message,
            data=exception.data,
        ) from exception
    if isinstance(result, dict):
        return result
    return {"resources": []}


async def tool_mcp_resource_templates_list(
    utility_tools: MCPUtilityToolsProtocol,
    arguments: JSONDict,
) -> JSONDict:
    reject_unexpected_parameters(arguments, _ALLOWED_LIST_KEYS)
    server = normalize_str(arguments.get("server"), field="server", required=False)
    cursor = normalize_str(arguments.get("cursor"), field="cursor", required=False)
    _cursor_rule(server, cursor)

    if server is not None:
        await _require_offline_allows_server(
            utility_tools,
            tool_name="mcp_resource_templates_list",
            capability="mcp remote templates",
            server_id=server,
        )
        try:
            result = await utility_tools.mcp_remote.send_host_mode_request(
                server,
                "resources/templates/list",
                {"cursor": cursor} if cursor else {},
            )
        except MCPJSONRPCError as exception:
            raise MCPToolError(
                int(exception.code),
                exception.message,
                data=exception.data,
            ) from exception
        if isinstance(result, dict):
            return result
        return {"resourceTemplates": []}

    connected = await utility_tools.mcp_remote.list_connected_servers()
    if is_offline_mode_enabled(utility_tools.runtime_flags):
        for entry in connected:
            status = entry.get("status")
            if status != "connected":
                continue
            transport_type = entry.get("transport_type")
            if transport_type != "streamable_http":
                continue
            endpoint = entry.get("endpoint")
            if not isinstance(endpoint, str) or not endpoint.strip():
                continue
            await require_url_allowed_when_offline(
                utility_tools.runtime_flags,
                tool_name="mcp_resource_templates_list",
                url=endpoint.strip(),
                capability="mcp remote templates",
            )
    templates: list[JSONDict] = []
    for server_info in connected:
        server_id_value = server_info.get("id")
        status_value = server_info.get("status")
        server_id = server_id_value.strip() if isinstance(server_id_value, str) else ""
        if not server_id or status_value != "connected":
            continue
        try:
            response = await utility_tools.mcp_remote.send_host_mode_request(
                server_id,
                "resources/templates/list",
                {},
            )
        except MCPJSONRPCError:
            continue
        if not isinstance(response, dict):
            continue
        page = response.get("resourceTemplates")
        if not isinstance(page, list):
            continue
        server_name = server_info.get("name") if isinstance(server_info.get("name"), str) else None
        for template_value in page:
            if not isinstance(template_value, dict):
                continue
            combined: JSONDict = dict(template_value)
            combined["server_id"] = server_id
            if server_name:
                combined["server_name"] = server_name
            templates.append(combined)

    return {"resourceTemplates": templates}


async def tool_mcp_resource_read(
    utility_tools: MCPUtilityToolsProtocol,
    arguments: JSONDict,
) -> JSONDict:
    reject_unexpected_parameters(arguments, _ALLOWED_READ_KEYS)
    server = get_arg(arguments, "server")
    uri = get_arg(arguments, "uri")
    if not isinstance(server, str) or not server.strip():
        raise MCPToolError(-32602, "server must be a non-empty string")
    if not isinstance(uri, str) or not uri.strip():
        raise MCPToolError(-32602, "uri must be a non-empty string")
    await _require_offline_allows_server(
        utility_tools,
        tool_name="mcp_resource_read",
        capability="mcp remote read",
        server_id=server.strip(),
    )
    try:
        return await utility_tools.mcp_remote.read_resource(server.strip(), uri.strip())
    except MCPJSONRPCError as exception:
        raise MCPToolError(
            int(exception.code),
            exception.message,
            data=exception.data,
        ) from exception
