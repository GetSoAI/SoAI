"""SoAI - WebUI per-conversation RAG document listing routes [backend/features/api/routes/webui/conversation_rag/documents/list_routes.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import Depends, Query, Request
from starlette.responses import JSONResponse, Response

from core.attachments.knowledge_attachment_statuses import (
    RAG_DOCUMENT_STATUS_COUNT_KEYS,
)
from core.serialization.json import normalize_for_json
from core.state.access import AccessAction
from core.types.json_value import coerce_json_dict
from core.validation.integers import is_strict_int
from features.api.routes.webui.rag_dependencies import require_rag_engine
from features.api.routes.webui.request_validators import require_user_id
from features.api.runtime.access_dependencies import require_action_dependencies
from features.api.runtime.container.api_routers import ApiRouters
from features.api.runtime.context import ApiContext, resolve_api_context
from features.api.runtime.current_user import CurrentUser, get_current_user
from features.api.runtime.errors import raise_server_error

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("register_routes",)

_DEFAULT_RAG_DOCUMENTS_PAGE_SIZE = 50
_MAX_RAG_DOCUMENTS_PAGE_SIZE = 500


def register_routes(routers: ApiRouters) -> None:
    @routers.webui.get(
        "/conversations/{conv_id}/rag/documents",
        dependencies=require_action_dependencies(AccessAction.RAG_USE),
    )
    async def list_rag_documents(
        request: Request,
        conv_id: str,
        limit: int = Query(
            default=_DEFAULT_RAG_DOCUMENTS_PAGE_SIZE,
            ge=0,
            le=_MAX_RAG_DOCUMENTS_PAGE_SIZE,
        ),
        offset: int = Query(default=0, ge=0),
        include_documents: bool = Query(default=True),
        current_user: CurrentUser = Depends(get_current_user),
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> Response:
        user_id = require_user_id(request, current_user)
        rag_engine = require_rag_engine(request, api_context)
        resolved_id = await rag_engine.resolve_conv_id_for_user(conv_id, user_id)
        counts = await api_context.dependencies.database_files.get_rag_counts_for_conversation_with_active_links(
            resolved_id,
            user_id,
        )
        if not isinstance(counts, dict):
            raise_server_error(request, "RAG counts payload is invalid.")
        document_count_value = counts.get("document_count")
        chunk_count_value = counts.get("chunk_count")
        if not is_strict_int(document_count_value):
            raise_server_error(request, "RAG document count is invalid.")
        if not is_strict_int(chunk_count_value):
            raise_server_error(request, "RAG chunk count is invalid.")
        document_count = document_count_value
        chunk_count = chunk_count_value
        status_counts: dict[str, int] = {}
        for key in RAG_DOCUMENT_STATUS_COUNT_KEYS:
            value = counts.get(key)
            if not is_strict_int(value):
                raise_server_error(request, f"RAG status count is invalid: {key}.")
            status_counts[key] = value
        response_payload: JSONDict = {
            "conv_id": resolved_id,
            "count": max(0, int(document_count)),
            "chunk_count": max(0, int(chunk_count)),
            "status_counts": status_counts,
            "limit": limit,
            "offset": offset,
        }
        if include_documents:
            documents_raw = await api_context.dependencies.database_files.get_rag_documents_for_conversation_with_active_links(
                resolved_id,
                user_id,
                offset=offset,
                limit=limit,
            )
            documents: list[JSONDict] = []
            for item in documents_raw:
                normalized = normalize_for_json(item)
                document = coerce_json_dict(normalized)
                if document is None:
                    raise_server_error(request, "RAG document payload is not JSON.")
                documents.append(document)
            response_payload["documents"] = documents
        return JSONResponse(content=response_payload)
