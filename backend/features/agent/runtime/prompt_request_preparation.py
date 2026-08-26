"""SoAI - Shared agent prompt request preparation [backend/features/agent/runtime/prompt_request_preparation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.agent.prompt_injection_messages import (
    prune_empty_system_and_developer_messages,
)
from core.errors.exceptions import ValidationError
from core.openai.chat_role_sets import OPENAI_PINNED_ROLES
from core.tool_calls.context_compaction_boundary_resolution import (
    resolve_context_compaction_boundaries,
)
from core.types.json_value import copy_json_dict_list
from features.agent.runtime.prompt_context import inject_agent_prompt_context_messages
from features.agent.runtime.tool_prompt_steering import apply_agent_tool_prompt_messages

if TYPE_CHECKING:
    from core.agent.settings_types import AgentSettings
    from core.orchestrator.types import MCPToolContext
    from core.types.json import JSONDict

__all__ = (
    "build_prepared_agent_messages",
    "prepare_agent_prompt_messages",
)


def _insert_scope_message(messages: list[JSONDict], scope_message: JSONDict | None) -> None:
    if scope_message is None:
        return
    insert_at = 0
    for index, message in enumerate(messages):
        role = message.get("role")
        if role in OPENAI_PINNED_ROLES:
            insert_at = index + 1
            continue
        break
    messages.insert(insert_at, scope_message)


def prepare_agent_prompt_messages(
    *,
    messages: list[JSONDict],
    agent_settings: AgentSettings,
    todo_state: JSONDict | None,
    subagent_summaries: list[JSONDict],
    tool_context: MCPToolContext | None,
    scope_message: JSONDict | None = None,
    prune_empty_messages: bool,
) -> list[JSONDict]:
    tools_visible_to_model = bool(tool_context is not None and tool_context.tool_map)
    inject_agent_prompt_context_messages(
        agent_settings=agent_settings,
        todo_state=todo_state,
        subagent_summaries=subagent_summaries,
        messages=messages,
        tools_visible_to_model=tools_visible_to_model,
    )
    _insert_scope_message(messages, scope_message)
    if tools_visible_to_model:
        if tool_context is None:
            raise ValidationError("Prompt preparation requires tool_context when tools exist.")
        tool_names = (
            list(tool_context.visible_tool_names)
            if tool_context.visible_tool_names is not None
            else list(tool_context.tool_map.keys())
        )
        apply_agent_tool_prompt_messages(
            messages=messages,
            agent_mode=agent_settings.mode,
            tool_entries=dict(tool_context.tool_map),
            tool_names=tool_names,
        )
    if prune_empty_messages:
        prune_empty_system_and_developer_messages(messages)
    return messages


def build_prepared_agent_messages(
    *,
    source_messages: list[JSONDict],
    agent_settings: AgentSettings,
    todo_state: JSONDict | None,
    subagent_summaries: list[JSONDict],
    tool_context: MCPToolContext | None,
    scope_message: JSONDict | None = None,
    prune_empty_messages: bool,
) -> list[JSONDict]:
    boundary_resolution = resolve_context_compaction_boundaries(
        source_messages,
        strip_leading_pinned_prefix=True,
    )
    prepared_messages = copy_json_dict_list(boundary_resolution.messages)
    return prepare_agent_prompt_messages(
        messages=prepared_messages,
        agent_settings=agent_settings,
        todo_state=todo_state,
        subagent_summaries=subagent_summaries,
        tool_context=tool_context,
        scope_message=scope_message,
        prune_empty_messages=prune_empty_messages,
    )
