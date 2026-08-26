"""SoAI - MCP utility tool: vault_delete [backend/mcp/tools/vault_delete.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from mcp.tools.argument_runtime import require_authenticated_user_id
from mcp.tools.error import MCPToolError
from mcp.tools.vault_common import (
    require_vault_credential_id,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from mcp.tools.internal_protocols import MCPUtilityToolsProtocol

__all__ = ("tool_vault_delete",)


async def tool_vault_delete(
    utility_tools: MCPUtilityToolsProtocol,
    arguments: JSONDict,
) -> JSONDict:
    user_id = require_authenticated_user_id(utility_tools, tool_name="vault_delete")
    credential_id = require_vault_credential_id(arguments)
    password_vault = utility_tools.database_password_vault
    if password_vault is None:
        raise MCPToolError(-32603, "Password vault is not configured.")
    deleted = await password_vault.delete_credential(user_id, credential_id)
    if not deleted:
        raise MCPToolError(-32602, "Credential not found.")
    return {"deleted": True}
