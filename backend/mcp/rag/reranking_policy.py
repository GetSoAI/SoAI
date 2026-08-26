"""SoAI - RAG reranking policy helpers shared across search paths [backend/mcp/rag/reranking_policy.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exception_logging import log_handled_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.protocols import LoggerProtocol
from mcp.rag.configuration import get_rag_config_metadata
from mcp.storage.reranking import rerank_results

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from mcp.rag.internal_protocols import MCPRAGSearchContextProtocol

__all__ = ("rerank_if_enabled",)


async def rerank_if_enabled(
    *,
    context: MCPRAGSearchContextProtocol,
    logger: LoggerProtocol,
    conv_id: str,
    query: str,
    results: list[JSONDict],
    failure_log_message: str,
    operation: str,
    failure_details: JSONDict,
) -> list[JSONDict]:
    rerank_config = await get_rag_config_metadata(context, conv_id)
    if not (rerank_config.get("rerank_enabled") and results):
        return results
    try:
        return await rerank_results(context.mcp_search.runtime_flags, query, results, rerank_config)
    except RECOVERABLE_EXCEPTIONS as exception:
        log_handled_exception(
            logger,
            exception,
            message="Reranking failed; returning un-reranked results (non-critical).",
            operation=operation,
            details={**dict(failure_details), "failure_log_message": failure_log_message},
            level="debug",
        )
        return results
