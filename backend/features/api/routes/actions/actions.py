"""SoAI - Plugin action and update API routes [backend/features/api/routes/actions/actions.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import Depends, Request
from fastapi.responses import JSONResponse
from starlette.responses import Response

from core.events.types_base import Event
from core.events.types_plugins import (
    RequestPluginDisableCommand,
    RequestPluginEnableCommand,
    RequestPluginStopAndWaitCommand,
    StopAllPluginsCommand,
    UpdateAllPluginBackendsCommand,
)
from core.models.discovery_trigger import publish_model_discovery_request
from core.runtime.network_policy import OfflineModeError
from core.state.access import AccessAction
from features.api.middleware.acl_enforcement import require_actions
from features.api.runtime.access_dependencies import (
    require_action_dependencies,
    restart_protected_dependencies,
)
from features.api.runtime.audit import log_audit_event
from features.api.runtime.context import ApiContext, resolve_api_context
from features.api.runtime.errors import raise_offline_mode
from features.api.runtime.plugin_compatibility import (
    ensure_plugin_compatible_or_raise,
    get_validated_plugin_name,
)
from features.api.runtime.response_timeout import require_response_timeout_value
from features.api.runtime.restart import check_restart_status_allow_backend

if TYPE_CHECKING:
    from core.types.json import JSONValue
    from features.api.runtime.container.api_routers import ApiRouters

__all__ = ("register_routes",)


async def _handle_plugin_state_change(
    request: Request,
    plugin_name: str,
    command_class: type[Event],
    audit_action: str,
    api_context: ApiContext,
    **command_fields: JSONValue,
) -> Response:
    plugin_manager_instance = api_context.dependencies.plugin_manager
    await ensure_plugin_compatible_or_raise(request, plugin_manager_instance, plugin_name)
    display_name = await plugin_manager_instance.get_plugin_display_name(plugin_name)
    dispatch_fields: dict[str, JSONValue] = dict(command_fields)
    response_timeout_value: float | None = None
    if "response_timeout" in dispatch_fields:
        response_timeout_raw = dispatch_fields.pop("response_timeout")
        response_timeout_value = require_response_timeout_value(
            request,
            response_timeout_raw,
            message="response_timeout must be numeric.",
        )
    audit_details: dict[str, JSONValue] = {
        "display_name": display_name,
        **dispatch_fields,
    }
    return await api_context.dependencies.command_dispatcher.dispatch_and_respond(
        request,
        command_class,
        "accepted",
        audit_action,
        plugin_name,
        audit_details,
        {"plugin_name": plugin_name, **dispatch_fields},
        response_timeout=response_timeout_value,
    )


def register_routes(routers: ApiRouters) -> None:
    @routers.actions.post(
        "/discover-models",
        status_code=202,
        dependencies=restart_protected_dependencies(AccessAction.PLUGIN_ADMIN),
    )
    async def discover_models(
        request: Request,
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> dict[str, str]:
        log_audit_event(request, "TRIGGER_MODEL_DISCOVERY", "all")
        await publish_model_discovery_request(
            api_context.dependencies.event_bus,
            context=request.state.context,
        )
        return {"message": "Model discovery command issued."}

    @routers.actions.post(
        "/stop-all-plugins",
        status_code=202,
        dependencies=restart_protected_dependencies(AccessAction.RECOVERY_ADMIN),
    )
    async def stop_all_plugins(
        request: Request,
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> dict[str, str]:
        log_audit_event(request, "STOP_ALL_PLUGINS", "all")
        await api_context.dependencies.event_bus.publish(
            StopAllPluginsCommand(context=request.state.context),
        )
        return {"message": "Command to stop all plugins has been issued."}

    @routers.actions.post(
        "/plugins/{plugin_name}/disable",
        status_code=202,
        dependencies=restart_protected_dependencies(AccessAction.PLUGIN_ADMIN),
        response_model=None,
    )
    async def disable_plugin(
        request: Request,
        api_context: ApiContext = Depends(resolve_api_context),
        normalized_name: str = Depends(get_validated_plugin_name),
    ) -> Response:
        return await _handle_plugin_state_change(
            request,
            normalized_name,
            RequestPluginDisableCommand,
            "DISABLE_PLUGIN",
            api_context,
        )

    @routers.actions.post(
        "/plugins/{plugin_name}/enable",
        status_code=202,
        dependencies=restart_protected_dependencies(AccessAction.PLUGIN_ADMIN),
        response_model=None,
    )
    async def enable_plugin(
        request: Request,
        api_context: ApiContext = Depends(resolve_api_context),
        normalized_name: str = Depends(get_validated_plugin_name),
    ) -> Response:
        return await _handle_plugin_state_change(
            request,
            normalized_name,
            RequestPluginEnableCommand,
            "ENABLE_PLUGIN",
            api_context,
        )

    @routers.actions.post(
        "/plugins/{plugin_name}/stop",
        status_code=202,
        dependencies=restart_protected_dependencies(AccessAction.RECOVERY_ADMIN),
        response_model=None,
    )
    async def stop_plugin(
        request: Request,
        api_context: ApiContext = Depends(resolve_api_context),
        normalized_name: str = Depends(get_validated_plugin_name),
    ) -> Response:
        display_name = await api_context.dependencies.plugin_manager.get_plugin_display_name(
            normalized_name,
        )
        return await api_context.dependencies.command_dispatcher.dispatch_and_respond(
            request,
            RequestPluginStopAndWaitCommand,
            "accepted",
            "STOP_PLUGIN",
            normalized_name,
            {"display_name": display_name},
            {"plugin_name": normalized_name},
        )

    @routers.actions.post(
        "/plugins/check-for-updates",
        dependencies=require_action_dependencies(AccessAction.PLUGIN_ADMIN),
    )
    async def check_for_backend_updates(
        request: Request,
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> JSONResponse:
        try:
            updates = await api_context.dependencies.plugin_manager.check_for_backend_updates()
            return JSONResponse(content=updates)
        except OfflineModeError as exception:
            raise_offline_mode(request, str(exception))

    @routers.actions.post(
        "/plugins/update-all-backends",
        dependencies=[
            Depends(check_restart_status_allow_backend),
            Depends(require_actions(AccessAction.PLUGIN_ADMIN)),
        ],
        response_model=None,
    )
    async def update_all_plugin_backends(
        request: Request,
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> Response:
        return await api_context.dependencies.command_dispatcher.dispatch_and_respond(
            request,
            UpdateAllPluginBackendsCommand,
            "accepted",
            "UPDATE_ALL_PLUGIN_BACKENDS",
            "all",
        )
