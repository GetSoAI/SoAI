"""SoAI - API routes for model management and configuration [backend/features/api/routes/models/models.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from starlette.responses import Response

from core.events.types_models_model_commands import (
    ModelDeleteCommand,
    ModelDownloadCommand,
)
from core.manual_install_paths import build_manual_install_path_payload
from core.models.source_identifier import require_source_model_id
from core.plugins.errors import PluginCapabilityError
from core.state.access import AccessAction
from core.state.state_names import ORCH_STATE_DISABLED
from core.types.json_value import filter_json_mapping_strict
from features.api.routes.models.model_mutation_routes import (
    register_model_mutation_routes,
)
from features.api.routes.models.model_snapshots import (
    get_model_details_snapshot,
    get_model_list_snapshot,
    get_model_parameters_snapshot,
)
from features.api.runtime import validation
from features.api.runtime.access_dependencies import (
    require_action_dependencies,
    restart_protected_dependencies,
)
from features.api.runtime.container.api_routers import ApiRouters
from features.api.runtime.context import ApiContext, resolve_api_context
from features.api.runtime.errors import (
    raise_action_not_supported,
    raise_bad_request,
    raise_invalid_request,
    raise_not_found,
)
from features.api.runtime.plugin_compatibility import ensure_plugin_compatible_or_raise
from features.api.schemas.models import (
    ModelDownloadRequest,
)

__all__ = (
    "ModelRouteRegistrar",
    "register_routes",
)


class ModelRouteRegistrar:
    def __init__(self, router: APIRouter) -> None:
        self.router = router

    def register(self) -> None:
        router = self.router
        model_read_deps = require_action_dependencies(AccessAction.MODEL_READ)
        model_admin_deps = require_action_dependencies(AccessAction.MODEL_ADMIN)
        model_admin_restart_deps = tuple(restart_protected_dependencies(AccessAction.MODEL_ADMIN))

        @router.get("", dependencies=model_read_deps)
        async def list_models(
            request: Request,
            api_context: ApiContext = Depends(resolve_api_context),
        ) -> Response:
            snapshot = await get_model_list_snapshot(request, api_context)
            return JSONResponse(content=snapshot)

        @router.get("/manual-install", dependencies=model_admin_deps)
        async def get_model_manual_install_path(
            api_context: ApiContext = Depends(resolve_api_context),
        ) -> Response:
            payload = build_manual_install_path_payload(
                config=api_context.dependencies.config,
                files=api_context.dependencies.files,
                resource_type="models",
                config_key="MODELS.MANAGER.PATHS.MODELS",
            )
            payload_json = filter_json_mapping_strict(
                payload,
                error_message="Model manual install payload must be JSON-compatible.",
            )
            return JSONResponse(content=payload_json)

        @router.get("/{universal_id}", dependencies=model_read_deps)
        async def get_model_details(
            request: Request,
            universal_id: str,
            api_context: ApiContext = Depends(resolve_api_context),
        ) -> Response:
            snapshot = await get_model_details_snapshot(
                request,
                api_context,
                universal_id,
            )
            return JSONResponse(content=snapshot)

        @router.post("/download", dependencies=model_admin_restart_deps)
        async def download_model(
            request: Request,
            payload: ModelDownloadRequest,
            api_context: ApiContext = Depends(resolve_api_context),
        ) -> Response:
            plugin_manager_instance = api_context.dependencies.plugin_manager
            plugin_name, model_id = (payload.plugin, payload.model_id)
            if payload.universal_id:
                model_info = (
                    await api_context.dependencies.model_information_service.model_get_info(
                        payload.universal_id,
                    )
                )
                if not model_info:
                    raise_not_found(
                        request,
                        f"Model with universal_id '{payload.universal_id}' not found.",
                    )
                plugin_name = validation.require_str_value(
                    request,
                    model_info["plugin"],
                    message="Model metadata field 'plugin' is invalid.",
                    allow_empty=False,
                )
                model_id = validation.require_str_value(
                    request,
                    model_info.get("model_id"),
                    message="Model metadata field 'model_id' is invalid.",
                    allow_empty=False,
                )
            if plugin_name is None:
                raise_invalid_request(request, "Plugin name is required.")
            if model_id is None:
                raise_invalid_request(request, "Model ID is required.")
            if not plugin_manager_instance.is_known_plugin(plugin_name):
                raise_not_found(request, f"Plugin '{plugin_name}' not found.")
            await ensure_plugin_compatible_or_raise(request, plugin_manager_instance, plugin_name)
            try:
                await plugin_manager_instance.ensure_plugin_capability(
                    plugin_name,
                    "SUPPORTS_MODEL_DOWNLOAD",
                    "Model Download",
                )
                await plugin_manager_instance.ensure_system_capabilities(
                    plugin_name,
                    "Model download",
                    action_key="download_model",
                )
            except PluginCapabilityError as exception:
                raise_action_not_supported(request, str(exception))
            display_name = await plugin_manager_instance.get_plugin_display_name(plugin_name)
            plugin_status = await api_context.dependencies.state_aggregator.get_plugin_status(
                plugin_name,
            )
            if plugin_status == ORCH_STATE_DISABLED:
                raise_bad_request(
                    request,
                    f"Cannot download model because plugin '{display_name}' is disabled.",
                    error_type="plugin_disabled",
                )
            return await api_context.dependencies.command_dispatcher.dispatch_and_respond(
                request,
                ModelDownloadCommand,
                "accepted",
                "DOWNLOAD_MODEL",
                model_id,
                {
                    "plugin": plugin_name,
                    "display_name": display_name,
                    "quantization": payload.quantization,
                },
                {
                    "plugin_name": plugin_name,
                    "model_id": model_id,
                    "quantization": payload.quantization,
                },
            )

        @router.delete("/{universal_id}", dependencies=model_admin_restart_deps)
        async def delete_model(
            request: Request,
            universal_id: str,
            api_context: ApiContext = Depends(resolve_api_context),
        ) -> Response:
            model_info = await api_context.dependencies.model_information_service.model_get_info(
                universal_id,
            )
            if not model_info:
                raise_not_found(request, f"Model '{universal_id}' not found.")
            plugin_name = validation.require_str_value(
                request,
                model_info["plugin"],
                message="Model metadata field 'plugin' is invalid.",
                allow_empty=False,
            )
            plugin_manager_instance = api_context.dependencies.plugin_manager
            if not plugin_manager_instance.is_known_plugin(plugin_name):
                raise_not_found(request, f"Plugin '{plugin_name}' not found.")
            await ensure_plugin_compatible_or_raise(
                request,
                plugin_manager_instance,
                plugin_name,
            )
            try:
                await plugin_manager_instance.ensure_plugin_capability(
                    plugin_name,
                    "SUPPORTS_MODEL_DELETION",
                    "Model Deletion",
                )
            except PluginCapabilityError as exception:
                raise_action_not_supported(request, str(exception))
            display_name = await plugin_manager_instance.get_plugin_display_name(plugin_name)
            return await api_context.dependencies.command_dispatcher.dispatch_and_respond(
                request,
                ModelDeleteCommand,
                "accepted",
                "DELETE_MODEL",
                display_name,
                {
                    "plugin": plugin_name,
                    "source_model_id": require_source_model_id(model_info),
                    "universal_id": universal_id,
                },
                {"universal_id": universal_id},
            )

        @router.get("/{universal_id}/parameters", dependencies=model_read_deps)
        async def get_model_parameters(
            universal_id: str,
            api_context: ApiContext = Depends(resolve_api_context),
        ) -> Response:
            snapshot = await get_model_parameters_snapshot(api_context, universal_id)
            return JSONResponse(content=snapshot)

        register_model_mutation_routes(
            router,
            model_admin_restart_deps=model_admin_restart_deps,
        )


def register_routes(routers: ApiRouters) -> None:
    ModelRouteRegistrar(routers.models).register()
