"""SoAI - WebSocket plugin backend admin command field validation [backend/features/api/routes/system/events/websocket_admin_task_commands_plugin_backend_common.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.state.access import AccessAction
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
    from features.api.streaming.websocket import WebsocketConnection

__all__ = ("require_plugin_backend_admin_payload",)


async def require_plugin_backend_admin_payload(
    data: JSONDict,
    *,
    connection: WebsocketConnection,
    request: RequestProtocol,
    api_context: ApiContext,
    enqueue_warning_tracker: EnqueueWarningTracker,
    trace_id: str | None,
    action_label: str,
    run_id: str | None,
    allowed_fields: frozenset[str],
    require_delete_models: bool,
) -> tuple[JSONDict, str] | None:
    _ = request
    if AccessAction.PLUGIN_ADMIN not in connection.granted_actions:
        await enqueue_websocket_forbidden_error(
            enqueue_warning_tracker,
            connection.queue,
            trace_id,
            run_id=run_id,
        )
        return None
    body = resolve_body_or_root_dict(data)
    if set(body) - allowed_fields:
        await enqueue_websocket_invalid_request_error(
            enqueue_warning_tracker,
            connection.queue,
            trace_id,
            f"{action_label} contains unsupported fields.",
            run_id=run_id,
        )
        return None
    plugin_name_value = body.get("plugin_name")
    if not isinstance(plugin_name_value, str) or not plugin_name_value.strip():
        await enqueue_websocket_invalid_request_error(
            enqueue_warning_tracker,
            connection.queue,
            trace_id,
            f"{action_label} requires a non-empty plugin_name.",
            run_id=run_id,
        )
        return None
    plugin_name = plugin_name_value.strip()
    if "backend_variant_id" in body:
        backend_variant_id = body["backend_variant_id"]
        if not isinstance(backend_variant_id, str) or not backend_variant_id.strip():
            await enqueue_websocket_invalid_request_error(
                enqueue_warning_tracker,
                connection.queue,
                trace_id,
                f"{action_label} backend_variant_id must be a non-empty string.",
                run_id=run_id,
            )
            return None
        body["backend_variant_id"] = backend_variant_id.strip()
    if require_delete_models and not isinstance(body.get("delete_models"), bool):
        await enqueue_websocket_invalid_request_error(
            enqueue_warning_tracker,
            connection.queue,
            trace_id,
            f"{action_label} requires a strict boolean delete_models.",
            run_id=run_id,
        )
        return None
    plugin_manager_instance = api_context.dependencies.plugin_manager
    normalized_name = plugin_manager_instance.normalize_plugin_name(plugin_name)
    if not normalized_name:
        await enqueue_websocket_not_found_error(
            enqueue_warning_tracker,
            connection.queue,
            trace_id,
            f"Plugin '{plugin_name}' not found.",
            run_id=run_id,
        )
        return None
    return (body, normalized_name)
