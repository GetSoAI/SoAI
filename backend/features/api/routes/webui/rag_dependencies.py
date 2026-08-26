"""SoAI - RAG engine dependency injection for WebUI routes [backend/features/api/routes/webui/rag_dependencies.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from fastapi import Request

from core.errors.external_service_exception import MCPError
from core.mcp.protocols_rag import MCPRAGProtocol
from features.api.runtime.context import ApiContext
from features.api.runtime.errors import raise_service_unavailable

__all__ = ("require_rag_engine",)


def require_rag_engine(request: Request, api_context: ApiContext) -> MCPRAGProtocol:
    try:
        return api_context.dependencies.mcp_server.registration.require_rag()
    except MCPError:
        raise_service_unavailable(
            request,
            "RAG engine is not available.",
        )
