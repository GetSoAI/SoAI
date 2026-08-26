"""SoAI - MCP shell transcript read and search tools [backend/mcp/tools/shell_output_tools.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.mcp.argument_validation import require_no_unknown_keys, require_non_empty_string_value
from core.state.access import AccessAction
from mcp.tools.access_control import require_tool_action
from mcp.tools.argument_scalars import parse_bool_strict_default
from mcp.tools.error import MCPToolError, build_invalid_params_error, get_arg
from mcp.tools.shell_output_arguments import parse_shell_output_limit, parse_shell_output_offset
from mcp.tools.shell_session_support import parse_session_id

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from mcp.tools.internal_protocols import MCPUtilityToolsProtocol

__all__ = ("tool_shell_output_read", "tool_shell_output_search")

_READ_KEYS: frozenset[str] = frozenset({"session_id", "offset", "limit", "from_end"})
_SEARCH_KEYS: frozenset[str] = frozenset(
    {"session_id", "query", "offset", "limit", "case_sensitive"},
)


def _require_only_allowed_keys(
    arguments: JSONDict, allowed: frozenset[str], tool_name: str
) -> None:
    require_no_unknown_keys(
        arguments,
        allowed,
        build_error=build_invalid_params_error,
        message=lambda unknown_keys: f"{tool_name} received unknown parameter(s): {', '.join(unknown_keys)}",
    )


async def _require_shell_output_access(
    utility_tools: MCPUtilityToolsProtocol,
    *,
    tool_name: str,
    session_id: int,
) -> None:
    await require_tool_action(
        utility_tools,
        action=AccessAction.TERMINAL_USE,
        tool_name=tool_name,
    )
    session = utility_tools.runtime_sessions.get_shell_session(session_id)
    owner_key = utility_tools.runtime_sessions.current_owner_key()
    if session is None or session.owner_key != owner_key:
        raise MCPToolError(-32602, f"Unknown session_id: {session_id}")


async def tool_shell_output_read(
    utility_tools: MCPUtilityToolsProtocol,
    arguments: JSONDict,
) -> JSONDict:
    _require_only_allowed_keys(arguments, _READ_KEYS, "shell_output_read")
    session_id = parse_session_id(get_arg(arguments, "session_id"))
    await _require_shell_output_access(
        utility_tools,
        tool_name="shell_output_read",
        session_id=session_id,
    )
    offset = parse_shell_output_offset(arguments.get("offset"))
    limit = parse_shell_output_limit(arguments.get("limit"))
    from_end = parse_bool_strict_default(
        arguments.get("from_end"),
        field_name="from_end",
        default=False,
    )
    result = utility_tools.runtime_sessions.read_shell_transcript_lines(
        session_id,
        offset,
        limit,
        from_end,
    )
    result["session_id"] = session_id
    return result


async def tool_shell_output_search(
    utility_tools: MCPUtilityToolsProtocol,
    arguments: JSONDict,
) -> JSONDict:
    _require_only_allowed_keys(arguments, _SEARCH_KEYS, "shell_output_search")
    session_id = parse_session_id(get_arg(arguments, "session_id"))
    await _require_shell_output_access(
        utility_tools,
        tool_name="shell_output_search",
        session_id=session_id,
    )
    query = require_non_empty_string_value(
        arguments.get("query"),
        build_error=build_invalid_params_error,
        type_message="query must be a non-empty string",
        empty_message="query must be a non-empty string",
    )
    offset = parse_shell_output_offset(arguments.get("offset"))
    limit = parse_shell_output_limit(arguments.get("limit"))
    case_sensitive = parse_bool_strict_default(
        arguments.get("case_sensitive"),
        field_name="case_sensitive",
        default=False,
    )
    result = utility_tools.runtime_sessions.search_shell_transcript(
        session_id,
        query,
        offset,
        limit,
        case_sensitive,
    )
    result["session_id"] = session_id
    return result
