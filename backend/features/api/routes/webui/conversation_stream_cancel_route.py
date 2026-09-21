"""SoAI - Request-fenced Chat stream cancellation route [backend/features/api/routes/webui/conversation_stream_cancel_route.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from fastapi import Depends, Request

from features.api.runtime.container.api_routers import ApiRouters
from features.api.runtime.context import ApiContext, resolve_api_context
from features.api.runtime.conversation_access import require_conversation_access_context
from features.api.runtime.current_user import CurrentUser, get_current_user
from features.api.schemas.conversations import (
    ConversationStreamCancelRequest,
    ConversationStreamCancelResponse,
)
from features.chat.conversation_stream_cancellation_operation import (
    accept_chat_stream_cancellation,
)

__all__ = ("register_routes",)


def register_routes(routers: ApiRouters) -> None:
    @routers.webui.post(
        "/conversations/{conv_id}/stream/cancel",
        response_model=ConversationStreamCancelResponse,
    )
    async def cancel_conversation_stream(
        request: Request,
        conv_id: str,
        payload: ConversationStreamCancelRequest,
        current_user: CurrentUser = Depends(get_current_user),
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> ConversationStreamCancelResponse:
        conversation_context = await require_conversation_access_context(
            request,
            api_context=api_context,
            conv_id=conv_id,
            user_id=current_user["id"],
        )
        accepted = await accept_chat_stream_cancellation(
            api_dependencies=api_context.dependencies,
            context=request.state.context,
            user_id=current_user["id"],
            conv_id=conversation_context.resolved_conv_id,
            request_id=payload.request_id,
            force_pending_steers=payload.force_pending_steers,
            allow_unregistered_target=True,
        )
        return ConversationStreamCancelResponse(
            conversation_id=accepted.conversation_id,
            request_id=accepted.request_id,
            status=accepted.status,
        )
