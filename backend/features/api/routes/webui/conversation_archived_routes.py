"""SoAI - Archived conversation REST routes [backend/features/api/routes/webui/conversation_archived_routes.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from fastapi import Depends, Query

from core.conversations.archived_conversation_models import (
    ArchivedConversationsListRequest,
    ArchivedConversationsResponse,
    ArchivedConversationsSearchResponse,
)
from features.api.runtime.container.api_routers import ApiRouters
from features.api.runtime.context import ApiContext, resolve_api_context
from features.api.runtime.current_user import CurrentUser, get_current_user

__all__ = ("register_routes",)


def register_routes(routers: ApiRouters) -> None:
    @routers.webui.get("/conversations/archived", response_model=ArchivedConversationsResponse)
    async def list_archived_conversations(
        limit: int = Query(default=50, ge=1, le=200),
        before_last_modified_at_ms: int | None = Query(default=None, ge=1),
        before_id: str | None = Query(default=None, min_length=1),
        current_user: CurrentUser = Depends(get_current_user),
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> ArchivedConversationsResponse:
        list_request = ArchivedConversationsListRequest(
            limit=limit,
            before_last_modified_at_ms=before_last_modified_at_ms,
            before_id=before_id,
        )
        database_conversations = api_context.dependencies.webui_manager.database_conversations
        page = await database_conversations.list_archived_conversations(
            current_user["id"],
            limit=list_request.limit,
            before_last_modified_at_ms=list_request.before_last_modified_at_ms,
            before_id=list_request.before_id,
        )
        return ArchivedConversationsResponse(
            conversations=page.conversations,
            total_count=page.total_count,
            next_cursor=page.next_cursor,
        )

    @routers.webui.get(
        "/conversations/archived/search",
        response_model=ArchivedConversationsSearchResponse,
    )
    async def search_archived_conversations(
        query: str = Query(default="", alias="q"),
        limit: int = Query(default=50, ge=1, le=200),
        current_user: CurrentUser = Depends(get_current_user),
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> ArchivedConversationsSearchResponse:
        database_conversations = api_context.dependencies.webui_manager.database_conversations
        conversations = await database_conversations.search_archived_conversation_titles(
            current_user["id"],
            query,
            limit,
        )
        return ArchivedConversationsSearchResponse(conversations=conversations)
