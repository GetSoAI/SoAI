"""SoAI - WebUI reusable knowledge catalog routes [backend/features/api/routes/webui/knowledge_catalog_routes.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from fastapi import Depends, Request
from starlette.responses import JSONResponse, Response

from features.api.routes.webui.conversation_attachments.knowledge_contracts import (
    KnowledgeAttachmentReusableRequest,
)
from features.api.routes.webui.request_validators import require_user_id
from features.api.runtime.container.api_routers import ApiRouters
from features.api.runtime.context import ApiContext, resolve_api_context
from features.api.runtime.current_user import CurrentUser, get_current_user

__all__ = ("register_routes",)


def register_routes(routers: ApiRouters) -> None:
    @routers.webui.post("/knowledge-attachments/reusable")
    async def list_reusable_knowledge_attachments(
        request: Request,
        body: KnowledgeAttachmentReusableRequest,
        current_user: CurrentUser = Depends(get_current_user),
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> Response:
        user_id = require_user_id(request, current_user)
        items = await api_context.dependencies.database_conversation_linked_knowledge.list_reusable_knowledge_attachments(
            user_id=user_id,
            query=body.query,
            limit=body.limit,
        )
        return JSONResponse(
            content={
                "items": items,
                "use_max_items": api_context.dependencies.config.get_int(
                    "SERVER.WEBUI.KNOWLEDGE_LINKS.USE_MAX_ITEMS",
                ),
            },
        )
