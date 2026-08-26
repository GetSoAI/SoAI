"""SoAI - MCP server config update validation [backend/features/api/runtime/mcp_server_configs_validation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.mcp.protocols_storage import DatabaseMCPProtocol
from core.mcp.tool_entries import SOAI_MCP_SERVER_ID
from core.runtime.protocols import RequestProtocol
from core.types.json import JSONValue
from features.api.runtime.errors import raise_invalid_request

__all__ = ("load_mcp_server_ids", "normalize_server_configs")


async def load_mcp_server_ids(database_mcp: DatabaseMCPProtocol) -> set[str]:
    servers = await database_mcp.get_all_mcp_servers()
    server_ids: set[str] = set()
    for server in servers:
        server_id = str(server.get("id") or "").strip()
        if server_id:
            server_ids.add(server_id)
    return server_ids


def normalize_server_configs(
    *,
    request: RequestProtocol,
    server_configs: JSONValue,
    server_ids: set[str],
) -> dict[str, bool]:
    if not isinstance(server_configs, dict):
        raise_invalid_request(request, "MCP server configs must be an object.")
    normalized: dict[str, bool] = {}
    for config_key, config_value in server_configs.items():
        if not isinstance(config_key, str):
            raise_invalid_request(request, "MCP server config ids must be strings.")
        normalized_key = config_key.strip()
        if not normalized_key:
            raise_invalid_request(request, "MCP server config ids cannot be empty.")
        if not isinstance(config_value, bool):
            raise_invalid_request(
                request,
                f"MCP server config '{normalized_key}' must be a boolean.",
            )
        normalized[normalized_key] = config_value
    valid_server_ids = set(server_ids)
    valid_server_ids.add(SOAI_MCP_SERVER_ID)
    invalid_servers = sorted([key for key in normalized if key not in valid_server_ids])
    if invalid_servers:
        raise_invalid_request(request, f"Unknown MCP server ids: {', '.join(invalid_servers)}")
    return normalized
