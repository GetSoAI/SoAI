"""SoAI - MCP RAG ingestion cache fulfillment [backend/mcp/rag/ingestion_cache.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exceptions import SoAIError
from core.tasks.enums import TaskStatus
from core.tasks.task_cancellation import cancel
from core.tasks.type_catalog import TASK_TYPE_RAG_WEB_FETCH_INGEST
from core.timing.epoch import epoch_ms
from core.types.json import JSONDict
from mcp.progress_reporting import create_rag_task
from mcp.rag.internal_protocols import (
    CreateRagTaskProtocol,
    MCPRAGInternalProtocol,
    SearchDocumentContextProtocol,
)
from mcp.rag.request_models import WebFetchIngestRequest
from mcp.rag.scraper.text_formatting import resolve_extract_mode_content, truncate_text
from mcp.rag.scraper.url_validation import generate_url_variants
from mcp.worker.processors import web_fetch_ingest_retrieval
from mcp.worker.processors.web_fetch_ingest_limits import (
    build_bounded_immediate_context,
    resolve_fetch_context_limits,
)

__all__ = ("try_web_fetch_ingest_cache_fulfillment",)


async def try_web_fetch_ingest_cache_fulfillment(
    *,
    rag_service: MCPRAGInternalProtocol,
    request: WebFetchIngestRequest,
    create_rag_task_factory: CreateRagTaskProtocol = create_rag_task,
    search_document_context: SearchDocumentContextProtocol = (
        web_fetch_ingest_retrieval.search_document_context
    ),
) -> JSONDict | None:
    url_cache_enabled = rag_service.config.get_bool("TOOLS.RAG.WEB.URL_CACHE.ENABLED")
    url_cache_ttl_sec = max(0, int(rag_service.config.get_int("TOOLS.RAG.WEB.URL_CACHE.TTL_SEC")))
    if not url_cache_enabled or url_cache_ttl_sec <= 0:
        return None
    url_variants = generate_url_variants(request.canonical_url)
    created_at_min_ms = epoch_ms() - (url_cache_ttl_sec * 1000)
    cached = (
        await rag_service.database_files.find_recent_completed_rag_document_by_source_url_cache(
            request.conv_id,
            url_variants,
            created_at_min_ms,
            chunking_strategy=request.chunking_strategy,
            chunk_size=request.chunk_size,
            chunk_overlap=request.chunk_overlap,
            embedding_model=request.embedding_model,
        )
    )
    if not cached:
        return None
    cached_document_id = str(cached.get("id") or "").strip()
    if not cached_document_id:
        return None
    task = await create_rag_task_factory(
        rag_service.task_registry,
        task_type=TASK_TYPE_RAG_WEB_FETCH_INGEST,
        user_id=request.user_id,
        conv_id=request.conv_id,
        status=TaskStatus.PENDING,
        progress_total=100,
        metadata={"document_id": cached_document_id, "url": request.canonical_url},
    )
    cached_task_id = task.task_id
    try:
        fetched = await rag_service.mcp_search.fetch_url(
            request.canonical_url,
            user_id=request.user_id,
            task_id=cached_task_id,
            progress_start=0,
            progress_end=0,
        )
        search_result = await search_document_context(
            rag_service.worker,
            conv_id=request.conv_id,
            document_id=cached_document_id,
            query=request.normalized_focus_query,
            top_k=request.top_k,
            similarity_threshold=request.similarity_threshold,
            retrieval_strategy=request.normalized_strategy,
            user_id=request.user_id,
            embedding_model=request.embedding_model,
            task_id=cached_task_id,
            token=None,
        )
        immediate_context, output_limits = build_bounded_immediate_context(
            limits=resolve_fetch_context_limits(rag_service.worker),
            query=request.normalized_focus_query,
            retrieval_strategy=request.normalized_strategy,
            search_result=search_result,
        )
        content, content_type = resolve_extract_mode_content(
            content=fetched.content,
            content_type=fetched.content_type,
            source_html=fetched.source_html,
            extract_mode=request.normalized_return_extract_mode,
        )
        content, truncated = truncate_text(content, max_chars=request.return_max_chars)
        await rag_service.worker.complete_task(
            cached_task_id,
            result={
                "chunks_created": 0,
                "fetched_content_type": "cache",
                "fetched_title": "",
                "fetched_source_url": str(cached.get("source_url") or request.canonical_url),
                "content": content,
                "content_type": content_type,
                "extract_mode": request.normalized_return_extract_mode,
                "truncated": truncated,
                "max_chars": request.return_max_chars,
                "length": len(content),
                "raw_length": len(fetched.content),
                "page_count": fetched.page_count,
                "immediate_context": immediate_context,
                "output_limits": output_limits,
            },
            message="Cache hit",
        )
    except (SoAIError, RuntimeError, OSError, TypeError, ValueError) as exception:
        await cancel(rag_service.task_registry, cached_task_id, reason=str(exception))
        raise
    return {
        "document_id": cached_document_id,
        "task_id": cached_task_id,
        "status": "queued",
    }
