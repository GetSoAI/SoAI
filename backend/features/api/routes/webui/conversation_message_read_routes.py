"""SoAI - HTTP endpoints for reading conversation messages [backend/features/api/routes/webui/conversation_message_read_routes.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import Depends, Request
from starlette.responses import JSONResponse, Response

from core.errors.exceptions import ValidationError
from core.validation.epoch import EPOCH_MS_MIN, require_unix_epoch_ms
from core.validation.requirements import require_non_negative_int
from features.api.routes.webui.conversation_message_write_outputs import (
    serialize_assistant_stream_state,
    serialize_message_sync_cursor,
    serialize_message_window_result,
    serialize_running_activity_snapshot,
)
from features.api.routes.webui.conversation_stream_state_freshness import (
    flush_matching_chat_stream_state_runtime,
)
from features.api.runtime.container.api_routers import ApiRouters
from features.api.runtime.context import ApiContext, resolve_api_context
from features.api.runtime.current_user import CurrentUser, get_current_user
from features.api.runtime.errors import raise_invalid_request, raise_not_found
from features.api.runtime.webui_records import webui_fetch_or_404

if TYPE_CHECKING:
    from core.conversations.conversation_message_window import (
        ConversationMessageWindowDirection,
    )

__all__ = ("register_routes",)


def _require_message_window_direction(value: str) -> ConversationMessageWindowDirection:
    if value == "tail":
        return "tail"
    if value == "before":
        return "before"
    if value == "after":
        return "after"
    if value == "around":
        return "around"
    raise ValidationError("direction must be tail, before, after, or around.")


def register_routes(routers: ApiRouters) -> None:
    @routers.webui.get("/conversations/{conv_id}/messages/window")
    async def get_conversation_message_window(
        request: Request,
        conv_id: str,
        direction: str,
        limit: int = 25,
        cursor_created_at_ms: int | None = None,
        cursor_id: int | None = None,
        anchor_created_at_ms: int | None = None,
        anchor_id: int | None = None,
        current_user: CurrentUser = Depends(get_current_user),
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> Response:
        try:
            validated_direction = _require_message_window_direction(direction)
            read_result = await api_context.dependencies.database_messages.get_message_window(
                conv_id,
                current_user["id"],
                direction=validated_direction,
                limit=limit,
                cursor_created_at_ms=cursor_created_at_ms,
                cursor_id=cursor_id,
                anchor_created_at_ms=anchor_created_at_ms,
                anchor_id=anchor_id,
            )
        except ValidationError as exception:
            raise_invalid_request(request, str(exception))
        if read_result is None:
            raise_not_found(
                request,
                "Conversation not found or you do not have permission to access it.",
            )
        return JSONResponse(
            content=await serialize_message_window_result(
                read_result,
                api_context=api_context,
                current_user=current_user,
            )
        )

    @routers.webui.get("/conversations/{conv_id}/messages/running-activity")
    async def get_conversation_running_activity(
        request: Request,
        conv_id: str,
        current_user: CurrentUser = Depends(get_current_user),
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> Response:
        try:
            snapshot = (
                await api_context.dependencies.database_messages.get_running_activity_snapshot(
                    conv_id,
                    current_user["id"],
                )
            )
        except ValidationError as exception:
            raise_invalid_request(request, str(exception))
        if snapshot is None:
            raise_not_found(
                request,
                "Conversation not found or you do not have permission to access it.",
            )
        return JSONResponse(
            content=await serialize_running_activity_snapshot(
                snapshot,
                api_context=api_context,
                current_user=current_user,
            )
        )

    @routers.webui.get(
        "/conversations/{conv_id}/assistant-turns/{assistant_turn_at_ms}/variants/{model_variant_index}/stream-state",
    )
    async def get_assistant_turn_variant_stream_state(
        request: Request,
        conv_id: str,
        assistant_turn_at_ms: int,
        model_variant_index: int,
        current_user: CurrentUser = Depends(get_current_user),
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> Response:
        try:
            validated_assistant_turn_at_ms = require_unix_epoch_ms(
                assistant_turn_at_ms,
                error_message=(
                    f"assistant_turn_at_ms must be an epoch-millisecond integer >= {EPOCH_MS_MIN}."
                ),
                enforce_maximum=False,
            )
            validated_model_variant_index = require_non_negative_int(
                model_variant_index,
                error_message="model_variant_index must be a non-negative integer.",
            )
            await flush_matching_chat_stream_state_runtime(
                api_context,
                user_id=current_user["id"],
                conv_id=conv_id,
                assistant_turn_at_ms=validated_assistant_turn_at_ms,
                model_variant_index=validated_model_variant_index,
            )
            payload = await webui_fetch_or_404(
                request,
                api_context.dependencies.database_messages.get_assistant_turn_variant_stream_state(
                    conv_id,
                    current_user["id"],
                    validated_assistant_turn_at_ms,
                    validated_model_variant_index,
                ),
                message="Assistant message not found or you do not have permission to access it.",
            )
        except ValidationError as exception:
            raise_invalid_request(request, str(exception))
        return JSONResponse(
            content=await serialize_assistant_stream_state(
                payload,
                api_context=api_context,
                current_user=current_user,
                conv_id=conv_id,
            )
        )

    @routers.webui.get("/conversations/{conv_id}/messages/sync-cursor")
    async def get_conversation_message_sync_cursor(
        request: Request,
        conv_id: str,
        current_user: CurrentUser = Depends(get_current_user),
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> Response:
        sync_cursor = await api_context.dependencies.database_messages.get_message_sync_cursor(
            conv_id,
            current_user["id"],
        )
        if sync_cursor is None:
            raise_not_found(
                request,
                "Conversation not found or you do not have permission to access it.",
            )
        return JSONResponse(content=serialize_message_sync_cursor(sync_cursor))
