"""SoAI - WebUI per-conversation RAG document delete routes [backend/features/api/routes/webui/conversation_rag/documents/delete_routes.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from fastapi import Depends, Request
from starlette.responses import Response

from core.state.access import AccessAction
from core.timing.epoch import epoch_ms
from features.api.routes.webui.conversation_attachments.events import (
    publish_knowledge_attachment_changed,
)
from features.api.routes.webui.conversation_rag.knowledge_attachment_identity import (
    require_knowledge_attachment_id,
)
from features.api.routes.webui.conversation_rag.knowledge_attachment_lifecycle import (
    ensure_and_publish_knowledge_attachment,
)
from features.api.routes.webui.rag_dependencies import require_rag_engine
from features.api.routes.webui.request_validators import require_user_id
from features.api.runtime.access_dependencies import require_action_dependencies
from features.api.runtime.container.api_routers import ApiRouters
from features.api.runtime.context import ApiContext, resolve_api_context
from features.api.runtime.current_user import CurrentUser, get_current_user
from features.api.runtime.responses import create_no_content_response
from features.api.runtime.webui_records import webui_require_true_or_404

__all__ = ("register_routes",)


def register_routes(routers: ApiRouters) -> None:
    @routers.webui.delete(
        "/conversations/{conv_id}/rag/documents/{doc_id}",
        status_code=204,
        dependencies=require_action_dependencies(AccessAction.RAG_USE),
    )
    async def delete_rag_document(
        request: Request,
        conv_id: str,
        doc_id: str,
        current_user: CurrentUser = Depends(get_current_user),
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> Response:
        rag_engine = require_rag_engine(request, api_context)
        user_id = require_user_id(request, current_user)
        resolved_id = await rag_engine.resolve_conv_id_for_user(conv_id, user_id)
        document = await api_context.dependencies.database_files.get_rag_document_by_id(doc_id)
        await webui_require_true_or_404(
            request,
            rag_engine.delete_document(resolved_id, doc_id),
            message="Document not found.",
        )
        if document is not None:
            filename = str(document.get("filename") or doc_id)
            file_type_value = document.get("file_type")
            file_size_value = document.get("file_size_bytes")
            summary = await ensure_and_publish_knowledge_attachment(
                api_context=api_context,
                conv_id=resolved_id,
                user_id=user_id,
                source_type="document_delete",
                operation_type="removed",
                title=filename,
            )
            updated_summary = await api_context.dependencies.database_conversation_knowledge_attachments.add_knowledge_attachment_item(
                conv_id=resolved_id,
                user_id=user_id,
                knowledge_attachment_id=require_knowledge_attachment_id(summary),
                document_id=doc_id,
                event_id=None,
                item_index=0,
                filename=filename,
                file_type=file_type_value if isinstance(file_type_value, str) else None,
                file_size_bytes=(file_size_value if isinstance(file_size_value, int) else None),
                rag_status="completed",
                operation_type="removed",
                error_message=None,
                created_at_ms=epoch_ms(),
            )
            await publish_knowledge_attachment_changed(
                api_context.dependencies.event_bus,
                summary=updated_summary,
            )
        return create_no_content_response()
