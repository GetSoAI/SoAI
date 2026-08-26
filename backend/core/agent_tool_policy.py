"""SoAI - Shared agent MCP tool policy helpers [backend/core/agent_tool_policy.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping

from core.agent_mode import is_plan_or_execute_agent_mode
from core.errors.exceptions import ValidationError
from core.tool_calls.plan_mode_policy import plan_mode_block_reason
from core.types.json import JSONDict

__all__ = (
    "agent_mode_requires_mcp_tools",
    "build_subagent_tool_map",
    "collect_plan_mode_block_reasons",
    "resolve_mode_default_tools",
)


def resolve_mode_default_tools(
    *,
    agent_mode: str,
    default_tools: tuple[str, ...],
    plan_tools: tuple[str, ...],
    execute_tools: tuple[str, ...],
) -> list[str]:
    if agent_mode == "plan":
        return list(plan_tools)
    if agent_mode == "execute":
        return list(execute_tools)
    return list(default_tools)


def agent_mode_requires_mcp_tools(agent_mode: str) -> bool:
    return is_plan_or_execute_agent_mode(agent_mode)


def collect_plan_mode_block_reasons(
    *,
    agent_mode: str,
    tool_names: list[str],
    tool_map: Mapping[str, JSONDict],
) -> dict[str, str]:
    if agent_mode != "plan":
        return {}
    blocked: dict[str, str] = {}
    for tool_name in tool_names:
        reason = plan_mode_block_reason(tool_name, tool_map[tool_name])
        if reason is not None:
            blocked[tool_name] = reason
    return blocked


def build_subagent_tool_map(
    parent_tool_map: Mapping[str, JSONDict],
    *,
    subagent_mode: str,
    requested_tools: tuple[str, ...] | None,
    forbidden_tool_names: frozenset[str],
    forbidden_prefixes: tuple[str, ...],
) -> dict[str, JSONDict]:
    requested_tool_names: set[str] | None = None
    if requested_tools is not None:
        requested_tool_names = set(requested_tools)
    subagent_tool_map: dict[str, JSONDict] = {}
    for tool_name, tool_entry in parent_tool_map.items():
        normalized_tool_name = str(tool_name or "").strip()
        if not normalized_tool_name:
            continue
        if normalized_tool_name in forbidden_tool_names:
            continue
        if normalized_tool_name.startswith(forbidden_prefixes):
            continue
        if subagent_mode == "plan":
            if plan_mode_block_reason(normalized_tool_name, tool_entry) is not None:
                continue
        if requested_tool_names is not None and normalized_tool_name not in requested_tool_names:
            continue
        subagent_tool_map[normalized_tool_name] = dict(tool_entry)
    if requested_tool_names is not None and set(subagent_tool_map.keys()) != requested_tool_names:
        raise ValidationError("subagent_spawn.tools may only narrow the allowed subagent tool set.")
    return subagent_tool_map
