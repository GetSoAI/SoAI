"""SoAI - HTTP endpoints for retrieving and deleting conversations [backend/features/api/routes/webui/conversation_detail_routes.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from fastapi import Depends, Request
from fastapi.responses import JSONResponse
from starlette.responses import Response

from core.errors.exceptions import NotFoundError, ValidationError
from features.api.routes.webui.conversation_deletion_events import (
    publish_conversation_deletion_side_effects,
)
from features.api.routes.webui.conversation_deletion_input_blockers import (
    require_no_active_conversation_inputs,
)
from features.api.routes.webui.conversation_deletion_quiescence import (
    quiesce_conversations_before_deletion,
)
from features.api.runtime.container.api_routers import ApiRouters
from features.api.runtime.context import ApiContext, resolve_api_context
from features.api.runtime.conversation_settings_projection import (
    project_effective_conversation_settings,
)
from features.api.runtime.current_user import CurrentUser, get_current_user
from features.api.runtime.responses import create_no_content_response
from features.api.runtime.webui_records import webui_fetch_or_404

__all__ = ("register_routes",)

CONVERSATION_EXECUTION_DELETE_REASON = "Conversation deletion requested."


def register_routes(routers: ApiRouters) -> None:
    @routers.webui.get("/conversations/{conv_id}")
    async def get_single_conversation(
        request: Request,
        conv_id: str,
        current_user: CurrentUser = Depends(get_current_user),
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> Response:
        record = await webui_fetch_or_404(
            request,
            api_context.dependencies.database_conversations.get_conversation(
                conv_id,
                current_user["id"],
            ),
            message="Conversation not found.",
        )
        if not isinstance(record, dict):
            raise ValidationError("Conversation record must be an object.")
        normalized = project_effective_conversation_settings(
            request=request,
            config=api_context.dependencies.config,
            conversation_record=record,
        )
        return JSONResponse(content=normalized)

    @routers.webui.delete("/conversations/{conv_id}", status_code=204)
    async def delete_a_conversation(
        request: Request,
        conv_id: str,
        current_user: CurrentUser = Depends(get_current_user),
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> Response:
        await quiesce_conversations_before_deletion(
            request=request,
            api_context=api_context,
            user_id=current_user["id"],
            conv_ids=(conv_id,),
            reason=CONVERSATION_EXECUTION_DELETE_REASON,
        )
        await require_no_active_conversation_inputs(
            request=request,
            api_context=api_context,
            user_id=current_user["id"],
            conv_ids=(conv_id,),
        )
        deleted_record = await api_context.dependencies.database_conversations.delete_conversation(
            conv_id,
            current_user["id"],
        )
        if deleted_record is None:
            raise NotFoundError("Conversation not found.", trace_id=request.state.context.trace_id)
        api_context.dependencies.metrics_manager.increment_counter(
            "api",
            "webui",
            "conversations_deleted",
        )
        await publish_conversation_deletion_side_effects(
            api_context,
            user_id=current_user["id"],
            deleted_records=(deleted_record,),
        )
        return create_no_content_response()
