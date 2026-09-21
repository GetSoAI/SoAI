"""SoAI - Subagent settings resolution [backend/features/agent/subagents/settings.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.agent.settings_types import AgentSettings
from core.errors.exceptions import ValidationError
from core.model_settings.request_projection import build_chat_execution_openai_request
from core.runtime.request_context import RequestContext
from core.types.json_value import copy_json_dict
from features.agent.session.runtime_resolution import (
    resolve_required_agent_runtime_settings,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from features.api.runtime.container.types import ApiDependencies

__all__ = ("resolve_subagent_settings",)


async def resolve_subagent_settings(
    api_dependencies: ApiDependencies,
    *,
    parent_context: RequestContext,
    mode: str,
    model: str | None,
    workspace_path: str | None,
    max_iterations: int | None,
) -> tuple[str, AgentSettings, JSONDict]:
    requested_model = str(model or parent_context.agent_requested_model or "").strip()
    if not requested_model:
        raise ValidationError("Subagents require a resolved model.")
    conversation_input_id = str(parent_context.conversation_input_id or "").strip()
    if not conversation_input_id:
        raise ValidationError("Subagents require a conversation input settings snapshot.")
    model_settings = copy_json_dict(
        await api_dependencies.database_input_execution.get_input_execution_settings(
            input_id=conversation_input_id,
        ),
    )
    inherited_agent_settings = model_settings.get("agent")
    if inherited_agent_settings is None:
        agent_settings_payload: JSONDict = {}
    elif isinstance(inherited_agent_settings, dict):
        agent_settings_payload = copy_json_dict(inherited_agent_settings)
    else:
        raise ValidationError("Subagent parent agent settings must be an object.")
    agent_settings_payload["mode"] = mode
    if max_iterations is not None:
        agent_settings_payload["max_iterations"] = max_iterations
    if workspace_path is not None and workspace_path.strip():
        agent_settings_payload["workspace_path"] = workspace_path.strip()
    model_settings["model"] = requested_model
    model_settings["agent"] = agent_settings_payload
    resolution = await resolve_required_agent_runtime_settings(
        api_dependencies=api_dependencies,
        user_id=parent_context.user_id,
        model_settings=model_settings,
        request_model=requested_model,
        require_context_window=False,
    )
    normalized_requested_model = resolution.requested_model
    if not isinstance(normalized_requested_model, str) or not normalized_requested_model.strip():
        raise ValidationError("Subagents require a resolved model.")
    execution_request = build_chat_execution_openai_request(model_settings)
    execution_request["model"] = normalized_requested_model
    return (normalized_requested_model, resolution.settings, execution_request)
