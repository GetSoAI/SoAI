"""SoAI - Shared agent runtime settings resolution [backend/features/agent/session/runtime_resolution.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.agent.settings_types import AgentSettings
from core.errors.exceptions import ValidationError
from core.model_settings.normalization import normalize_comparison_models
from core.model_settings.request_projection import read_execution_context_window_override
from core.validation.strings import coerce_optional_trimmed_str
from core.workspaces.user_workspace_path import resolve_user_record_workspace_access
from features.agent.runtime.model_tool_calling import model_supports_vision_input
from features.agent.session.model_id_reconciliation import reconcile_agent_request_model
from features.agent.session.service import resolve_agent_settings
from features.openai.model_runtime_profile_resolution import (
    resolve_openai_model_runtime_profile,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from features.api.runtime.container.types import ApiDependencies

__all__ = (
    "AgentRuntimeSettingsResolution",
    "resolve_agent_runtime_settings",
    "resolve_required_agent_runtime_settings",
)


@dataclass(frozen=True, slots=True)
class AgentRuntimeSettingsResolution:
    requested_model: str | None
    context_window_tokens: int | None
    context_window_unverified: bool
    settings: AgentSettings


async def resolve_agent_runtime_settings(
    api_dependencies: ApiDependencies,
    *,
    user_id: int,
    model_settings: JSONDict,
    request_model: str | None,
) -> AgentRuntimeSettingsResolution:
    settings_model = coerce_optional_trimmed_str(model_settings.get("model"))
    comparison_models = normalize_comparison_models(
        primary_model=settings_model,
        raw_value=model_settings.get("comparison_models"),
    )
    requested_model = await reconcile_agent_request_model(
        request_model=request_model,
        conversation_model=settings_model,
        comparison_models=tuple(comparison_models),
        model_resolution_service=api_dependencies.model_resolution_service,
        virtual_model_get=api_dependencies.model_virtual_model_service.virtual_model_get,
    )
    context_window_tokens: int | None = None
    context_window_unverified = True
    token_estimation_profile = api_dependencies.prompt_token_counter.default_profile()
    if requested_model is not None:
        runtime_profile = await resolve_openai_model_runtime_profile(
            config=api_dependencies.config,
            model_name=requested_model,
            model_resolution_service=api_dependencies.model_resolution_service,
            model_information_service=api_dependencies.model_information_service,
            provider_get_external=api_dependencies.model_provider_coordinator.provider_get_external,
            virtual_model_get=api_dependencies.model_virtual_model_service.virtual_model_get,
        )
        context_window_tokens = runtime_profile.context_window_tokens
        context_window_unverified = runtime_profile.context_window_unverified
        token_estimation_profile = runtime_profile.token_estimation_profile
    context_window_override = read_execution_context_window_override(model_settings)
    if context_window_override is not None:
        context_window_tokens = context_window_override
        context_window_unverified = False
    user_record = await api_dependencies.database_users.get_account_by_id(user_id)
    if not isinstance(user_record, dict):
        raise ValidationError("Authenticated user is unavailable.")
    user_workspace_value = user_record.get("workspace_path")
    if not isinstance(user_workspace_value, str) or not user_workspace_value.strip():
        raise ValidationError("Authenticated user is missing workspace_path.")
    resolve_user_record_workspace_access(
        api_dependencies.files,
        user_record,
    )
    tool_result_image_relay_enabled = False
    if requested_model is not None:
        tool_result_image_relay_enabled = await model_supports_vision_input(
            api_dependencies,
            requested_model,
        )
    settings = resolve_agent_settings(
        config=api_dependencies.config,
        files=api_dependencies.files,
        user_workspace_path=user_workspace_value,
        model_settings=model_settings,
        context_window_tokens=context_window_tokens,
        context_window_unverified=context_window_unverified,
        token_estimation_profile=token_estimation_profile,
        tool_result_image_relay_enabled=tool_result_image_relay_enabled,
    )
    return AgentRuntimeSettingsResolution(
        requested_model=requested_model,
        context_window_tokens=context_window_tokens,
        context_window_unverified=context_window_unverified,
        settings=settings,
    )


async def resolve_required_agent_runtime_settings(
    api_dependencies: ApiDependencies,
    *,
    user_id: int,
    model_settings: JSONDict,
    request_model: str | None,
    require_context_window: bool,
) -> AgentRuntimeSettingsResolution:
    resolution = await resolve_agent_runtime_settings(
        api_dependencies,
        user_id=user_id,
        model_settings=model_settings,
        request_model=request_model,
    )
    requested_model = resolution.requested_model
    if not isinstance(requested_model, str) or not requested_model.strip():
        raise ValidationError("Agent runtime requires a resolved model.")
    if require_context_window:
        context_window_tokens = resolution.context_window_tokens
        if context_window_tokens is None or context_window_tokens <= 0:
            raise ValidationError("Agent runtime requires a resolved context window.")
    return resolution
