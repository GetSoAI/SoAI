"""SoAI - WebUI per-conversation RAG document upload routes [backend/features/api/routes/webui/conversation_rag/documents/upload/upload_routes.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from fastapi import Depends, Query, Request
from starlette.responses import Response

from core.attachments.attachment_content_validation import require_knowledge_source_type
from core.state.access import AccessAction
from features.api.routes.webui.conversation_rag.documents.upload.flow import (
    handle_rag_document_upload,
)
from features.api.routes.webui.request_validators import require_user_id
from features.api.runtime.access_dependencies import require_action_dependencies
from features.api.runtime.container.api_routers import ApiRouters
from features.api.runtime.context import ApiContext, resolve_api_context
from features.api.runtime.current_user import CurrentUser, get_current_user

__all__ = ("register_routes",)


def register_routes(routers: ApiRouters) -> None:
    @routers.webui.post(
        "/conversations/{conv_id}/rag/documents",
        status_code=202,
        dependencies=require_action_dependencies(AccessAction.RAG_USE),
    )
    async def upload_rag_document(
        request: Request,
        conv_id: str,
        client_batch_id: str | None = Query(None),
        attachment_source: str = Query("composer_document_upload"),
        current_user: CurrentUser = Depends(get_current_user),
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> Response:
        user_id = require_user_id(request, current_user)
        return await handle_rag_document_upload(
            request,
            conv_id=conv_id,
            user_id=user_id,
            api_context=api_context,
            client_batch_id=client_batch_id,
            attachment_source=require_knowledge_source_type(attachment_source),
        )
