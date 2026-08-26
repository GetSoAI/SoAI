"""SoAI - HTTP endpoints for updating conversation metadata [backend/features/api/routes/webui/conversation_update_routes.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from fastapi import Depends, Request
from starlette.responses import JSONResponse, Response

from core.errors.exceptions import ArchivedConversationLimitError, ValidationError
from core.prompts.colors import validate_prompt_color
from features.api.routes.webui.conversation_event_publishing import (
    publish_conversation_update,
)
from features.api.runtime.container.api_routers import ApiRouters
from features.api.runtime.context import ApiContext, resolve_api_context
from features.api.runtime.conversation_access import resolve_conversation_access_id
from features.api.runtime.conversation_settings_projection import (
    project_effective_conversation_settings,
)
from features.api.runtime.current_user import CurrentUser, get_current_user
from features.api.runtime.errors import raise_conflict, raise_invalid_request
from features.api.runtime.webui_records import webui_fetch_or_404
from features.api.schemas.conversations import (
    ConversationArchivedUpdate,
    ConversationColorUpdate,
    ConversationFavoriteUpdate,
    ConversationUpdate,
)

__all__ = ("register_routes",)


def register_routes(routers: ApiRouters) -> None:
    @routers.webui.patch("/conversations/{conv_id}/title")
    async def update_conversation_metadata(
        request: Request,
        conv_id: str,
        payload: ConversationUpdate,
        current_user: CurrentUser = Depends(get_current_user),
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> Response:
        conversation_record = await webui_fetch_or_404(
            request,
            api_context.dependencies.webui_manager.database_conversations.update_conversation_title(
                conv_id,
                current_user["id"],
                payload.title,
            ),
            message="Conversation not found.",
        )
        resolved_conv_id = resolve_conversation_access_id(conversation_record, conv_id)
        await publish_conversation_update(
            request,
            api_context,
            current_user["id"],
            resolved_conv_id,
            conversation_record,
            title=payload.title,
        )
        return JSONResponse(
            content=project_effective_conversation_settings(
                request=request,
                config=api_context.dependencies.config,
                conversation_record=conversation_record,
            ),
        )

    @routers.webui.patch("/conversations/{conv_id}/color")
    async def patch_conversation_color(
        request: Request,
        conv_id: str,
        payload: ConversationColorUpdate,
        current_user: CurrentUser = Depends(get_current_user),
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> Response:
        try:
            validated_color = validate_prompt_color(payload.color)
        except (ValidationError, ValueError) as error:
            raise_invalid_request(request, str(error), error_type="invalid_color")
        conversation_record = await webui_fetch_or_404(
            request,
            api_context.dependencies.webui_manager.database_conversations.update_conversation_color(
                conv_id,
                current_user["id"],
                validated_color,
            ),
            message="Conversation not found.",
        )
        resolved_conv_id = resolve_conversation_access_id(conversation_record, conv_id)
        await publish_conversation_update(
            request,
            api_context,
            current_user["id"],
            resolved_conv_id,
            conversation_record,
            color=validated_color,
            color_present=True,
        )
        return JSONResponse(
            content=project_effective_conversation_settings(
                request=request,
                config=api_context.dependencies.config,
                conversation_record=conversation_record,
            ),
        )

    @routers.webui.patch("/conversations/{conv_id}/favorite")
    async def patch_conversation_favorite(
        request: Request,
        conv_id: str,
        payload: ConversationFavoriteUpdate,
        current_user: CurrentUser = Depends(get_current_user),
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> Response:
        database_conversations = api_context.dependencies.webui_manager.database_conversations
        conversation_record = await webui_fetch_or_404(
            request,
            database_conversations.update_conversation_favorite(
                conv_id,
                current_user["id"],
                payload.is_favorite,
            ),
            message="Conversation not found.",
        )
        resolved_conv_id = resolve_conversation_access_id(conversation_record, conv_id)
        await publish_conversation_update(
            request,
            api_context,
            current_user["id"],
            resolved_conv_id,
            conversation_record,
            is_favorite=payload.is_favorite,
        )
        return JSONResponse(
            content=project_effective_conversation_settings(
                request=request,
                config=api_context.dependencies.config,
                conversation_record=conversation_record,
            ),
        )

    @routers.webui.patch("/conversations/{conv_id}/archived")
    async def patch_conversation_archived(
        request: Request,
        conv_id: str,
        payload: ConversationArchivedUpdate,
        current_user: CurrentUser = Depends(get_current_user),
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> Response:
        database_conversations = api_context.dependencies.webui_manager.database_conversations
        try:
            conversation_record = await webui_fetch_or_404(
                request,
                database_conversations.update_conversation_archived(
                    conv_id,
                    current_user["id"],
                    payload.is_archived,
                ),
                message="Conversation not found.",
            )
        except ArchivedConversationLimitError as exception:
            raise_conflict(request, str(exception), error_type="archive_limit_reached")
        resolved_conv_id = resolve_conversation_access_id(conversation_record, conv_id)
        await publish_conversation_update(
            request,
            api_context,
            current_user["id"],
            resolved_conv_id,
            conversation_record,
            is_archived=payload.is_archived,
        )
        return JSONResponse(
            content=project_effective_conversation_settings(
                request=request,
                config=api_context.dependencies.config,
                conversation_record=conversation_record,
            ),
        )
