"""SoAI - Plugin backend installation routes [backend/features/api/routes/plugins/plugin_backend_routes.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import Body, Depends, Query, Request
from fastapi.responses import JSONResponse
from starlette.responses import Response

from core.events.types_plugins import (
    InstallPluginBackendCommand,
    RemovePluginBackendCommand,
    UpdatePluginBackendCommand,
)
from core.mutations.identifiers import require_mutation_request_id
from core.plugins.errors import PluginCapabilityError
from core.state.access import AccessAction
from core.types.json import JSONDict, JSONValue
from core.types.json_value import coerce_json_dict_or_empty
from features.api.middleware.acl_enforcement import require_actions
from features.api.routes.configs.gpu_binding_validation import (
    validate_gpu_binding_backend_variant_selection,
)
from features.api.runtime.container.api_routers import ApiRouters
from features.api.runtime.context import ApiContext, resolve_api_context
from features.api.runtime.errors import raise_action_not_supported
from features.api.runtime.plugin_compatibility import ensure_plugin_compatible_or_raise
from features.api.runtime.plugin_mutation_admission import (
    build_backend_mutation_admission,
    resolve_backend_mutation_operation,
)
from features.api.runtime.restart import check_restart_status_allow_backend
from features.api.schemas.plugins import (
    InstallPluginBackendRequest,
    RemovePluginBackendRequest,
    UpdatePluginBackendRequest,
)

__all__ = ("register_routes",)

if TYPE_CHECKING:
    from features.api.runtime.plugin_mutation_admission import BackendMutationType


async def _dispatch_backend_action(
    request: Request,
    plugin_name: str,
    command_class: type[
        InstallPluginBackendCommand | RemovePluginBackendCommand | UpdatePluginBackendCommand
    ],
    audit_action: str,
    api_context: ApiContext,
    *,
    task_id: str,
    **command_fields: JSONValue,
) -> Response:
    plugin_manager_instance = api_context.dependencies.plugin_manager
    operation_type: BackendMutationType = resolve_backend_mutation_operation(command_class)
    await ensure_plugin_compatible_or_raise(request, plugin_manager_instance, plugin_name)
    try:
        action_label = audit_action.replace("_", " ").title()
        await plugin_manager_instance.ensure_plugin_capability(
            plugin_name,
            "SUPPORTS_BACKEND_INSTALLATION",
            action_label,
        )
        await plugin_manager_instance.ensure_system_capabilities(
            plugin_name,
            action_label,
            action_key=operation_type,
        )
    except PluginCapabilityError as exception:
        raise_action_not_supported(request, str(exception))
    request.state.context.task_id = task_id
    display_name = await plugin_manager_instance.get_plugin_display_name(plugin_name)
    audit_details: JSONDict = {"display_name": display_name}
    for detail_key, detail_value in command_fields.items():
        if detail_value is not None:
            audit_details[str(detail_key)] = detail_value
    mutation_admission = build_backend_mutation_admission(
        request_id=task_id,
        plugin_name=plugin_name,
        operation_type=operation_type,
        command_fields=command_fields,
    )
    return await api_context.dependencies.command_dispatcher.dispatch_and_respond(
        request=request,
        command_class=command_class,
        response_type="accepted",
        audit_action=audit_action,
        audit_target=plugin_name,
        audit_details=audit_details,
        command_fields={"plugin_name": plugin_name, **command_fields},
        mutation_admission=mutation_admission,
    )


async def _snapshot_backend_variant_id(
    api_context: ApiContext,
    plugin_name: str,
    body: JSONDict,
) -> str:
    return await api_context.dependencies.plugin_manager.snapshot_backend_variant_selection(
        plugin_name,
        body.get("backend_variant_id"),
        has_requested_variant_id="backend_variant_id" in body,
    )


def register_routes(routers: ApiRouters) -> None:
    @routers.plugins.post(
        "/{plugin_name}/install-backend",
        dependencies=[
            Depends(check_restart_status_allow_backend),
            Depends(require_actions(AccessAction.PLUGIN_ADMIN)),
        ],
    )
    async def install_backend(
        request: Request,
        plugin_name: str,
        payload: InstallPluginBackendRequest,
        task_id: str = Query(description="Client-provided durable mutation request ID."),
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> Response:
        validated_task_id = require_mutation_request_id(task_id)
        request_body = payload.model_dump(exclude_none=True)
        backend_variant_id = await _snapshot_backend_variant_id(
            api_context,
            plugin_name,
            request_body,
        )
        return await _dispatch_backend_action(
            request,
            plugin_name,
            InstallPluginBackendCommand,
            "INSTALL_PLUGIN_BACKEND",
            api_context,
            task_id=validated_task_id,
            backend_variant_id=backend_variant_id,
        )

    @routers.plugins.post(
        "/{plugin_name}/remove-backend",
        dependencies=[
            Depends(check_restart_status_allow_backend),
            Depends(require_actions(AccessAction.PLUGIN_ADMIN)),
        ],
    )
    async def remove_backend(
        request: Request,
        plugin_name: str,
        payload: RemovePluginBackendRequest,
        task_id: str = Query(description="Client-provided durable mutation request ID."),
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> Response:
        validated_task_id = require_mutation_request_id(task_id)
        return await _dispatch_backend_action(
            request,
            plugin_name,
            RemovePluginBackendCommand,
            "REMOVE_PLUGIN_BACKEND",
            api_context,
            task_id=validated_task_id,
            delete_models=payload.delete_models,
        )

    @routers.plugins.post(
        "/{plugin_name}/update-backend",
        dependencies=[
            Depends(check_restart_status_allow_backend),
            Depends(require_actions(AccessAction.PLUGIN_ADMIN)),
        ],
    )
    async def update_backend(
        request: Request,
        plugin_name: str,
        payload: UpdatePluginBackendRequest,
        task_id: str = Query(description="Client-provided durable mutation request ID."),
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> Response:
        validated_task_id = require_mutation_request_id(task_id)
        request_body = payload.model_dump(exclude_none=True)
        backend_variant_id = await _snapshot_backend_variant_id(
            api_context,
            plugin_name,
            request_body,
        )
        return await _dispatch_backend_action(
            request,
            plugin_name,
            UpdatePluginBackendCommand,
            "UPDATE_PLUGIN_BACKEND",
            api_context,
            task_id=validated_task_id,
            backend_variant_id=backend_variant_id,
        )

    @routers.plugins.get(
        "/{plugin_name}/backend-variants",
        dependencies=[Depends(require_actions(AccessAction.PLUGIN_ADMIN))],
    )
    async def get_backend_variants(
        request: Request,
        plugin_name: str,
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> JSONResponse:
        plugin_manager_instance = api_context.dependencies.plugin_manager
        await ensure_plugin_compatible_or_raise(request, plugin_manager_instance, plugin_name)
        try:
            await plugin_manager_instance.ensure_plugin_capability(
                plugin_name,
                "SUPPORTS_BACKEND_INSTALLATION",
                "Backend variants",
            )
        except PluginCapabilityError as exception:
            raise_action_not_supported(request, str(exception))
        payload = await plugin_manager_instance.get_backend_variants(plugin_name)
        return JSONResponse(content=payload)

    @routers.plugins.put(
        "/{plugin_name}/backend-variant-selection",
        dependencies=[
            Depends(check_restart_status_allow_backend),
            Depends(require_actions(AccessAction.PLUGIN_ADMIN)),
        ],
    )
    async def save_backend_variant_selection(
        request: Request,
        plugin_name: str,
        body: JSONDict = Body(default_factory=dict[str, JSONValue]),
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> JSONResponse:
        plugin_manager_instance = api_context.dependencies.plugin_manager
        await ensure_plugin_compatible_or_raise(request, plugin_manager_instance, plugin_name)
        try:
            await plugin_manager_instance.ensure_plugin_capability(
                plugin_name,
                "SUPPORTS_BACKEND_INSTALLATION",
                "Backend variants",
            )
        except PluginCapabilityError as exception:
            raise_action_not_supported(request, str(exception))
        request_body = coerce_json_dict_or_empty(body)
        await validate_gpu_binding_backend_variant_selection(
            request,
            plugin_name,
            request_body.get("backend_variant_id"),
            api_context,
        )
        payload = await plugin_manager_instance.save_backend_variant_selection(
            plugin_name,
            request_body.get("backend_variant_id"),
        )
        return JSONResponse(content=payload)
