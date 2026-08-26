"""SoAI - MCP files root runtime resolution helpers [backend/mcp/workspace_resolution.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import StateError
from core.files.path_resolver import ConfigFilesPathResolver
from core.mcp.qualified_name import decode_qualified_tool_name
from core.types.json import JSONDict
from core.users.user_id import is_strict_user_id
from core.workspaces.user_workspace_path import resolve_user_record_workspace_access
from mcp.tools.browser.session_access import (
    build_browser_owner_key,
    parse_browser_profile,
    parse_browser_session_scope,
    resolve_browser_owner_base,
)

if TYPE_CHECKING:
    from core.config.protocols import ConfigProtocol
    from core.users.protocols_database import DatabaseUsersProtocol
    from mcp.tools.internal_protocols import (
        MCPToolRuntimeSessionStoreProtocol,
        MCPUtilityToolsProtocol,
    )

__all__ = (
    "ensure_runtime_workspace_path_from_user",
    "propagate_runtime_workspace_path_for_tool_execution",
    "resolve_tool_execution_workspace_owner_keys",
    "resolve_user_workspace_path",
    "set_runtime_workspace_path_for_owner_keys",
)


async def resolve_user_workspace_path(
    *,
    database_users: DatabaseUsersProtocol,
    config: ConfigProtocol,
    user_id: int,
) -> str:
    user_record = await database_users.get_account_by_id(user_id)
    if user_record is None:
        raise StateError("Account is unavailable for MCP tool execution.")
    return resolve_user_record_workspace_access(
        ConfigFilesPathResolver(config),
        user_record,
    )


async def ensure_runtime_workspace_path_from_user(
    *,
    runtime_sessions: MCPToolRuntimeSessionStoreProtocol,
    database_users: DatabaseUsersProtocol,
    config: ConfigProtocol,
    user_id: int,
    owner_key: str | None = None,
) -> str | None:
    if not is_strict_user_id(user_id):
        return None
    state = runtime_sessions.get_or_create_workspace_state(owner_key)
    configured_workspace_path = state.workspace_path
    if isinstance(configured_workspace_path, str) and configured_workspace_path.strip():
        return configured_workspace_path
    resolved_workspace_path = await resolve_user_workspace_path(
        database_users=database_users,
        config=config,
        user_id=user_id,
    )
    runtime_sessions.set_workspace_path(resolved_workspace_path, owner_key)
    return resolved_workspace_path


def _is_local_browser_tool(tool_name: str) -> bool:
    normalized_tool_name = str(tool_name or "").strip()
    if not normalized_tool_name:
        return False
    server_id, local_tool_name = decode_qualified_tool_name(normalized_tool_name)
    if server_id is not None:
        return False
    return str(local_tool_name or "").strip().startswith("browser_")


def resolve_tool_execution_workspace_owner_keys(
    *,
    utility_tools: MCPUtilityToolsProtocol,
    tool_name: str,
    arguments: JSONDict,
    owner_key: str,
) -> tuple[str, ...]:
    resolved_owner_key = str(owner_key or "").strip()
    if not resolved_owner_key:
        return ()
    owner_keys: list[str] = [resolved_owner_key]
    if not _is_local_browser_tool(tool_name):
        return tuple(owner_keys)
    profile = parse_browser_profile(arguments, config=utility_tools.config)
    session_scope = parse_browser_session_scope(arguments, config=utility_tools.config)
    owner_base = resolve_browser_owner_base(utility_tools, session_scope=session_scope)
    browser_owner_key = build_browser_owner_key(
        owner_base=owner_base,
        profile=profile,
        session_scope=session_scope,
    )
    for candidate in (owner_base, browser_owner_key):
        normalized_candidate = str(candidate or "").strip()
        if normalized_candidate and normalized_candidate not in owner_keys:
            owner_keys.append(normalized_candidate)
    return tuple(owner_keys)


def set_runtime_workspace_path_for_owner_keys(
    *,
    runtime_sessions: MCPToolRuntimeSessionStoreProtocol,
    workspace_path: str,
    owner_keys: tuple[str, ...],
) -> None:
    for owner_key in owner_keys:
        runtime_sessions.set_workspace_path(workspace_path, owner_key=owner_key)


def propagate_runtime_workspace_path_for_tool_execution(
    *,
    utility_tools: MCPUtilityToolsProtocol,
    tool_name: str,
    arguments: JSONDict,
    owner_key: str,
    workspace_path: str,
) -> None:
    owner_keys = resolve_tool_execution_workspace_owner_keys(
        utility_tools=utility_tools,
        tool_name=tool_name,
        arguments=arguments,
        owner_key=owner_key,
    )
    set_runtime_workspace_path_for_owner_keys(
        runtime_sessions=utility_tools.runtime_sessions,
        workspace_path=workspace_path,
        owner_keys=tuple(
            scoped_owner_key for scoped_owner_key in owner_keys if scoped_owner_key != owner_key
        ),
    )
