"""SoAI - Injected prompt message list management [backend/core/agent/prompt_injection_messages.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

from core.agent.prompt_injection_support import (
    build_subagent_state_system_message,
    build_todo_state_system_message,
)
from core.openai.chat_role_sets import OPENAI_PINNED_ROLES
from core.openai.internal_message_metadata import (
    AGENT_CAPABILITY_POLICIES_MESSAGE_TYPE,
    AGENT_INSTRUCTIONS_MESSAGE_TYPE,
    AGENT_MODE_MESSAGE_TYPE,
    AGENT_PATH_HINTS_MESSAGE_TYPE,
    AGENT_SUBAGENT_STATE_MESSAGE_TYPE,
    AGENT_TODO_STATE_MESSAGE_TYPE,
    AGENT_TOOL_CONTEXT_MESSAGE_TYPE,
    AGENT_TOOL_HINTS_MESSAGE_TYPE,
    AGENT_WORKSPACE_CONTEXT_MESSAGE_TYPE,
    INJECTED_AGENT_MESSAGE_TYPES,
    SOAI_MESSAGE_TYPE_FIELD,
    has_internal_message_type,
)
from core.types.json import JSONDict

__all__ = (
    "InjectedPromptMessages",
    "extract_injected_prompt_messages",
    "prune_empty_system_and_developer_messages",
    "prune_injected_prompt_messages",
    "rebuild_injected_prompt_messages",
    "refresh_agent_subagent_state_prompt_message",
    "refresh_agent_todo_state_prompt_message",
    "upsert_agent_tool_prompt_messages",
)


def _is_injected_prompt_system_message(message: JSONDict) -> bool:
    return message.get("role") == "system" and has_internal_message_type(
        message,
        INJECTED_AGENT_MESSAGE_TYPES,
    )


@dataclass(frozen=True, slots=True)
class InjectedPromptMessages:
    mode_message: JSONDict | None
    todo_state_message: JSONDict | None
    workspace_context_message: JSONDict | None
    path_hints_message: JSONDict | None
    subagent_state_message: JSONDict | None
    tool_context_message: JSONDict | None
    capability_policies_message: JSONDict | None
    tool_hints_message: JSONDict | None
    agents_message: JSONDict | None


def prune_injected_prompt_messages(messages: list[JSONDict]) -> None:
    filtered: list[JSONDict] = []
    for message in messages:
        if not isinstance(message, dict):
            filtered.append(message)
            continue
        if _is_injected_prompt_system_message(message):
            continue
        filtered.append(message)
    messages[:] = filtered
    prune_empty_system_and_developer_messages(messages)


def prune_empty_system_and_developer_messages(messages: list[JSONDict]) -> None:
    filtered: list[JSONDict] = []
    for message in messages:
        if not isinstance(message, dict):
            filtered.append(message)
            continue
        role = message.get("role")
        if role in OPENAI_PINNED_ROLES:
            content = message.get("content")
            if content is None:
                continue
            if isinstance(content, str) and not content.strip():
                continue
        filtered.append(message)
    messages[:] = filtered


def rebuild_injected_prompt_messages(
    messages: list[JSONDict],
    *,
    mode_message: JSONDict | None,
    todo_state_message: JSONDict | None,
    workspace_context_message: JSONDict | None,
    path_hints_message: JSONDict | None,
    subagent_state_message: JSONDict | None,
    tool_context_message: JSONDict | None = None,
    capability_policies_message: JSONDict | None = None,
    tool_hints_message: JSONDict | None = None,
    agents_message: JSONDict | None = None,
) -> None:
    prune_injected_prompt_messages(messages)
    ordered_messages = [
        mode_message,
        todo_state_message,
        workspace_context_message,
        path_hints_message,
        subagent_state_message,
        tool_context_message,
        capability_policies_message,
        tool_hints_message,
        agents_message,
    ]
    insert_at = 0
    for index, existing in enumerate(messages):
        if not isinstance(existing, dict):
            continue
        if existing.get("role") in OPENAI_PINNED_ROLES:
            insert_at = index + 1
    for injected in ordered_messages:
        if injected is None:
            continue
        if not _should_insert_injected_message(injected):
            continue
        messages.insert(insert_at, injected)
        insert_at += 1
    prune_empty_system_and_developer_messages(messages)


def extract_injected_prompt_messages(messages: list[JSONDict]) -> InjectedPromptMessages:
    return InjectedPromptMessages(
        mode_message=_extract_typed_system_message(messages, AGENT_MODE_MESSAGE_TYPE),
        todo_state_message=_extract_typed_system_message(
            messages,
            AGENT_TODO_STATE_MESSAGE_TYPE,
        ),
        workspace_context_message=_extract_typed_system_message(
            messages,
            AGENT_WORKSPACE_CONTEXT_MESSAGE_TYPE,
        ),
        path_hints_message=_extract_typed_system_message(
            messages,
            AGENT_PATH_HINTS_MESSAGE_TYPE,
        ),
        subagent_state_message=_extract_typed_system_message(
            messages,
            AGENT_SUBAGENT_STATE_MESSAGE_TYPE,
        ),
        tool_context_message=_extract_typed_system_message(
            messages,
            AGENT_TOOL_CONTEXT_MESSAGE_TYPE,
        ),
        capability_policies_message=_extract_typed_system_message(
            messages,
            AGENT_CAPABILITY_POLICIES_MESSAGE_TYPE,
        ),
        tool_hints_message=_extract_typed_system_message(
            messages,
            AGENT_TOOL_HINTS_MESSAGE_TYPE,
        ),
        agents_message=_extract_typed_system_message(
            messages,
            AGENT_INSTRUCTIONS_MESSAGE_TYPE,
        ),
    )


def upsert_agent_tool_prompt_messages(
    messages: list[JSONDict],
    *,
    tool_context_message: JSONDict | None,
    capability_policies_message: JSONDict | None,
    tool_hints_message: JSONDict | None,
) -> None:
    injected = extract_injected_prompt_messages(messages)
    rebuild_injected_prompt_messages(
        messages,
        mode_message=injected.mode_message,
        todo_state_message=injected.todo_state_message,
        workspace_context_message=injected.workspace_context_message,
        path_hints_message=injected.path_hints_message,
        subagent_state_message=injected.subagent_state_message,
        tool_context_message=tool_context_message,
        capability_policies_message=capability_policies_message,
        tool_hints_message=tool_hints_message,
        agents_message=injected.agents_message,
    )


def refresh_agent_todo_state_prompt_message(
    messages: list[JSONDict],
    *,
    todo_state: JSONDict | None,
) -> None:
    replacement = build_todo_state_system_message(todo_state)
    if _replace_typed_system_message(
        messages,
        message_type=AGENT_TODO_STATE_MESSAGE_TYPE,
        replacement=replacement,
    ):
        return
    injected = extract_injected_prompt_messages(messages)
    rebuild_injected_prompt_messages(
        messages,
        mode_message=injected.mode_message,
        todo_state_message=replacement,
        workspace_context_message=injected.workspace_context_message,
        path_hints_message=injected.path_hints_message,
        subagent_state_message=injected.subagent_state_message,
        tool_context_message=injected.tool_context_message,
        capability_policies_message=injected.capability_policies_message,
        tool_hints_message=injected.tool_hints_message,
        agents_message=injected.agents_message,
    )


def refresh_agent_subagent_state_prompt_message(
    messages: list[JSONDict],
    *,
    subagent_summaries: list[JSONDict],
) -> None:
    replacement = build_subagent_state_system_message(subagent_summaries)
    if _replace_typed_system_message(
        messages,
        message_type=AGENT_SUBAGENT_STATE_MESSAGE_TYPE,
        replacement=replacement,
    ):
        return
    injected = extract_injected_prompt_messages(messages)
    rebuild_injected_prompt_messages(
        messages,
        mode_message=injected.mode_message,
        todo_state_message=injected.todo_state_message,
        workspace_context_message=injected.workspace_context_message,
        path_hints_message=injected.path_hints_message,
        subagent_state_message=replacement,
        tool_context_message=injected.tool_context_message,
        capability_policies_message=injected.capability_policies_message,
        tool_hints_message=injected.tool_hints_message,
        agents_message=injected.agents_message,
    )


def _extract_typed_system_message(
    messages: list[JSONDict],
    message_type: str,
) -> JSONDict | None:
    for message in messages:
        if not isinstance(message, dict):
            continue
        if _is_typed_system_message(message, message_type):
            return dict(message)
    return None


def _replace_typed_system_message(
    messages: list[JSONDict],
    *,
    message_type: str,
    replacement: JSONDict,
) -> bool:
    for index, message in enumerate(messages):
        if not isinstance(message, dict):
            continue
        if not _is_typed_system_message(message, message_type):
            continue
        messages[index] = replacement
        return True
    return False


def _is_typed_system_message(message: JSONDict, message_type: str) -> bool:
    return message.get("role") == "system" and message.get(SOAI_MESSAGE_TYPE_FIELD) == message_type


def _should_insert_injected_message(message: JSONDict | None) -> bool:
    if not isinstance(message, dict):
        return False
    role = message.get("role")
    if role not in OPENAI_PINNED_ROLES:
        return False
    content = message.get("content")
    return (
        isinstance(content, str)
        and bool(content.strip())
        and _is_injected_prompt_system_message(message)
    )
