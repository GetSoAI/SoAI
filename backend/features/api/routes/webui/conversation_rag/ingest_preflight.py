"""SoAI - Shared conversation RAG ingest preflight [backend/features/api/routes/webui/conversation_rag/ingest_preflight.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from features.api.routes.webui.rag_dependencies import require_rag_engine
from features.api.runtime.errors import raise_invalid_request

if TYPE_CHECKING:
    from fastapi import Request

    from core.mcp.protocols_rag import MCPRAGProtocol
    from features.api.runtime.context import ApiContext

__all__ = ("resolve_conversation_rag_ingest_preflight",)


async def resolve_conversation_rag_ingest_preflight(
    *,
    request: Request,
    api_context: ApiContext,
    conv_id: str,
    user_id: int,
    reindex_error_verb: str,
) -> tuple[MCPRAGProtocol, str]:
    rag_engine = require_rag_engine(request, api_context)
    resolved_conv_id = await rag_engine.resolve_conv_id_for_user(conv_id, user_id)
    if await rag_engine.worker.reindex_locks.is_in_progress(resolved_conv_id):
        raise_invalid_request(
            request,
            f"Cannot {reindex_error_verb} while reindex is in progress for conversation {resolved_conv_id}.",
        )
    return rag_engine, resolved_conv_id
