"""SoAI - WebSocket dispatching for system admin messages [backend/features/api/routes/system/events/websocket_message_dispatch_admin.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from features.api.routes.system.events.internal_protocols import WebSocketMessageTypes
from features.api.routes.system.events.websocket_admin_updates import (
    handle_update_openai_api_key_quota,
    handle_update_user_workspace_path,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from features.api.routes.system.events.websocket_event_context import (
        WebsocketEventRuntimeContext,
    )

__all__ = ("try_handle_admin_message",)


async def try_handle_admin_message(
    message_type: str,
    data: JSONDict,
    *,
    runtime_context: WebsocketEventRuntimeContext,
) -> bool:
    match message_type:
        case WebSocketMessageTypes.UPDATE_OPENAI_API_KEY_QUOTA:
            await runtime_context.invoke_with_request_adapter(
                handle_update_openai_api_key_quota,
                data,
            )
            return True
        case WebSocketMessageTypes.UPDATE_USER_WORKSPACE_PATH:
            await runtime_context.invoke_with_request_adapter(
                handle_update_user_workspace_path,
                data,
            )
            return True
        case _:
            return False
