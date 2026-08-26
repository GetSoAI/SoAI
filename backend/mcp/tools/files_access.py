"""SoAI - MCP tool files root argument resolution [backend/mcp/tools/files_access.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from mcp.tools.argument_fields import normalize_string_argument
from mcp.tools.error import MCPToolError, build_invalid_params_error
from mcp.tools.files_paths import (
    resolve_existing_dir_under_workspace,
    resolve_existing_file_under_workspace,
    resolve_path_under_workspace_or_tool_error,
)

if TYPE_CHECKING:
    from core.types.json import JSONValue
    from mcp.tools.internal_protocols import MCPUtilityToolsProtocol
    from mcp.tools.runtime_sessions import ToolWorkspaceState

__all__ = (
    "get_workspace_context",
    "normalize_str",
    "resolve_document_id_to_file_path",
    "resolve_existing_dir",
    "resolve_existing_file",
    "resolve_existing_file_source",
    "resolve_file_id_to_file_path",
    "resolve_workspace_path",
)


def get_workspace_context(
    utility_tools: MCPUtilityToolsProtocol,
) -> tuple[str, ToolWorkspaceState, str]:
    owner_key = utility_tools.runtime_sessions.current_owner_key()
    state = utility_tools.runtime_sessions.get_or_create_workspace_state(owner_key)
    root = utility_tools.runtime_sessions.require_workspace_path(owner_key)
    return (owner_key, state, root)


def resolve_existing_dir(
    utility_tools: MCPUtilityToolsProtocol,
    dir_path: str,
    *,
    description: str,
) -> str:
    _, _state, workspace_path = get_workspace_context(utility_tools)
    return resolve_existing_dir_under_workspace(
        dir_path,
        workspace_path=workspace_path,
        description=description,
    )


def resolve_existing_file(
    utility_tools: MCPUtilityToolsProtocol,
    file_path: str,
    *,
    description: str,
) -> str:
    _, _state, workspace_path = get_workspace_context(utility_tools)
    try:
        return resolve_existing_file_under_workspace(
            file_path,
            workspace_path=workspace_path,
            description=description,
        )
    except ValidationError as exception:
        raise build_invalid_params_error(str(exception)) from exception


async def resolve_file_id_to_file_path(utility_tools: MCPUtilityToolsProtocol, file_id: str) -> str:
    if not utility_tools.database_files:
        raise MCPToolError(-32603, "Database access not configured")
    file_info = await utility_tools.database_files.get_file_info_with_path(str(file_id).strip())
    if not file_info:
        raise MCPToolError(-32602, f"File not found: {file_id}")
    file_path_value = file_info.get("file_path")
    if not isinstance(file_path_value, str) or not file_path_value:
        raise MCPToolError(-32602, f"File has no path: {file_id}")
    return file_path_value


async def resolve_document_id_to_file_path(
    utility_tools: MCPUtilityToolsProtocol,
    document_id: str,
) -> str:
    if not utility_tools.database_files:
        raise MCPToolError(-32603, "Database access not configured")
    rag_doc = await utility_tools.database_files.get_rag_document_by_id(str(document_id).strip())
    if not rag_doc:
        raise MCPToolError(-32602, f"Document not found: {document_id}")
    linked_file_id_value = rag_doc.get("file_id")
    if not isinstance(linked_file_id_value, str) or not linked_file_id_value:
        raise MCPToolError(-32602, f"Document has no associated file: {document_id}")
    file_info = await utility_tools.database_files.get_file_info_with_path(linked_file_id_value)
    if not file_info:
        raise MCPToolError(-32602, f"Linked file not found: {linked_file_id_value}")
    file_path_value = file_info.get("file_path")
    if not isinstance(file_path_value, str) or not file_path_value:
        raise MCPToolError(-32602, f"Linked file has no path: {linked_file_id_value}")
    return file_path_value


async def resolve_existing_file_source(
    utility_tools: MCPUtilityToolsProtocol,
    *,
    file_id: str | None,
    document_id: str | None,
    file_path: str | None,
    missing_message: str,
    description: str = "file_path",
) -> str:
    if file_id is not None:
        resolved_from_file_id = await resolve_file_id_to_file_path(utility_tools, file_id)
        return resolve_existing_file(utility_tools, resolved_from_file_id, description=description)
    if document_id is not None:
        resolved_from_document_id = await resolve_document_id_to_file_path(
            utility_tools,
            document_id,
        )
        return resolve_existing_file(
            utility_tools,
            resolved_from_document_id,
            description=description,
        )
    if file_path is not None:
        return resolve_existing_file(utility_tools, file_path, description=description)
    raise MCPToolError(-32602, missing_message)


def resolve_workspace_path(
    utility_tools: MCPUtilityToolsProtocol,
    path_value: str,
    *,
    description: str,
) -> str:
    _, _state, workspace_path = get_workspace_context(utility_tools)
    return resolve_path_under_workspace_or_tool_error(
        path_value,
        workspace_path=workspace_path,
        description=description,
    )


def normalize_str(value: JSONValue, *, field: str, required: bool) -> str | None:
    return normalize_string_argument(value, field=field, required=required)
