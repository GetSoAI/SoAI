"""SoAI - Chat input client-disconnect cancellation policy [backend/features/chat/conversation_input_disconnect.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.validation.integers import is_strict_int
from features.api.routes.system.events.chat_stream.cancel import (
    schedule_ws_chat_stream_cancel,
)
from features.chat.conversation_stream_cancellation import (
    mark_conversation_stream_runtime_cancellation_requested,
)

if TYPE_CHECKING:
    from features.api.runtime.context import ApiContext
    from features.api.streaming.websocket import WebsocketConnection

__all__ = ("cancel_running_chat_input_for_disconnected_client",)


async def cancel_running_chat_input_for_disconnected_client(
    *,
    api_context: ApiContext,
    connection: WebsocketConnection,
) -> None:
    if not api_context.dependencies.config.get_bool(
        "MODELS.ROUTING.CANCEL_ON_CLIENT_DISCONNECT",
    ):
        return
    client_id = connection.conversation_presence_tab_id
    user_id_value = connection.user.get("id")
    if not client_id or not is_strict_int(user_id_value) or user_id_value <= 0:
        return
    input_records = (
        await api_context.dependencies.database_input_queue.list_running_chat_inputs_for_client(
            user_id=int(user_id_value),
            client_id=client_id,
        )
    )
    reason = "WebSocket client disconnected."
    for input_record in input_records:
        conv_id = input_record.get("conv_id")
        request_id = input_record.get("request_id")
        if not isinstance(conv_id, str) or not isinstance(request_id, str):
            continue
        runtime = await api_context.dependencies.chat_stream_registry.get(
            user_id=int(user_id_value),
            conv_id=conv_id,
        )
        if runtime is None or runtime.request_id != request_id:
            continue
        mark_conversation_stream_runtime_cancellation_requested(runtime, reason)
        _ = schedule_ws_chat_stream_cancel(
            api_context=api_context,
            context=connection.request.state.context,
            runtime=runtime,
            reason=reason,
        )
