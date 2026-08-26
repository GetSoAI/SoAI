"""SoAI - Shared agent prompt-context injection [backend/features/agent/runtime/prompt_context.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from core.agent.prompt_injection_messages import (
    prune_injected_prompt_messages,
    rebuild_injected_prompt_messages,
)
from core.agent.prompt_injection_support import (
    build_files_path_hints_system_message,
    build_subagent_state_system_message,
    build_todo_state_system_message,
    build_workspace_context_system_message,
)
from core.agent_mode import is_agent_mode
from core.errors.exceptions import ValidationError
from features.agent.runtime.agents_prompts import (
    build_agents_message,
    discover_agents_files,
    read_agents_instructions,
)
from features.agent.runtime.mode_prompts import (
    build_mode_system_message,
    load_mode_template,
)

if TYPE_CHECKING:
    from core.agent.settings_types import AgentSettings
    from core.types.json import JSONDict

__all__ = ("inject_agent_prompt_context_messages",)


def inject_agent_prompt_context_messages(
    *,
    agent_settings: AgentSettings,
    todo_state: JSONDict | None,
    subagent_summaries: list[JSONDict],
    messages: list[JSONDict],
    tools_visible_to_model: bool,
) -> int:
    base_count = len(messages)
    if not is_agent_mode(agent_settings.mode):
        return base_count
    prune_injected_prompt_messages(messages)
    base_count = len(messages)
    template = load_mode_template(
        mode=agent_settings.mode,
        tools_visible_to_model=tools_visible_to_model,
    )
    mode_message = build_mode_system_message(template)
    workspace_path = agent_settings.workspace_path
    if not workspace_path.strip():
        raise ValidationError("workspace_path must be configured for agent mode.")
    if not os.path.isdir(workspace_path):
        raise ValidationError("workspace_path must be an existing directory for agent mode.")
    workspace_context_message = build_workspace_context_system_message(
        workspace_path=workspace_path,
    )
    path_hints_message = build_files_path_hints_system_message(
        workspace_path=workspace_path,
    )
    agents_message = None
    if agent_settings.mode != "chat" and tools_visible_to_model:
        instructions = read_agents_instructions(
            discover_agents_files(
                workspace_path=workspace_path,
            ),
            workspace_path=workspace_path,
        )
        if instructions is not None:
            agents_message = build_agents_message(instructions)
    rebuild_injected_prompt_messages(
        messages,
        mode_message=mode_message,
        todo_state_message=build_todo_state_system_message(todo_state),
        workspace_context_message=workspace_context_message,
        path_hints_message=path_hints_message,
        subagent_state_message=build_subagent_state_system_message(subagent_summaries),
        agents_message=agents_message,
    )
    return base_count
