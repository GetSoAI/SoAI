"""SoAI - Plugin package endpoint handlers and registration [backend/features/api/routes/plugins/plugin_package_endpoints.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import JSONResponse
from starlette.responses import Response

from core.events.types_plugins import ClonePluginCommand, DeletePluginCommand
from core.plugins.compatibility_payload import compatibility_to_payload
from core.plugins.errors import PluginCapabilityError
from core.state.access import AccessAction
from features.api.runtime.access_dependencies import restart_protected_dependencies
from features.api.runtime.audit import log_audit_event
from features.api.runtime.context import ApiContext, resolve_api_context
from features.api.runtime.errors import (
    raise_action_not_supported,
    raise_bad_request,
    raise_not_found,
)
from features.api.runtime.plugin_compatibility import ensure_plugin_compatible_or_raise
from features.api.runtime.plugin_mutation_admission import build_clone_mutation_admission
from features.api.schemas.plugins import (
    ClonePluginRequest,
    PluginCompatibilityOverrideRequest,
)

__all__ = (
    "clone_plugin",
    "delete_plugin",
    "override_incompatibility",
    "register_endpoints",
)


async def delete_plugin(
    request: Request,
    plugin_name: str,
    delete_models: bool = False,
    api_context: ApiContext = Depends(resolve_api_context),
) -> Response:
    display_name = await api_context.dependencies.plugin_manager.get_plugin_display_name(
        plugin_name,
    )
    log_audit_event(request, "DELETE_PLUGIN", display_name, {"delete_models": delete_models})
    return await api_context.dependencies.command_dispatcher.dispatch_and_respond(
        request,
        DeletePluginCommand,
        "accepted",
        "DELETE_PLUGIN",
        display_name,
        {"plugin_name": plugin_name, "delete_models": delete_models},
        {
            "plugin_name": plugin_name,
            "delete_models": delete_models,
        },
    )


async def override_incompatibility(
    request: Request,
    plugin_name: str,
    payload: PluginCompatibilityOverrideRequest,
    api_context: ApiContext = Depends(resolve_api_context),
) -> Response:
    normalized_name = (
        api_context.dependencies.plugin_manager.normalize_plugin_name(plugin_name) or plugin_name
    )
    info = await api_context.dependencies.plugin_manager.set_incompatibility_override(
        normalized_name,
        bool(payload.override),
    )
    record = await api_context.dependencies.database_plugins.get_plugin_by_name(normalized_name)
    if not record:
        raise_not_found(request, f"Plugin '{normalized_name}' not found.")
    state_value = record.get("state")
    state = state_value if isinstance(state_value, str) else ""
    incompatibility = compatibility_to_payload(info)
    log_audit_event(
        request,
        "OVERRIDE_INCOMPATIBILITY",
        normalized_name,
        {"override": bool(payload.override), "state": state},
    )
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={"plugin": normalized_name, "state": state, "incompatibility": incompatibility},
    )


async def clone_plugin(
    request: Request,
    plugin_name: str,
    payload: ClonePluginRequest,
    api_context: ApiContext = Depends(resolve_api_context),
) -> Response:
    plugin_manager_instance = api_context.dependencies.plugin_manager
    await ensure_plugin_compatible_or_raise(request, plugin_manager_instance, plugin_name)
    source_instance = await plugin_manager_instance.get_plugin_instance(plugin_name)
    if source_instance is None:
        plugin_record = await api_context.dependencies.database_plugins.get_plugin_by_name(
            plugin_name,
        )
        if not plugin_record:
            raise_not_found(request, f"Plugin '{plugin_name}' not found.")
        if payload.field_overrides:
            raise_bad_request(
                request,
                "Field overrides are not available when plugin backend is not installed. Install the backend first or clone without field overrides.",
                error_type="field_overrides_unavailable",
            )
    try:
        await plugin_manager_instance.ensure_plugin_capability(
            plugin_name,
            "SUPPORTS_CLONING",
            "Cloning",
        )
        supports_cloning = True
    except PluginCapabilityError:
        supports_cloning = False
    if not supports_cloning:
        raise_action_not_supported(request, f"Plugin '{plugin_name}' does not support cloning.")
    request.state.context.task_id = payload.task_id
    display_name = await plugin_manager_instance.get_plugin_display_name(plugin_name)
    audit_details = {
        "display_name": display_name,
        "target_name": payload.target_name,
        "clone_models": payload.clone_models,
    }
    log_audit_event(request, "CLONE_PLUGIN", display_name, audit_details)
    mutation_admission = build_clone_mutation_admission(
        request_id=payload.task_id,
        source_plugin_name=plugin_name,
        target_plugin_name=payload.target_name,
        clone_models=payload.clone_models,
        field_overrides=payload.field_overrides,
        clonable_fields=source_instance.CLONABLE_FIELDS if source_instance is not None else (),
        fernets=api_context.dependencies.database_plugins.fernet,
        fingerprint_secret=api_context.dependencies.auth_config.primary_signing_secret or "",
        occupied_target_names=await plugin_manager_instance.snapshot_clone_target_occupancy(
            source_plugin_name=plugin_name,
            source_instance=source_instance,
            clone_models=payload.clone_models,
        ),
    )
    return await api_context.dependencies.command_dispatcher.dispatch_and_respond(
        request,
        ClonePluginCommand,
        "accepted",
        "CLONE_PLUGIN",
        display_name,
        audit_details,
        {
            "plugin_name": plugin_name,
            "target_name": payload.target_name,
            "clone_models": payload.clone_models,
            "field_overrides": payload.field_overrides,
        },
        mutation_admission=mutation_admission,
        sensitive_command_fields=frozenset(("field_overrides",)),
    )


def register_endpoints(router: APIRouter) -> None:
    router.delete(
        "/{plugin_name}",
        dependencies=restart_protected_dependencies(AccessAction.PLUGIN_ADMIN),
    )(delete_plugin)
    router.post(
        "/{plugin_name}/override-incompatibility",
        dependencies=restart_protected_dependencies(AccessAction.PLUGIN_ADMIN),
    )(override_incompatibility)
    router.post(
        "/{plugin_name}/clone",
        dependencies=restart_protected_dependencies(AccessAction.PLUGIN_ADMIN),
    )(clone_plugin)
