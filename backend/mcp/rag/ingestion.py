"""SoAI - MCP RAG ingestion entrypoints [backend/mcp/rag/ingestion.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.logging.trace import get_logger
from core.types.json import JSONDict
from mcp.progress_reporting import create_rag_task
from mcp.rag.embedding_model import prepare_ingest_context
from mcp.rag.ingestion_cache import try_web_fetch_ingest_cache_fulfillment
from mcp.rag.ingestion_queue import enqueue_web_fetch_ingest_job
from mcp.rag.ingestion_validation import normalize_and_validate_web_fetch_ingest_request
from mcp.rag.internal_protocols import MCPRAGInternalProtocol
from mcp.rag.request_models import WebFetchIngestRequest
from mcp.rag.scraper.url_validation import canonicalize_fetch_cache_url
from mcp.worker.processors.web_fetch_ingest_retrieval import search_document_context

__all__ = (
    "create_rag_task",
    "prepare_ingest_context",
    "search_document_context",
    "web_fetch_ingest",
)

LOGGER_NAME = "SoAI.mcp.rag.ingestion"


async def web_fetch_ingest(
    rag_service: MCPRAGInternalProtocol,
    conv_id: str,
    user_id: int,
    url: str,
    focus_query: str,
    retrieval_strategy: str,
    top_k: int,
    similarity_threshold: float,
    chunk_size: int = 500,
    chunk_overlap: int = 100,
    embedding_model_id: str | None = None,
    chunking_strategy: str = "token_based",
    return_extract_mode: str = "markdown",
    return_max_chars: int = 50_000,
) -> JSONDict:
    logger = get_logger(LOGGER_NAME)
    (
        normalized_focus_query,
        normalized_strategy,
        normalized_return_extract_mode,
        normalized_return_max_chars,
    ) = normalize_and_validate_web_fetch_ingest_request(
        rag_service=rag_service,
        focus_query=focus_query,
        retrieval_strategy=retrieval_strategy,
        top_k=top_k,
        similarity_threshold=similarity_threshold,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        chunking_strategy=chunking_strategy,
        return_extract_mode=return_extract_mode,
        return_max_chars=return_max_chars,
    )
    conv_id, resolved_embedding_model = await prepare_ingest_context(
        rag_service,
        conv_id,
        user_id,
        embedding_model_id,
        check_reindex=True,
        reindex_error_verb="ingest URL",
    )
    request = WebFetchIngestRequest(
        conv_id=conv_id,
        user_id=user_id,
        canonical_url=canonicalize_fetch_cache_url(url),
        normalized_focus_query=normalized_focus_query,
        normalized_strategy=normalized_strategy,
        top_k=top_k,
        similarity_threshold=float(similarity_threshold),
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        embedding_model=resolved_embedding_model,
        chunking_strategy=chunking_strategy,
        normalized_return_extract_mode=normalized_return_extract_mode,
        return_max_chars=normalized_return_max_chars,
    )
    cached_response = await try_web_fetch_ingest_cache_fulfillment(
        rag_service=rag_service,
        request=request,
        create_rag_task_factory=create_rag_task,
        search_document_context=search_document_context,
    )
    if cached_response is not None:
        return cached_response
    return await enqueue_web_fetch_ingest_job(
        rag_service=rag_service,
        request=request,
        logger=logger,
    )
