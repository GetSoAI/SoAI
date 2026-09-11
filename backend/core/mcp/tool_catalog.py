"""SoAI - MCP tool catalog collection helpers [backend/core/mcp/tool_catalog.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING

from core.mcp.protocols import (
    MCPRemoteToolCatalogProtocol,
    MCPServerToolCatalogProtocol,
)
from core.mcp.qualified_name import encode_qualified_tool_name
from core.mcp.tool_catalog_cache import (
    MCPToolCatalogCache,
    MCPToolCatalogCacheEntry,
    MCPToolCatalogCacheKey,
)
from core.mcp.tool_catalog_scope import (
    PUBLIC_MCP_TOOL_CATALOG_SCOPE,
    MCPToolCatalogScope,
)
from core.mcp.tool_config_normalization import normalize_server_filter
from core.mcp.tool_entries import SOAI_MCP_SERVER_ID, SOAI_MCP_SERVER_NAME
from core.types.json_value import copy_json_dict, filter_json_mapping

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "build_local_catalog_version",
    "build_openai_tool_definition",
    "clone_tool_catalog_entry",
    "clone_tool_catalog_payload",
    "collect_mcp_tool_catalog",
    "collect_mcp_tool_map",
    "normalize_server_filter",
)

_OPENAI_TOOL_PARAMETERS_FORBIDDEN_TOP_LEVEL_KEYS = frozenset(
    ("oneOf", "anyOf", "allOf", "enum", "const", "not"),
)
_OPENAI_TOOL_PARAMETERS_FORBIDDEN_NESTED_KEYS = frozenset(
    (
        "oneOf",
        "anyOf",
        "allOf",
        "not",
        "if",
        "then",
        "else",
        "dependentRequired",
        "dependentSchemas",
    ),
)


def _default_openai_tool_parameters() -> JSONDict:
    return {"type": "object", "properties": {}, "additionalProperties": True}


def _sanitize_openai_schema_value(value: JSONValue) -> JSONValue:
    if isinstance(value, Mapping):
        sanitized: JSONDict = {}
        for key, item in value.items():
            if not isinstance(key, str):
                continue
            if key in _OPENAI_TOOL_PARAMETERS_FORBIDDEN_NESTED_KEYS:
                continue
            sanitized[key] = _sanitize_openai_schema_value(item)
        return sanitized
    if isinstance(value, list):
        return [_sanitize_openai_schema_value(item) for item in value]
    return value


def _sanitize_openai_tool_parameters(parameters: Mapping[str, JSONValue]) -> JSONDict:
    normalized = copy_json_dict(filter_json_mapping(parameters))
    sanitized_value = _sanitize_openai_schema_value(normalized)
    sanitized = sanitized_value if isinstance(sanitized_value, dict) else {}
    for key in _OPENAI_TOOL_PARAMETERS_FORBIDDEN_TOP_LEVEL_KEYS:
        sanitized.pop(key, None)
    return sanitized


def build_local_catalog_version(
    *,
    local_definitions: Mapping[str, JSONValue],
    available_local_tools: set[str],
) -> str:
    signature_parts: list[str] = []
    for name in sorted(available_local_tools):
        definition = local_definitions.get(name)
        if not isinstance(definition, Mapping):
            signature_parts.append(name)
            continue
        keys_signature = ",".join(
            sorted(str(key) for key in definition if isinstance(key, str)),
        )
        description_signature = repr(definition.get("description"))
        input_schema_signature = repr(definition.get("input_schema"))
        parameters_signature = repr(definition.get("parameters"))
        signature = "".join(
            (
                f"{name}|{keys_signature}|{description_signature}|",
                f"{input_schema_signature}|{parameters_signature}",
            ),
        )
        signature_parts.append(signature)
    return "|".join(signature_parts)


def _normalize_openai_tool_parameters(parameters: JSONValue | None) -> JSONDict:
    if not isinstance(parameters, Mapping):
        return _default_openai_tool_parameters()
    normalized = _sanitize_openai_tool_parameters(parameters)
    normalized["type"] = "object"
    if not isinstance(normalized.get("properties"), Mapping):
        normalized["properties"] = {}
    return normalized


def build_openai_tool_definition(tool_name: str, definition: Mapping[str, JSONValue]) -> JSONDict:
    parameters = definition.get("parameters")
    if parameters is None:
        parameters = definition.get("input_schema")
    if parameters is None:
        parameters = definition.get("inputSchema")
    description = definition.get("description")
    return {
        "type": "function",
        "function": {
            "name": tool_name,
            "description": description if isinstance(description, str) else "",
            "parameters": _normalize_openai_tool_parameters(parameters),
        },
    }


def clone_tool_catalog_entry(entry: JSONDict) -> JSONDict:
    return copy_json_dict(entry)


def clone_tool_catalog_payload(
    *,
    tool_entries: list[JSONDict] | tuple[JSONDict, ...],
    tools_by_name: Mapping[str, JSONDict],
) -> tuple[list[JSONDict], dict[str, JSONDict]]:
    return (
        [clone_tool_catalog_entry(entry) for entry in tool_entries],
        {name: clone_tool_catalog_entry(entry) for name, entry in tools_by_name.items()},
    )


async def collect_mcp_tool_catalog(
    mcp_server: MCPServerToolCatalogProtocol,
    mcp_remote: MCPRemoteToolCatalogProtocol,
    cache: MCPToolCatalogCache,
    server_configs: Mapping[str, bool] | None = None,
    local_scope: MCPToolCatalogScope = PUBLIC_MCP_TOOL_CATALOG_SCOPE,
) -> tuple[list[JSONDict], dict[str, JSONDict]]:
    normalized_server_filter = normalize_server_filter(server_configs)
    server_filter_signature = tuple(sorted(normalized_server_filter.items()))
    tool_entries: list[JSONDict] = []
    tools_by_name: dict[str, JSONDict] = {}
    local_definitions = mcp_server.registration.tool_definitions(local_scope)
    available_local_tools = set(mcp_server.registration.available_local_tool_names(local_scope))
    local_version = build_local_catalog_version(
        local_definitions=local_definitions,
        available_local_tools=available_local_tools,
    )
    remote_version = await mcp_remote.tool_catalog_version()
    cache_key = MCPToolCatalogCacheKey(
        local_version=local_version,
        local_scope=local_scope,
        remote_version=remote_version,
        server_filter_signature=server_filter_signature,
    )
    cached = await cache.get(cache_key)
    if cached is not None:
        return clone_tool_catalog_payload(
            tool_entries=cached.tool_entries,
            tools_by_name=cached.tools_by_name,
        )
    if normalized_server_filter.get(SOAI_MCP_SERVER_ID, True) is not False:
        for name in sorted(available_local_tools):
            definition = local_definitions.get(name)
            if not isinstance(definition, Mapping):
                continue
            openai_definition = build_openai_tool_definition(name, definition)
            tool_entries.append(openai_definition)
            tools_by_name[name] = {
                "definition": openai_definition,
                "server_id": None,
                "server_name": SOAI_MCP_SERVER_NAME,
                "raw": dict(definition),
            }
    remote_tools = await mcp_remote.list_all_tools()
    for tool in remote_tools:
        server_id = tool.get("server_id")
        raw_name = tool.get("name")
        if not isinstance(server_id, str) or not server_id.strip():
            continue
        normalized_server_id = server_id.strip()
        if normalized_server_filter.get(normalized_server_id, True) is False:
            continue
        if not isinstance(raw_name, str) or not raw_name.strip():
            continue
        qualified_name = encode_qualified_tool_name(normalized_server_id, raw_name.strip())
        openai_definition = build_openai_tool_definition(qualified_name, tool)
        tool_entries.append(openai_definition)
        tools_by_name[qualified_name] = {
            "definition": openai_definition,
            "server_id": normalized_server_id,
            "server_name": tool.get("server_name"),
            "raw": tool,
        }
    cached_tool_entries, cached_tools_by_name = clone_tool_catalog_payload(
        tool_entries=tool_entries,
        tools_by_name=tools_by_name,
    )
    await cache.set(
        MCPToolCatalogCacheEntry(
            key=cache_key,
            tool_entries=tuple(cached_tool_entries),
            tools_by_name=cached_tools_by_name,
        ),
    )
    return clone_tool_catalog_payload(
        tool_entries=tool_entries,
        tools_by_name=tools_by_name,
    )


async def collect_mcp_tool_map(
    mcp_server: MCPServerToolCatalogProtocol,
    mcp_remote: MCPRemoteToolCatalogProtocol,
    cache: MCPToolCatalogCache,
    *,
    local_scope: MCPToolCatalogScope,
) -> dict[str, JSONDict]:
    _tool_entries, tools_by_name = await collect_mcp_tool_catalog(
        mcp_server,
        mcp_remote,
        cache,
        local_scope=local_scope,
    )
    return tools_by_name
