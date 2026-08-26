"""SoAI - Internal prompt message ownership metadata [backend/core/openai/internal_message_metadata.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exceptions import ValidationError
from core.types.json import JSONDict

__all__ = (
    "AGENT_CAPABILITY_POLICIES_MESSAGE_TYPE",
    "AGENT_INSTRUCTIONS_MESSAGE_TYPE",
    "AGENT_MODE_MESSAGE_TYPE",
    "AGENT_PATH_HINTS_MESSAGE_TYPE",
    "AGENT_SUBAGENT_STATE_MESSAGE_TYPE",
    "AGENT_TODO_STATE_MESSAGE_TYPE",
    "AGENT_TOOL_CONTEXT_MESSAGE_TYPE",
    "AGENT_TOOL_HINTS_MESSAGE_TYPE",
    "AGENT_WORKSPACE_CONTEXT_MESSAGE_TYPE",
    "INJECTED_AGENT_MESSAGE_TYPES",
    "INJECTED_SOAI_MESSAGE_TYPES",
    "SOAI_MESSAGE_TYPE_FIELD",
    "SOAI_PROMPT_PROJECTION_MESSAGE_TYPE",
    "SOAI_RUNTIME_CONTEXT_MESSAGE_TYPE",
    "build_internal_system_message",
    "has_internal_message_type",
)

SOAI_MESSAGE_TYPE_FIELD = "soai_message_type"
SOAI_PROMPT_PROJECTION_MESSAGE_TYPE = "soai_prompt_projection"
SOAI_RUNTIME_CONTEXT_MESSAGE_TYPE = "soai_runtime_context"
AGENT_MODE_MESSAGE_TYPE = "agent_mode"
AGENT_TODO_STATE_MESSAGE_TYPE = "agent_todo_state"
AGENT_WORKSPACE_CONTEXT_MESSAGE_TYPE = "agent_workspace_context"
AGENT_PATH_HINTS_MESSAGE_TYPE = "agent_path_hints"
AGENT_SUBAGENT_STATE_MESSAGE_TYPE = "agent_subagent_state"
AGENT_TOOL_CONTEXT_MESSAGE_TYPE = "agent_tool_context"
AGENT_CAPABILITY_POLICIES_MESSAGE_TYPE = "agent_capability_policies"
AGENT_TOOL_HINTS_MESSAGE_TYPE = "agent_tool_hints"
AGENT_INSTRUCTIONS_MESSAGE_TYPE = "agent_instructions"

INJECTED_SOAI_MESSAGE_TYPES = frozenset(
    (
        SOAI_PROMPT_PROJECTION_MESSAGE_TYPE,
        SOAI_RUNTIME_CONTEXT_MESSAGE_TYPE,
    )
)
INJECTED_AGENT_MESSAGE_TYPES = frozenset(
    (
        AGENT_MODE_MESSAGE_TYPE,
        AGENT_TODO_STATE_MESSAGE_TYPE,
        AGENT_WORKSPACE_CONTEXT_MESSAGE_TYPE,
        AGENT_PATH_HINTS_MESSAGE_TYPE,
        AGENT_SUBAGENT_STATE_MESSAGE_TYPE,
        AGENT_TOOL_CONTEXT_MESSAGE_TYPE,
        AGENT_CAPABILITY_POLICIES_MESSAGE_TYPE,
        AGENT_TOOL_HINTS_MESSAGE_TYPE,
        AGENT_INSTRUCTIONS_MESSAGE_TYPE,
    )
)


def build_internal_system_message(*, content: str, message_type: str) -> JSONDict:
    if (
        message_type not in INJECTED_SOAI_MESSAGE_TYPES
        and message_type not in INJECTED_AGENT_MESSAGE_TYPES
    ):
        raise ValidationError(f"Unsupported internal system message type: {message_type!r}.")
    return {
        "role": "system",
        "content": content,
        SOAI_MESSAGE_TYPE_FIELD: message_type,
    }


def has_internal_message_type(message: JSONDict, message_types: frozenset[str]) -> bool:
    return message.get(SOAI_MESSAGE_TYPE_FIELD) in message_types
