"""SoAI - Conversation settings update route [backend/features/api/routes/webui/conversation_settings_route.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from fastapi import Depends, Request
from starlette.responses import JSONResponse, Response

from features.api.routes.webui.conversation_settings_update import (
    update_conversation_settings_record,
)
from features.api.runtime.container.api_routers import ApiRouters
from features.api.runtime.context import ApiContext, resolve_api_context
from features.api.runtime.conversation_settings_projection import (
    project_effective_conversation_settings,
)
from features.api.runtime.current_user import CurrentUser, get_current_user
from features.api.schemas.conversations import ConversationSettingsUpdate

__all__ = ("register_routes",)


def register_routes(routers: ApiRouters) -> None:
    @routers.webui.patch("/conversations/{conv_id}/settings")
    async def update_conversation_model_settings(
        request: Request,
        conv_id: str,
        payload: ConversationSettingsUpdate,
        current_user: CurrentUser = Depends(get_current_user),
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> Response:
        conversation_record, _previous_mode, _next_mode = await update_conversation_settings_record(
            request=request,
            conv_id=conv_id,
            payload=payload,
            current_user=current_user,
            api_context=api_context,
        )
        return JSONResponse(
            content=project_effective_conversation_settings(
                request=request,
                config=api_context.dependencies.config,
                conversation_record=conversation_record,
            ),
        )
