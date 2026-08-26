"""SoAI - WebSocket model admin task commands [backend/features/api/routes/system/events/websocket_admin_task_commands_models.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.events.types_models_model_commands import ModelDownloadCommand
from core.state.access import AccessAction
from core.state.state_names import ORCH_STATE_DISABLED
from core.validation.strings import coerce_optional_trimmed_str
from features.api.routes.system.events.websocket_admin_plugin_action_support import (
    PluginAdminDispatchContext,
    dispatch_plugin_admin_command_accepted_for_context,
    enqueue_plugin_admin_invalid_request,
    resolve_run_id,
)
from features.api.routes.system.events.websocket_command_payloads import (
    resolve_body_or_root_dict,
)
from features.api.routes.system.events.websocket_errors import (
    enqueue_websocket_forbidden_error,
    enqueue_websocket_invalid_request_error,
    enqueue_websocket_not_found_error,
)
from features.api.runtime.container.enqueue_warning_tracker import EnqueueWarningTracker

if TYPE_CHECKING:
    from core.runtime.protocols import RequestProtocol
    from core.types.json import JSONDict
    from features.api.runtime.context import ApiContext
    from features.api.streaming.websocket import (
        WebsocketConnection,
        WebSocketRequestAdapter,
    )

__all__ = ("handle_model_download",)


async def handle_model_download(
    data: JSONDict,
    *,
    connection: WebsocketConnection,
    request: RequestProtocol,
    request_adapter: WebSocketRequestAdapter,
    api_context: ApiContext,
    enqueue_warning_tracker: EnqueueWarningTracker,
    trace_id: str | None,
) -> None:
    _ = request_adapter
    run_id = resolve_run_id(data)
    if AccessAction.MODEL_ADMIN not in connection.granted_actions:
        await enqueue_websocket_forbidden_error(
            enqueue_warning_tracker,
            connection.queue,
            trace_id,
            run_id=run_id,
        )
        return
    body = resolve_body_or_root_dict(data)
    universal_id = coerce_optional_trimmed_str(body.get("universal_id"))
    plugin_name: str | None
    model_id: str | None
    if universal_id is not None:
        model_info = await api_context.dependencies.model_information_service.model_get_info(
            universal_id,
        )
        if not model_info:
            await enqueue_websocket_not_found_error(
                enqueue_warning_tracker,
                connection.queue,
                trace_id,
                f"Model with universal_id '{universal_id}' not found.",
                run_id=run_id,
            )
            return
        plugin_value = model_info.get("plugin")
        model_id_value = model_info.get("model_id")
        plugin_name = coerce_optional_trimmed_str(plugin_value)
        model_id = coerce_optional_trimmed_str(model_id_value)
    else:
        plugin_value = body.get("plugin")
        model_id_value = body.get("model_id")
        plugin_name = coerce_optional_trimmed_str(plugin_value)
        model_id = coerce_optional_trimmed_str(model_id_value)
    if plugin_name is None:
        await enqueue_websocket_invalid_request_error(
            enqueue_warning_tracker,
            connection.queue,
            trace_id,
            "Plugin name is required.",
            run_id=run_id,
        )
        return
    if model_id is None:
        await enqueue_websocket_invalid_request_error(
            enqueue_warning_tracker,
            connection.queue,
            trace_id,
            "Model ID is required.",
            run_id=run_id,
        )
        return
    plugin_manager_instance = api_context.dependencies.plugin_manager
    normalized_plugin_name = plugin_manager_instance.normalize_plugin_name(plugin_name)
    if not normalized_plugin_name:
        await enqueue_websocket_not_found_error(
            enqueue_warning_tracker,
            connection.queue,
            trace_id,
            f"Plugin '{plugin_name}' not found.",
            run_id=run_id,
        )
        return
    plugin_name = normalized_plugin_name
    display_name = await plugin_manager_instance.get_plugin_display_name(plugin_name)
    plugin_status = await api_context.dependencies.state_aggregator.get_plugin_status(plugin_name)
    if plugin_status == ORCH_STATE_DISABLED:
        await enqueue_plugin_admin_invalid_request(
            connection=connection,
            enqueue_warning_tracker=enqueue_warning_tracker,
            trace_id=trace_id,
            run_id=run_id,
            message=f"Cannot download model because plugin '{display_name}' is disabled.",
            code="plugin_disabled",
        )
        return
    quantization = coerce_optional_trimmed_str(body.get("quantization"))
    dispatch_context = PluginAdminDispatchContext(
        request,
        api_context,
        connection,
        enqueue_warning_tracker,
        trace_id,
        run_id,
        plugin_name,
    )
    await dispatch_plugin_admin_command_accepted_for_context(
        dispatch_context,
        capability_name="SUPPORTS_MODEL_DOWNLOAD",
        capability_label="Model Download",
        action_label="Model download",
        action_key="download_model",
        command_type=ModelDownloadCommand,
        command_factory=ModelDownloadCommand,
        audit_action="DOWNLOAD_MODEL",
        audit_target=model_id,
        audit_details={
            "plugin": plugin_name,
            "display_name": display_name,
            "quantization": quantization,
        },
        command_fields={
            "plugin_name": plugin_name,
            "model_id": model_id,
            "quantization": quantization,
        },
    )
