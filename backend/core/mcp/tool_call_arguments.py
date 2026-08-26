"""SoAI - MCP tools/call argument normalization [backend/core/mcp/tool_call_arguments.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.types.json_value import is_json_value

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "MCPToolCallArguments",
    "parse_mcp_tool_call_arguments",
)


@dataclass(frozen=True, slots=True)
class MCPToolCallArguments:
    name: str
    arguments: JSONDict
    task_requested: bool


def parse_mcp_tool_call_arguments(
    parameters: JSONDict,
    *,
    build_error: Callable[[int, str], Exception],
) -> MCPToolCallArguments:
    if not isinstance(parameters, dict):
        raise build_error(
            -32602,
            f"Invalid params type for tools/call: {type(parameters).__name__}",
        )
    name_raw = parameters.get("name")
    if not isinstance(name_raw, str) or not name_raw.strip():
        raise build_error(
            -32602,
            "Invalid or missing tool call name.",
        )
    name = name_raw.strip()
    arguments_raw = parameters.get("arguments")
    arguments: JSONDict = {}
    if arguments_raw is not None:
        if not isinstance(arguments_raw, dict):
            raise build_error(
                -32602,
                f"Invalid arguments type for tool call '{name}': {type(arguments_raw).__name__}",
            )
        for raw_key, raw_value in arguments_raw.items():
            if not isinstance(raw_key, str):
                raise build_error(
                    -32602,
                    f"Invalid argument key type for tool call '{name}': {type(raw_key).__name__}",
                )
            if not is_json_value(raw_value):
                value_type = type(raw_value).__name__
                raise build_error(
                    -32602,
                    (
                        f"Invalid argument value for tool call '{name}' "
                        f"at key '{raw_key}': {value_type}"
                    ),
                )
            arguments[raw_key] = raw_value
    task_raw = parameters.get("task")
    if task_raw is None:
        task_requested = False
    elif isinstance(task_raw, bool):
        task_requested = task_raw
    else:
        raise build_error(
            -32602,
            f"Invalid task flag type for tool call '{name}': {type(task_raw).__name__}",
        )
    return MCPToolCallArguments(
        name=name,
        arguments=arguments,
        task_requested=task_requested,
    )
