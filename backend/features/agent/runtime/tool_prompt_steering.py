"""SoAI - Agent tool prompt steering application [backend/features/agent/runtime/tool_prompt_steering.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.agent.prompt_injection_messages import (
    upsert_agent_tool_prompt_messages,
)
from core.agent.prompt_injection_support import (
    build_capability_policies_system_message,
    build_tool_context_system_message,
    build_tool_hints_system_message,
)
from core.types.json import JSONDict
from features.agent.runtime.capability_policy_messages import (
    build_agent_capability_policies_text,
)
from features.agent.runtime.inline_attachment_detection import (
    build_inline_attachment_tool_hint,
)
from features.agent.runtime.tool_context_messages import (
    build_agent_tool_context_json,
    build_agent_tool_hints_text,
)
from features.agent.runtime.tool_context_profiles import (
    build_tool_payload_entries,
    collect_profiles_from_tool_payloads,
)

__all__ = ("apply_agent_tool_prompt_messages",)


def apply_agent_tool_prompt_messages(
    *,
    messages: list[JSONDict],
    agent_mode: str,
    tool_entries: dict[str, JSONDict],
    tool_names: list[str],
) -> None:
    tool_context_json = build_agent_tool_context_json(
        agent_mode=agent_mode,
        tool_names=tool_names,
        tool_entries=tool_entries,
    )
    tool_hints_text = build_agent_tool_hints_text(
        agent_mode=agent_mode,
        tool_names=tool_names,
        tool_entries=tool_entries,
    )
    inline_attachment_hint = build_inline_attachment_tool_hint(messages, tool_names)
    combined_tool_hints_text = "\n".join(
        line for line in (tool_hints_text, inline_attachment_hint) if line.strip()
    )
    tool_payloads = build_tool_payload_entries(tool_names=tool_names, tool_entries=tool_entries)
    capability_policies_text = build_agent_capability_policies_text(
        agent_mode=agent_mode,
        profiles=collect_profiles_from_tool_payloads(tool_payloads),
        tool_names=tool_names,
    )
    upsert_agent_tool_prompt_messages(
        messages,
        tool_context_message=(
            build_tool_context_system_message(tool_context_json)
            if tool_context_json.strip()
            else None
        ),
        capability_policies_message=(
            build_capability_policies_system_message(capability_policies_text)
            if capability_policies_text.strip()
            else None
        ),
        tool_hints_message=(
            build_tool_hints_system_message(combined_tool_hints_text)
            if combined_tool_hints_text.strip()
            else None
        ),
    )
