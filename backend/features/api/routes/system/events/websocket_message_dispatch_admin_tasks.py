"""SoAI - WebSocket dispatching for admin task commands [backend/features/api/routes/system/events/websocket_message_dispatch_admin_tasks.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from features.api.routes.system.events.internal_protocols import WebSocketMessageTypes
from features.api.routes.system.events.websocket_admin_task_commands_models import (
    handle_model_download,
)
from features.api.routes.system.events.websocket_admin_task_commands_plugins import (
    handle_plugin_backend_install,
    handle_plugin_backend_remove,
    handle_plugin_backend_update,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from features.api.routes.system.events.websocket_event_context import (
        WebsocketEventRuntimeContext,
    )

__all__ = ("try_handle_admin_task_message",)


async def try_handle_admin_task_message(
    message_type: str,
    data: JSONDict,
    *,
    runtime_context: WebsocketEventRuntimeContext,
) -> bool:
    match message_type:
        case WebSocketMessageTypes.PLUGIN_BACKEND_INSTALL:
            await runtime_context.invoke_with_request_adapter(handle_plugin_backend_install, data)
            return True
        case WebSocketMessageTypes.PLUGIN_BACKEND_REMOVE:
            await runtime_context.invoke_with_request_adapter(handle_plugin_backend_remove, data)
            return True
        case WebSocketMessageTypes.PLUGIN_BACKEND_UPDATE:
            await runtime_context.invoke_with_request_adapter(handle_plugin_backend_update, data)
            return True
        case WebSocketMessageTypes.MODEL_DOWNLOAD:
            await runtime_context.invoke_with_request_adapter(handle_model_download, data)
            return True
        case _:
            return False
