"""SoAI - API routes for model parameter and alias mutations [backend/features/api/routes/models/model_mutation_routes.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from fastapi import APIRouter, Depends, Request, params
from starlette.responses import Response

from core.errors.exceptions import ValidationError
from core.events.types_models_model_commands import (
    DeleteModelAliasCommand,
    DeleteModelParametersCommand,
    ResetModelOpenAICapabilityOverridesCommand,
    UpdateModelAliasCommand,
    UpdateModelEnabledCommand,
    UpdateModelOpenAICapabilityOverrideCommand,
    UpdateModelParametersCommand,
)
from core.models.universal_id import is_universal_id
from features.api.runtime.context import ApiContext, resolve_api_context
from features.api.schemas.models import (
    ModelAliasUpdate,
    ModelEnabledUpdate,
    ModelOpenAICapabilityOverrideUpdate,
    ModelParametersResetRequest,
    ModelParametersUpdate,
)

__all__ = ("register_model_mutation_routes",)


def register_model_mutation_routes(
    router: APIRouter,
    *,
    model_admin_restart_deps: tuple[params.Depends, ...],
) -> None:
    def _require_universal_id(universal_id: str) -> str:
        candidate = universal_id.strip() if isinstance(universal_id, str) else ""
        if not candidate or not is_universal_id(candidate):
            raise ValidationError("Model mutation requires a SoAI universal_id")
        return candidate

    @router.patch("/{universal_id}/parameters", dependencies=model_admin_restart_deps)
    async def model_update_parameters(
        request: Request,
        universal_id: str,
        payload: ModelParametersUpdate,
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> Response:
        universal_id = _require_universal_id(universal_id)
        return await api_context.dependencies.command_dispatcher.execute_model_mutation_command(
            request,
            validator=lambda: api_context.dependencies.model_parameter_service.model_validate_parameters(
                universal_id,
                payload.parameters,
            ),
            command_class=UpdateModelParametersCommand,
            audit_action="UPDATE_MODEL_PARAMETERS",
            audit_target=universal_id,
            audit_details={"keys_updated": list(payload.parameters.keys())},
            dispatch_fields={
                "universal_id": universal_id,
                "parameters": payload.parameters,
            },
            success_status=202,
        )

    @router.delete("/{universal_id}/parameters", dependencies=model_admin_restart_deps)
    async def model_delete_parameters(
        request: Request,
        universal_id: str,
        payload: ModelParametersResetRequest,
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> Response:
        universal_id = _require_universal_id(universal_id)
        return await api_context.dependencies.command_dispatcher.execute_model_mutation_command(
            request,
            validator=lambda: api_context.dependencies.model_parameter_service.model_validate_parameter_keys_exist(
                universal_id,
                payload.keys,
            ),
            command_class=DeleteModelParametersCommand,
            audit_action="RESET_MODEL_PARAMETERS",
            audit_target=universal_id,
            audit_details={"keys_reset": payload.keys},
            dispatch_fields={"universal_id": universal_id, "keys": payload.keys},
            success_status=202,
        )

    @router.patch("/{universal_id}/alias", dependencies=model_admin_restart_deps)
    async def model_update_alias(
        request: Request,
        universal_id: str,
        payload: ModelAliasUpdate,
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> Response:
        universal_id = _require_universal_id(universal_id)
        return await api_context.dependencies.command_dispatcher.dispatch_and_respond(
            request,
            UpdateModelAliasCommand,
            "final",
            "UPDATE_MODEL_ALIAS",
            universal_id,
            audit_details={"new_display_name": payload.display_name},
            command_fields={
                "universal_id": universal_id,
                "display_name": payload.display_name,
                "description": payload.description,
            },
        )

    @router.delete("/{universal_id}/alias", dependencies=model_admin_restart_deps)
    async def model_delete_alias(
        request: Request,
        universal_id: str,
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> Response:
        universal_id = _require_universal_id(universal_id)
        return await api_context.dependencies.command_dispatcher.dispatch_and_respond(
            request,
            DeleteModelAliasCommand,
            "final",
            "DELETE_MODEL_ALIAS",
            universal_id,
            command_fields={"universal_id": universal_id},
        )

    @router.patch("/{universal_id}/enabled", dependencies=model_admin_restart_deps)
    async def model_set_enabled(
        request: Request,
        universal_id: str,
        payload: ModelEnabledUpdate,
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> Response:
        universal_id = _require_universal_id(universal_id)
        return await api_context.dependencies.command_dispatcher.execute_model_mutation_command(
            request,
            validator=None,
            command_class=UpdateModelEnabledCommand,
            audit_action="UPDATE_MODEL_ENABLED",
            audit_target=universal_id,
            audit_details={"enabled": payload.enabled},
            dispatch_fields={"universal_id": universal_id, "enabled": payload.enabled},
            success_status=202,
        )

    @router.patch("/{universal_id}/capabilities/openai", dependencies=model_admin_restart_deps)
    async def model_update_openai_capabilities(
        request: Request,
        universal_id: str,
        payload: ModelOpenAICapabilityOverrideUpdate,
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> Response:
        universal_id = _require_universal_id(universal_id)
        return await api_context.dependencies.command_dispatcher.execute_model_mutation_command(
            request,
            validator=None,
            command_class=UpdateModelOpenAICapabilityOverrideCommand,
            audit_action="UPDATE_MODEL_OPENAI_CAPABILITIES",
            audit_target=universal_id,
            audit_details={
                "category": payload.category,
                "token": payload.token,
                "enabled": payload.enabled,
            },
            dispatch_fields={
                "universal_id": universal_id,
                "category": payload.category,
                "token": payload.token,
                "enabled": payload.enabled,
            },
            success_status=202,
        )

    @router.delete("/{universal_id}/capabilities/openai", dependencies=model_admin_restart_deps)
    async def model_reset_openai_capabilities(
        request: Request,
        universal_id: str,
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> Response:
        universal_id = _require_universal_id(universal_id)
        return await api_context.dependencies.command_dispatcher.execute_model_mutation_command(
            request,
            validator=None,
            command_class=ResetModelOpenAICapabilityOverridesCommand,
            audit_action="RESET_MODEL_OPENAI_CAPABILITIES",
            audit_target=universal_id,
            audit_details={},
            dispatch_fields={"universal_id": universal_id},
            success_status=202,
        )
