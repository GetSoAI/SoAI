"""SoAI - WebSocket plugin backend admin task commands [backend/features/api/routes/system/events/websocket_admin_task_commands_plugins.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from core.events.types_plugins import (
    InstallPluginBackendCommand,
    RemovePluginBackendCommand,
    UpdatePluginBackendCommand,
)
from features.api.routes.system.events.websocket_admin_plugin_action_support import (
    PluginAdminDispatchContext,
    dispatch_plugin_admin_command_accepted_for_context,
    resolve_run_id,
)
from features.api.routes.system.events.websocket_admin_task_commands_plugin_backend_common import (
    require_plugin_backend_admin_payload,
)
from features.api.runtime.container.enqueue_warning_tracker import EnqueueWarningTracker

if TYPE_CHECKING:
    from core.events.types_base import ReplyableCommand
    from core.plugins.protocols import PluginManagerProtocol
    from core.runtime.protocols import RequestProtocol
    from core.types.json import JSONDict
    from core.types.json_value import JSONValue
    from features.api.runtime.context import ApiContext
    from features.api.streaming.websocket import (
        WebsocketConnection,
        WebSocketRequestAdapter,
    )

__all__ = (
    "handle_plugin_backend_install",
    "handle_plugin_backend_remove",
    "handle_plugin_backend_update",
)


async def _dispatch_plugin_backend_command(
    *,
    data: JSONDict,
    connection: WebsocketConnection,
    request: RequestProtocol,
    request_adapter: WebSocketRequestAdapter,
    api_context: ApiContext,
    enqueue_warning_tracker: EnqueueWarningTracker,
    trace_id: str | None,
    action_label: str,
    capability_label: str,
    system_action_label: str,
    action_key: str,
    command_type: type[ReplyableCommand],
    audit_action: str,
    audit_details_builder: Callable[
        [PluginManagerProtocol, str, JSONDict],
        Awaitable[dict[str, JSONValue]],
    ],
    command_fields_builder: Callable[[str, JSONDict], dict[str, JSONValue]],
) -> None:
    _ = request_adapter
    run_id = resolve_run_id(data)
    payload = await require_plugin_backend_admin_payload(
        data,
        connection=connection,
        request=request,
        api_context=api_context,
        enqueue_warning_tracker=enqueue_warning_tracker,
        trace_id=trace_id,
        action_label=action_label,
        run_id=run_id,
        allowed_fields=(
            frozenset({"plugin_name", "delete_models"})
            if command_type is RemovePluginBackendCommand
            else frozenset({"plugin_name", "backend_variant_id"})
        ),
        require_delete_models=command_type is RemovePluginBackendCommand,
    )
    if payload is None:
        return
    body, plugin_name = payload
    plugin_manager_instance = api_context.dependencies.plugin_manager
    task_id_value = data.get("task_id")
    dispatch_context = PluginAdminDispatchContext(
        request,
        api_context,
        connection,
        enqueue_warning_tracker=enqueue_warning_tracker,
        trace_id=trace_id,
        run_id=run_id,
        plugin_name=plugin_name,
        task_id=task_id_value if isinstance(task_id_value, str) else None,
        requires_mutation_id=True,
    )
    command_fields = command_fields_builder(plugin_name, body)
    if command_type in {InstallPluginBackendCommand, UpdatePluginBackendCommand}:
        command_fields["backend_variant_id"] = (
            await plugin_manager_instance.snapshot_backend_variant_selection(
                plugin_name,
                body.get("backend_variant_id"),
                has_requested_variant_id="backend_variant_id" in body,
            )
        )
    audit_details = await audit_details_builder(
        plugin_manager_instance,
        plugin_name,
        body,
    )
    backend_variant_id = command_fields.get("backend_variant_id")
    if isinstance(backend_variant_id, str):
        audit_details["backend_variant_id"] = backend_variant_id
    await dispatch_plugin_admin_command_accepted_for_context(
        dispatch_context,
        capability_name="SUPPORTS_BACKEND_INSTALLATION",
        capability_label=capability_label,
        action_label=system_action_label,
        action_key=action_key,
        command_type=command_type,
        command_factory=command_type,
        audit_action=audit_action,
        audit_target=plugin_name,
        audit_details=audit_details,
        command_fields=command_fields,
    )


async def handle_plugin_backend_install(
    data: JSONDict,
    *,
    connection: WebsocketConnection,
    request: RequestProtocol,
    request_adapter: WebSocketRequestAdapter,
    api_context: ApiContext,
    enqueue_warning_tracker: EnqueueWarningTracker,
    trace_id: str | None,
) -> None:
    await _dispatch_plugin_backend_command(
        data=data,
        connection=connection,
        request=request,
        request_adapter=request_adapter,
        api_context=api_context,
        enqueue_warning_tracker=enqueue_warning_tracker,
        trace_id=trace_id,
        action_label="plugin_backend_install",
        capability_label="Install Backend",
        system_action_label="Install backend",
        action_key="install_backend",
        command_type=InstallPluginBackendCommand,
        audit_action="INSTALL_PLUGIN_BACKEND",
        audit_details_builder=_build_install_or_update_audit_details,
        command_fields_builder=_build_install_command_fields,
    )


async def handle_plugin_backend_remove(
    data: JSONDict,
    *,
    connection: WebsocketConnection,
    request: RequestProtocol,
    request_adapter: WebSocketRequestAdapter,
    api_context: ApiContext,
    enqueue_warning_tracker: EnqueueWarningTracker,
    trace_id: str | None,
) -> None:
    await _dispatch_plugin_backend_command(
        data=data,
        connection=connection,
        request=request,
        request_adapter=request_adapter,
        api_context=api_context,
        enqueue_warning_tracker=enqueue_warning_tracker,
        trace_id=trace_id,
        action_label="plugin_backend_remove",
        capability_label="Remove Backend",
        system_action_label="Remove backend",
        action_key="remove_backend",
        command_type=RemovePluginBackendCommand,
        audit_action="REMOVE_PLUGIN_BACKEND",
        audit_details_builder=_build_remove_audit_details,
        command_fields_builder=_build_remove_command_fields,
    )


async def handle_plugin_backend_update(
    data: JSONDict,
    *,
    connection: WebsocketConnection,
    request: RequestProtocol,
    request_adapter: WebSocketRequestAdapter,
    api_context: ApiContext,
    enqueue_warning_tracker: EnqueueWarningTracker,
    trace_id: str | None,
) -> None:
    await _dispatch_plugin_backend_command(
        data=data,
        connection=connection,
        request=request,
        request_adapter=request_adapter,
        api_context=api_context,
        enqueue_warning_tracker=enqueue_warning_tracker,
        trace_id=trace_id,
        action_label="plugin_backend_update",
        capability_label="Update Backend",
        system_action_label="Update backend",
        action_key="update_backend",
        command_type=UpdatePluginBackendCommand,
        audit_action="UPDATE_PLUGIN_BACKEND",
        audit_details_builder=_build_install_or_update_audit_details,
        command_fields_builder=_build_install_command_fields,
    )


async def _build_install_or_update_audit_details(
    plugin_manager_instance: PluginManagerProtocol,
    plugin_name: str,
    body: JSONDict,
) -> dict[str, JSONValue]:
    _ = body
    details: dict[str, JSONValue] = {
        "display_name": await plugin_manager_instance.get_plugin_display_name(plugin_name),
    }
    return details


async def _build_remove_audit_details(
    plugin_manager_instance: PluginManagerProtocol,
    plugin_name: str,
    body: JSONDict,
) -> dict[str, JSONValue]:
    delete_models = _read_delete_models(body)
    return {
        "display_name": await plugin_manager_instance.get_plugin_display_name(plugin_name),
        "delete_models": delete_models,
    }


def _build_install_command_fields(plugin_name: str, body: JSONDict) -> dict[str, JSONValue]:
    _ = body
    return {"plugin_name": plugin_name}


def _build_remove_command_fields(plugin_name: str, body: JSONDict) -> dict[str, JSONValue]:
    return {"plugin_name": plugin_name, "delete_models": _read_delete_models(body)}


def _read_delete_models(body: JSONDict) -> bool:
    delete_models_raw = body.get("delete_models")
    if isinstance(delete_models_raw, bool):
        return delete_models_raw
    raise ValueError("Validated plugin backend remove payload lost delete_models.")
