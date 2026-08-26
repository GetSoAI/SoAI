"""SoAI - MCP worker web-fetch ingest processor [backend/mcp/worker/processors/web_fetch_ingest.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.config.numeric import require_strict_int_at_least
from core.errors.exceptions import ValidationError
from mcp.rag.scraper.text_formatting import resolve_extract_mode_content, truncate_text
from mcp.worker.processing.durable_job_payloads import lease_identity_from_job_payload
from mcp.worker.processors.chunk_embed import process_chunk_embed_store
from mcp.worker.processors.web_fetch_ingest_job import parse_web_fetch_ingest_job
from mcp.worker.processors.web_fetch_ingest_limits import (
    build_bounded_immediate_context,
    resolve_fetch_context_limits,
    truncate_at_boundary,
)
from mcp.worker.processors.web_fetch_ingest_retrieval import search_document_context
from mcp.worker.rag_document_status_flow import update_worker_rag_document_status

if TYPE_CHECKING:
    from core.concurrency.protocols import CancellationTokenProtocol
    from core.types.json import JSONDict
    from mcp.worker.internal_protocols import MCPWorkerProtocol

__all__ = (
    "process_web_fetch_ingest",
    "trim_fetched_content_for_ingestion",
)

_CONTENT_MAX_CHARS_KEY = "TOOLS.RAG.WEB.CONTENT_MAX_CHARS"
_CONTENT_TRIM_MODE_KEY = "TOOLS.RAG.WEB.CONTENT_TRIM_MODE"
_DEFAULT_CONTENT_MAX_CHARS = 120000
_DEFAULT_CONTENT_TRIM_MODE = "sentence"
_VALID_CONTENT_TRIM_MODES = frozenset(("sentence", "hard"))


def _resolve_content_max_chars(worker: MCPWorkerProtocol) -> int:
    return require_strict_int_at_least(
        worker.config.get_int(_CONTENT_MAX_CHARS_KEY),
        key=_CONTENT_MAX_CHARS_KEY,
        minimum=1,
    )


def _resolve_content_trim_mode(worker: MCPWorkerProtocol) -> str:
    value = worker.config.get(_CONTENT_TRIM_MODE_KEY, _DEFAULT_CONTENT_TRIM_MODE)
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(
            f"Invalid configuration: {_CONTENT_TRIM_MODE_KEY} must be a non-empty string",
        )
    mode = value.strip().lower()
    if mode not in _VALID_CONTENT_TRIM_MODES:
        raise ValidationError(
            f"Invalid configuration: {_CONTENT_TRIM_MODE_KEY} must be one of: sentence, hard",
        )
    return mode


def trim_fetched_content_for_ingestion(
    worker: MCPWorkerProtocol,
    content: str,
) -> tuple[str, dict[str, int | bool]]:
    max_chars = _resolve_content_max_chars(worker)
    trim_mode = _resolve_content_trim_mode(worker)
    original_chars = len(content)
    if original_chars <= max_chars:
        return (
            content,
            {
                "original_chars": original_chars,
                "ingested_chars": original_chars,
                "max_content_chars": max_chars,
                "truncated": False,
            },
        )
    if trim_mode == "hard":
        trimmed = content[:max_chars].rstrip()
    else:
        trimmed = truncate_at_boundary(content, max_chars)
    return (
        trimmed,
        {
            "original_chars": original_chars,
            "ingested_chars": len(trimmed),
            "max_content_chars": max_chars,
            "truncated": len(trimmed) < original_chars,
        },
    )


async def process_web_fetch_ingest(
    self: MCPWorkerProtocol,
    job: JSONDict,
    task_id: str,
    token: CancellationTokenProtocol | None = None,
) -> JSONDict:
    limits = resolve_fetch_context_limits(self)
    ingest_job = parse_web_fetch_ingest_job(job, limits)
    job_id, lease_token = lease_identity_from_job_payload(job)
    await self.send_progress(task_id, 5, f"Fetching URL: {ingest_job.url[:60]}...")
    await update_worker_rag_document_status(
        self,
        document_id=ingest_job.document_id,
        status="fetching",
        job_id=job_id,
        lease_token=lease_token,
    )
    fetched = await self.mcp_search.fetch_url(
        ingest_job.url,
        user_id=ingest_job.user_id,
        task_id=task_id,
        progress_start=5,
        progress_end=20,
    )
    await self.send_progress(task_id, 20, "URL fetched. Processing content...")
    content_for_ingestion, ingest_limits = trim_fetched_content_for_ingestion(self, fetched.content)
    content_for_return, returned_content_type = resolve_extract_mode_content(
        content=content_for_ingestion,
        content_type=fetched.content_type,
        source_html=fetched.source_html,
        extract_mode=ingest_job.return_extract_mode,
    )
    truncated_content, truncated = truncate_text(
        content_for_return,
        max_chars=ingest_job.return_max_chars,
    )
    chunks_created = await process_chunk_embed_store(
        self,
        ingest_job.document_id,
        ingest_job.conv_id,
        content_for_ingestion,
        ingest_job.chunk_size,
        ingest_job.chunk_overlap,
        ingest_job.embedding_model,
        task_id,
        ingest_job.user_id,
        ingest_job.chunking_strategy,
        token=token,
        job_id=job_id,
        lease_token=lease_token,
    )
    await self.check_cancellation(task_id, "web_fetch_ingest_post_ingest", token=token)
    query = ingest_job.focus_query
    search_result = await search_document_context(
        self,
        conv_id=ingest_job.conv_id,
        document_id=ingest_job.document_id,
        query=query,
        top_k=ingest_job.top_k,
        similarity_threshold=ingest_job.similarity_threshold,
        retrieval_strategy=ingest_job.retrieval_strategy,
        user_id=ingest_job.user_id,
        embedding_model=ingest_job.embedding_model,
        task_id=task_id,
        token=token,
    )
    await self.check_cancellation(task_id, "web_fetch_ingest_post_retrieval", token=token)
    immediate_context, output_limits = build_bounded_immediate_context(
        limits=limits,
        query=query,
        retrieval_strategy=ingest_job.retrieval_strategy,
        search_result=search_result,
    )
    return {
        "chunks_created": chunks_created,
        "fetched_content_type": fetched.content_type,
        "fetched_title": fetched.title or "",
        "fetched_source_url": fetched.source_url or ingest_job.url,
        "content": truncated_content,
        "content_type": returned_content_type,
        "extract_mode": ingest_job.return_extract_mode,
        "truncated": truncated,
        "max_chars": ingest_job.return_max_chars,
        "length": len(truncated_content),
        "raw_length": len(content_for_return),
        "page_count": fetched.page_count,
        "immediate_context": immediate_context,
        "output_limits": output_limits,
        "ingest_limits": ingest_limits,
    }
