"""SoAI - Conversation clone WebUI routes [backend/features/api/routes/webui/conversation_clone_routes.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from fastapi import Depends, Request
from starlette.responses import JSONResponse, Response

from core.errors.exceptions import ConflictError, ValidationError
from core.events.conversation_publication import publish_conversation_created
from features.api.runtime.container.api_routers import ApiRouters
from features.api.runtime.context import ApiContext, resolve_api_context
from features.api.runtime.conversation_settings_projection import (
    project_effective_conversation_settings,
)
from features.api.runtime.current_user import CurrentUser, get_current_user
from features.api.runtime.errors import raise_conflict, raise_invalid_request, raise_not_found
from features.api.schemas.conversations import ConversationCloneRequest

__all__ = ("register_routes",)


def register_routes(routers: ApiRouters) -> None:
    @routers.webui.post("/conversations/{conv_id}/clone", status_code=201)
    async def clone_conversation(
        request: Request,
        conv_id: str,
        payload: ConversationCloneRequest,
        current_user: CurrentUser = Depends(get_current_user),
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> Response:
        try:
            conversation_record = (
                await api_context.dependencies.database_conversations.clone_conversation(
                    conv_id,
                    current_user["id"],
                    target_conv_id=payload.id,
                )
            )
        except ConflictError as exception:
            raise_conflict(request, str(exception))
        except ValidationError as exception:
            raise_invalid_request(request, str(exception))
        if conversation_record is None:
            raise_not_found(
                request,
                "Conversation not found or you do not have permission to access it.",
            )
        response_content = project_effective_conversation_settings(
            request=request,
            config=api_context.dependencies.config,
            conversation_record=conversation_record,
        )
        await publish_conversation_created(
            api_context.dependencies.event_bus,
            user_id=current_user["id"],
            conversation_record=conversation_record,
        )
        return JSONResponse(content=response_content)
