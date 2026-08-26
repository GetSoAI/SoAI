"""SoAI - Agent injected prompt slot registry [backend/core/agent/prompt_injection_slots.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

__all__ = (
    "AGENT_INSTRUCTIONS_PREFIXES",
    "CAPABILITY_POLICIES_TAG",
    "INJECTED_PROMPT_XML_TAGS",
    "MODE_TAG",
    "PATH_HINTS_TAG",
    "SUBAGENT_STATE_TAG",
    "TODO_STATE_TAG",
    "TOOL_CONTEXT_TAG",
    "TOOL_HINTS_TAG",
    "WORKSPACE_CONTEXT_TAG",
    "build_injected_prompt_xml",
)

MODE_TAG = "collaboration_mode"
TODO_STATE_TAG = "agent_todo_state"
WORKSPACE_CONTEXT_TAG = "agent_workspace_context"
PATH_HINTS_TAG = "agent_path_hints"
SUBAGENT_STATE_TAG = "agent_subagent_state"
TOOL_CONTEXT_TAG = "agent_tool_context"
CAPABILITY_POLICIES_TAG = "agent_capability_policies"
TOOL_HINTS_TAG = "agent_tool_hints"
AGENT_INSTRUCTIONS_PREFIXES = (
    "# SOAI.md instructions for ",
    "# AGENTS.md instructions for ",
)


INJECTED_PROMPT_XML_TAGS = (
    MODE_TAG,
    TODO_STATE_TAG,
    WORKSPACE_CONTEXT_TAG,
    PATH_HINTS_TAG,
    SUBAGENT_STATE_TAG,
    TOOL_CONTEXT_TAG,
    CAPABILITY_POLICIES_TAG,
    TOOL_HINTS_TAG,
)


def build_injected_prompt_xml(*, xml_tag: str, content: str) -> str:
    escaped_content = content.replace("</", "<\\/")
    return f"<{xml_tag}>{escaped_content}</{xml_tag}>"
