"""SoAI - HTTP endpoint for deleting all user conversations [backend/features/api/routes/webui/conversation_bulk_delete_routes.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from fastapi import Depends, Request
from fastapi.responses import JSONResponse
from starlette.responses import Response

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
from features.api.runtime.current_user import CurrentUser, get_current_user
from features.api.schemas.conversations import ConversationBatchDeleteRequest

__all__ = ("register_routes",)

CONVERSATION_EXECUTION_BULK_DELETE_REASON = "Bulk conversation deletion requested."


def register_routes(routers: ApiRouters) -> None:
    @routers.webui.post("/conversations/batch-delete")
    async def delete_selected_conversations(
        request: Request,
        payload: ConversationBatchDeleteRequest,
        current_user: CurrentUser = Depends(get_current_user),
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> Response:
        await quiesce_conversations_before_deletion(
            request=request,
            api_context=api_context,
            user_id=current_user["id"],
            conv_ids=tuple(payload.ids),
            reason=CONVERSATION_EXECUTION_BULK_DELETE_REASON,
        )
        await require_no_active_conversation_inputs(
            request=request,
            api_context=api_context,
            user_id=current_user["id"],
            conv_ids=tuple(payload.ids),
        )
        deleted_records = (
            await api_context.dependencies.database_conversations.delete_conversations(
                tuple(payload.ids),
                current_user["id"],
            )
        )
        deleted_count = len(deleted_records)
        if deleted_count > 0:
            api_context.dependencies.metrics_manager.increment_counter(
                "api",
                "webui",
                "conversations_deleted",
                value=deleted_count,
            )
        await publish_conversation_deletion_side_effects(
            api_context,
            user_id=current_user["id"],
            deleted_records=tuple(deleted_records),
        )
        return JSONResponse(
            content={
                "deleted": deleted_count,
                "deleted_ids": [record.conv_id for record in deleted_records],
            },
        )

    @routers.webui.delete("/conversations")
    async def delete_all_conversations(
        request: Request,
        current_user: CurrentUser = Depends(get_current_user),
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> Response:
        conv_ids = await api_context.dependencies.database_conversations.list_conversation_ids_for_deletion(
            current_user["id"],
        )
        await quiesce_conversations_before_deletion(
            request=request,
            api_context=api_context,
            user_id=current_user["id"],
            conv_ids=conv_ids,
            reason=CONVERSATION_EXECUTION_BULK_DELETE_REASON,
        )
        await require_no_active_conversation_inputs(
            request=request,
            api_context=api_context,
            user_id=current_user["id"],
            conv_ids=conv_ids,
        )
        deleted_records = (
            await api_context.dependencies.database_conversations.delete_all_conversations(
                current_user["id"],
            )
        )
        deleted_count = len(deleted_records)
        if deleted_count > 0:
            api_context.dependencies.metrics_manager.increment_counter(
                "api",
                "webui",
                "conversations_deleted",
                value=deleted_count,
            )
        await publish_conversation_deletion_side_effects(
            api_context,
            user_id=current_user["id"],
            deleted_records=tuple(deleted_records),
        )
        return JSONResponse(content={"deleted": deleted_count})
