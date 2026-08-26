"""SoAI - WebUI per-conversation RAG search routes [backend/features/api/routes/webui/conversation_rag/search/search_routes.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from fastapi import Depends, Request
from starlette.responses import JSONResponse, Response

from core.state.access import AccessAction
from features.api.routes.webui.conversation_rag.config.normalization import (
    build_normalized_rag_config_response,
)
from features.api.routes.webui.rag_dependencies import require_rag_engine
from features.api.runtime.access_dependencies import require_action_dependencies
from features.api.runtime.container.api_routers import ApiRouters
from features.api.runtime.context import ApiContext, resolve_api_context
from features.api.runtime.current_user import CurrentUser, get_current_user
from features.api.schemas.rag import RAGSearchRequest

__all__ = ("register_routes",)


def register_routes(routers: ApiRouters) -> None:
    @routers.webui.post(
        "/conversations/{conv_id}/rag/search",
        dependencies=require_action_dependencies(AccessAction.RAG_USE),
    )
    async def search_rag(
        request: Request,
        conv_id: str,
        payload: RAGSearchRequest,
        current_user: CurrentUser = Depends(get_current_user),
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> Response:
        rag_engine = require_rag_engine(request, api_context)
        resolved_id = await rag_engine.resolve_conv_id_for_user(conv_id, current_user["id"])
        config = await api_context.dependencies.database_files.get_rag_config(resolved_id)
        normalized_config = build_normalized_rag_config_response(resolved_id, rag_engine, config)
        top_k = payload.top_k if payload.top_k is not None else normalized_config["top_k"]
        strategy = (
            payload.retrieval_strategy
            if payload.retrieval_strategy is not None
            else normalized_config["retrieval_strategy"]
        )
        threshold = (
            payload.similarity_threshold
            if payload.similarity_threshold is not None
            else normalized_config["similarity_threshold"]
        )
        result = await rag_engine.search(
            conv_id=resolved_id,
            query=payload.query,
            top_k=top_k,
            similarity_threshold=threshold,
            retrieval_strategy=strategy,
            user_id=current_user["id"],
        )
        return JSONResponse(content=result)
