"""SoAI - MCP utility tool: vault_search [backend/mcp/tools/vault_search.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from mcp.tools.argument_runtime import require_authenticated_user_id
from mcp.tools.error import MCPToolError, get_arg
from mcp.tools.vault_common import format_vault_credential

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from mcp.tools.internal_protocols import MCPUtilityToolsProtocol

__all__ = ("tool_vault_search",)


def _require_query(arguments: JSONDict) -> str:
    value = get_arg(arguments, "query")
    text = value.strip() if isinstance(value, str) else ""
    if not text:
        raise MCPToolError(-32602, "query must be a non-empty string.")
    return text


async def tool_vault_search(
    utility_tools: MCPUtilityToolsProtocol,
    arguments: JSONDict,
) -> JSONDict:
    user_id = require_authenticated_user_id(utility_tools, tool_name="vault_search")
    query = _require_query(arguments)
    password_vault = utility_tools.database_password_vault
    if password_vault is None:
        raise MCPToolError(-32603, "Password vault is not configured.")
    credentials = await password_vault.list_credentials(
        user_id,
        query=query,
        limit=200,
        offset=0,
    )
    return {"credentials": [format_vault_credential(item) for item in credentials]}
