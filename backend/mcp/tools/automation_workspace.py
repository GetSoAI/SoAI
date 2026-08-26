"""SoAI - MCP automation workspace path normalization [backend/mcp/tools/automation_workspace.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exceptions import StateError, ValidationError
from core.types.json import JSONDict
from core.workspaces.model_settings_workspace_path import (
    normalize_payload_model_settings_workspace_path,
)
from core.workspaces.user_workspace_path import require_user_record_workspace_path
from mcp.tools.error import MCPToolError
from mcp.tools.internal_protocols import MCPUtilityToolsProtocol

__all__ = ("normalize_automation_payload_workspace",)


async def normalize_automation_payload_workspace(
    utility_tools: MCPUtilityToolsProtocol,
    *,
    payload: JSONDict,
    user_id: int,
) -> JSONDict:
    user = await utility_tools.database_users.get_account_by_id(user_id)
    if not isinstance(user, dict):
        raise MCPToolError(-32603, "User record not found.")
    try:
        return normalize_payload_model_settings_workspace_path(
            files=utility_tools.files,
            payload=payload,
            user_workspace_path=require_user_record_workspace_path(user),
        )
    except ValidationError as exception:
        raise MCPToolError(-32602, exception.message) from exception
    except StateError as exception:
        raise MCPToolError(-32603, exception.message) from exception
