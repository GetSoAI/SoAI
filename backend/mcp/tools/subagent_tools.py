"""SoAI - MCP utility tools: subagent_* [backend/mcp/tools/subagent_tools.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.agent.protocols import SubagentSpawnRequest
from core.agent.subagent_serialization import (
    serialize_subagent_accepted_execution,
    serialize_subagent_cancel_result,
    serialize_subagent_snapshot,
)
from core.errors.exceptions import SoAITimeoutError
from core.tool_calls.deferred_tool_call_signal import mark_result_deferred
from core.validation.integers import is_strict_int
from mcp.tools.argument_fields import (
    optional_string,
    reject_unexpected_parameters,
    require_non_empty_string,
)
from mcp.tools.error import MCPToolError
from mcp.tools.internal_protocols import MCPUtilityToolsProtocol
from mcp.tools.timeout_ms import resolve_timeout_ms

if TYPE_CHECKING:
    from core.agent.protocols import AgentSubagentServiceProtocol
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "tool_subagent_cancel",
    "tool_subagent_observe",
    "tool_subagent_spawn",
)

_ALLOWED_SUBAGENT_SPAWN_KEYS: frozenset[str] = frozenset(
    {
        "task",
        "context",
        "mode",
        "display_name",
        "model",
        "workspace_path",
        "max_iterations",
        "tools",
    },
)
_ALLOWED_SUBAGENT_ID_KEYS: frozenset[str] = frozenset({"subagent_id"})
_ALLOWED_SUBAGENT_OBSERVE_KEYS: frozenset[str] = frozenset(
    {"subagent_id", "mode", "timeout_ms"},
)
_DEFAULT_SUBAGENT_OBSERVE_TIMEOUT_MS: int | None = None
_SUBAGENT_OBSERVE_MODE_CURRENT = "current"
_SUBAGENT_OBSERVE_MODE_TERMINAL = "terminal"


def _require_subagent_service(
    utility_tools: MCPUtilityToolsProtocol,
) -> AgentSubagentServiceProtocol:
    service = utility_tools.subagent_service
    if service is None:
        raise MCPToolError(-32603, "Subagent service is not configured.")
    return service


def _optional_positive_int(value: JSONValue, *, key: str) -> int | None:
    if value is None:
        return None
    if not is_strict_int(value):
        raise MCPToolError(-32602, f"{key} must be an integer when provided")
    if value <= 0:
        raise MCPToolError(-32602, f"{key} must be a positive integer when provided")
    return int(value)


def _optional_tools(value: JSONValue) -> tuple[str, ...] | None:
    if value is None:
        return None
    if not isinstance(value, list):
        raise MCPToolError(-32602, "tools must be an array when provided")
    tool_names: list[str] = []
    for entry in value:
        tool_names.append(require_non_empty_string(entry, key="tools[]"))
    return tuple(tool_names)


async def tool_subagent_spawn(
    utility_tools: MCPUtilityToolsProtocol,
    arguments: JSONDict,
) -> JSONDict:
    reject_unexpected_parameters(arguments, _ALLOWED_SUBAGENT_SPAWN_KEYS)
    service = _require_subagent_service(utility_tools)
    subagent = await service.spawn_subagent(
        SubagentSpawnRequest(
            task=require_non_empty_string(arguments.get("task"), key="task"),
            context=optional_string(arguments.get("context"), key="context"),
            mode=optional_string(arguments.get("mode"), key="mode"),
            display_name=optional_string(arguments.get("display_name"), key="display_name"),
            model=optional_string(arguments.get("model"), key="model"),
            workspace_path=optional_string(
                arguments.get("workspace_path"),
                key="workspace_path",
            ),
            max_iterations=_optional_positive_int(
                arguments.get("max_iterations"),
                key="max_iterations",
            ),
            tools=_optional_tools(arguments.get("tools")),
        ),
    )
    return mark_result_deferred(
        {
            "subagent": serialize_subagent_accepted_execution(subagent),
            "subagent_stream": {"tool_calls": []},
        },
    )


async def tool_subagent_observe(
    utility_tools: MCPUtilityToolsProtocol,
    arguments: JSONDict,
) -> JSONDict:
    reject_unexpected_parameters(arguments, _ALLOWED_SUBAGENT_OBSERVE_KEYS)
    service = _require_subagent_service(utility_tools)
    mode = require_non_empty_string(arguments.get("mode"), key="mode")
    if mode not in {_SUBAGENT_OBSERVE_MODE_CURRENT, _SUBAGENT_OBSERVE_MODE_TERMINAL}:
        raise MCPToolError(-32602, "mode must be current or terminal")
    if mode == _SUBAGENT_OBSERVE_MODE_CURRENT and "timeout_ms" in arguments:
        raise MCPToolError(-32602, "timeout_ms is only valid when mode is terminal")
    resolved_timeout_ms: int | None = 0
    if mode == _SUBAGENT_OBSERVE_MODE_TERMINAL:
        resolved_timeout_ms = resolve_timeout_ms(
            arguments,
            field_name="timeout_ms",
            config=utility_tools.config,
            config_key="TOOLS.MCP.SUBAGENT.OBSERVE_TIMEOUT_MS",
            default_timeout_ms=_DEFAULT_SUBAGENT_OBSERVE_TIMEOUT_MS,
        )
        if resolved_timeout_ms == 0:
            raise MCPToolError(-32602, "timeout_ms must be positive or null when provided")
    subagent_id = require_non_empty_string(arguments.get("subagent_id"), key="subagent_id")
    try:
        snapshot = await service.wait_for_subagent(
            subagent_id=subagent_id,
            timeout_ms=resolved_timeout_ms,
        )
        return {"subagent": serialize_subagent_snapshot(snapshot), "timed_out": False}
    except (SoAITimeoutError, TimeoutError):
        latest = await service.get_subagent(subagent_id=subagent_id)
        return {"subagent": serialize_subagent_snapshot(latest), "timed_out": True}


async def tool_subagent_cancel(
    utility_tools: MCPUtilityToolsProtocol,
    arguments: JSONDict,
) -> JSONDict:
    reject_unexpected_parameters(arguments, _ALLOWED_SUBAGENT_ID_KEYS)
    service = _require_subagent_service(utility_tools)
    return serialize_subagent_cancel_result(
        await service.cancel_subagent(
            subagent_id=require_non_empty_string(arguments.get("subagent_id"), key="subagent_id"),
        ),
    )
