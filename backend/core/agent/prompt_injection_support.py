"""SoAI - Shared agent prompt injection support [backend/core/agent/prompt_injection_support.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TypedDict

from core.agent.prompt_injection_slots import (
    CAPABILITY_POLICIES_TAG,
    PATH_HINTS_TAG,
    SUBAGENT_STATE_TAG,
    TODO_STATE_TAG,
    TOOL_CONTEXT_TAG,
    TOOL_HINTS_TAG,
    WORKSPACE_CONTEXT_TAG,
    build_injected_prompt_xml,
)
from core.agent.status_values import SUBAGENT_STATUS_RUNNING
from core.agent.todo_state_parsing import (
    parse_agent_todo_state_payload,
    render_agent_todo_state_payload,
)
from core.openai.internal_message_metadata import (
    AGENT_CAPABILITY_POLICIES_MESSAGE_TYPE,
    AGENT_PATH_HINTS_MESSAGE_TYPE,
    AGENT_SUBAGENT_STATE_MESSAGE_TYPE,
    AGENT_TODO_STATE_MESSAGE_TYPE,
    AGENT_TOOL_CONTEXT_MESSAGE_TYPE,
    AGENT_TOOL_HINTS_MESSAGE_TYPE,
    AGENT_WORKSPACE_CONTEXT_MESSAGE_TYPE,
    build_internal_system_message,
)
from core.prompts.system_prompts import get_text_prompt_v1
from core.serialization.json import serialize_json_compact_stable_strict
from core.types.json import JSONDict, JSONValue
from core.types.json_value import filter_json_mapping_strict

__all__ = (
    "build_capability_policies_system_message",
    "build_files_path_hints_system_message",
    "build_subagent_state_system_message",
    "build_todo_state_system_message",
    "build_tool_context_system_message",
    "build_tool_hints_system_message",
    "build_workspace_context_system_message",
    "normalize_todo_state_for_prompt_injection",
)


class _WorkspaceContextFields(TypedDict):
    workspace_path: str


class _PathHintsFields(TypedDict):
    workspace_path: str
    warning: str


class _SubagentSummaryFields(TypedDict):
    subagent_id: str
    status: str
    mode: JSONValue
    display_name: JSONValue
    result_text: JSONValue
    error_message: JSONValue
    token_usage: JSONValue


class _SubagentStateFields(TypedDict):
    instruction: str
    required_next_actions: list[str]
    running_subagents: int
    total_subagents: int
    unresolved_subagent_ids: list[str]
    subagents: list[_SubagentSummaryFields]


def normalize_todo_state_for_prompt_injection(todo_state: JSONDict | None) -> JSONDict:
    state = parse_agent_todo_state_payload(todo_state)
    return render_agent_todo_state_payload(state)


def build_workspace_context_system_message(*, workspace_path: str) -> JSONDict:
    payload: _WorkspaceContextFields = {
        "workspace_path": str(workspace_path).strip(),
    }
    return build_internal_system_message(
        message_type=AGENT_WORKSPACE_CONTEXT_MESSAGE_TYPE,
        content=build_injected_prompt_xml(
            xml_tag=WORKSPACE_CONTEXT_TAG,
            content=serialize_json_compact_stable_strict(
                filter_json_mapping_strict(
                    payload,
                    error_message="Injected prompt payload must be JSON-compatible.",
                ),
                ensure_ascii=False,
            ),
        ),
    )


def build_files_path_hints_system_message(*, workspace_path: str) -> JSONDict:
    payload: _PathHintsFields = {
        "workspace_path": str(workspace_path).strip(),
        "warning": get_text_prompt_v1("agent.path_hints.warning.v1"),
    }
    return build_internal_system_message(
        message_type=AGENT_PATH_HINTS_MESSAGE_TYPE,
        content=build_injected_prompt_xml(
            xml_tag=PATH_HINTS_TAG,
            content=serialize_json_compact_stable_strict(
                filter_json_mapping_strict(
                    payload,
                    error_message="Injected prompt payload must be JSON-compatible.",
                ),
                ensure_ascii=False,
            ),
        ),
    )


def build_todo_state_system_message(todo_state: JSONDict | None) -> JSONDict:
    payload = normalize_todo_state_for_prompt_injection(todo_state)
    return build_internal_system_message(
        message_type=AGENT_TODO_STATE_MESSAGE_TYPE,
        content=build_injected_prompt_xml(
            xml_tag=TODO_STATE_TAG,
            content=serialize_json_compact_stable_strict(
                filter_json_mapping_strict(
                    payload,
                    error_message="Injected prompt payload must be JSON-compatible.",
                ),
                ensure_ascii=False,
            ),
        ),
    )


def build_subagent_state_system_message(subagent_summaries: list[JSONDict]) -> JSONDict:
    normalized_subagents: list[_SubagentSummaryFields] = []
    running_subagents = 0
    for summary in subagent_summaries:
        if not isinstance(summary, dict):
            continue
        subagent_id = str(summary.get("subagent_id") or "").strip()
        status = str(summary.get("status") or "").strip()
        if not subagent_id or not status:
            continue
        if status == SUBAGENT_STATUS_RUNNING:
            running_subagents += 1
        normalized_subagents.append(
            {
                "subagent_id": subagent_id,
                "status": status,
                "mode": summary.get("mode"),
                "display_name": summary.get("display_name"),
                "result_text": summary.get("result_text"),
                "error_message": summary.get("error_message"),
                "token_usage": summary.get("token_usage"),
            },
        )
    unresolved_subagent_ids = [
        str(entry.get("subagent_id") or "")
        for entry in normalized_subagents
        if str(entry.get("status") or "").strip() == SUBAGENT_STATUS_RUNNING
    ]
    payload: _SubagentStateFields = {
        "instruction": get_text_prompt_v1("agent.subagent_state.instruction.v1"),
        "required_next_actions": [
            get_text_prompt_v1("agent.subagent_state.required_action.wait_or_get.v1"),
            get_text_prompt_v1("agent.subagent_state.required_action.cancel_or_ignore.v1"),
        ],
        "running_subagents": running_subagents,
        "total_subagents": len(normalized_subagents),
        "unresolved_subagent_ids": unresolved_subagent_ids,
        "subagents": normalized_subagents,
    }
    return build_internal_system_message(
        message_type=AGENT_SUBAGENT_STATE_MESSAGE_TYPE,
        content=build_injected_prompt_xml(
            xml_tag=SUBAGENT_STATE_TAG,
            content=serialize_json_compact_stable_strict(
                filter_json_mapping_strict(
                    payload,
                    error_message="Injected prompt payload must be JSON-compatible.",
                ),
                ensure_ascii=False,
            ),
        ),
    )


def build_tool_context_system_message(tool_context_json: str) -> JSONDict:
    return build_internal_system_message(
        message_type=AGENT_TOOL_CONTEXT_MESSAGE_TYPE,
        content=build_injected_prompt_xml(
            xml_tag=TOOL_CONTEXT_TAG,
            content=tool_context_json.strip(),
        ),
    )


def build_capability_policies_system_message(policy_text: str) -> JSONDict:
    return build_internal_system_message(
        message_type=AGENT_CAPABILITY_POLICIES_MESSAGE_TYPE,
        content=build_injected_prompt_xml(
            xml_tag=CAPABILITY_POLICIES_TAG,
            content=policy_text.strip(),
        ),
    )


def build_tool_hints_system_message(tool_hints_text: str) -> JSONDict:
    return build_internal_system_message(
        message_type=AGENT_TOOL_HINTS_MESSAGE_TYPE,
        content=build_injected_prompt_xml(
            xml_tag=TOOL_HINTS_TAG,
            content=tool_hints_text.strip(),
        ),
    )
