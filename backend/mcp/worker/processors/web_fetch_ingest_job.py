"""SoAI - MCP worker web-fetch ingest job validation [backend/mcp/worker/processors/web_fetch_ingest_job.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.rag.parameter_validation import validate_chunking_window
from core.rag.web_fetch_ingest_validation import (
    require_web_fetch_chunking_strategy,
    require_web_fetch_int,
    require_web_fetch_non_empty_str,
    require_web_fetch_retrieval_strategy,
    require_web_fetch_return_extract_mode,
    require_web_fetch_return_max_chars,
    require_web_fetch_similarity_threshold,
    require_web_fetch_top_k,
    resolve_web_fetch_focus_query,
    resolve_web_fetch_user_id,
)
from mcp.worker.processors.web_fetch_ingest_limits import FetchContextLimits

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "WebFetchIngestJob",
    "parse_web_fetch_ingest_job",
)


@dataclass(frozen=True, slots=True)
class WebFetchIngestJob:
    url: str
    focus_query: str
    document_id: str
    conv_id: str
    retrieval_strategy: str
    top_k: int
    similarity_threshold: float
    chunk_size: int
    chunk_overlap: int
    embedding_model: str
    chunking_strategy: str
    return_extract_mode: str
    return_max_chars: int
    user_id: int


def parse_web_fetch_ingest_job(job: JSONDict, limits: FetchContextLimits) -> WebFetchIngestJob:
    chunk_size = require_web_fetch_int(
        job.get("chunk_size"),
        "Job missing valid chunk_size for web_fetch_ingest",
    )
    chunk_overlap = require_web_fetch_int(
        job.get("chunk_overlap"),
        "Job missing valid chunk_overlap for web_fetch_ingest",
    )
    chunking_strategy = require_web_fetch_chunking_strategy(job.get("chunking_strategy"))
    validate_chunking_window(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        chunking_strategy=chunking_strategy,
    )
    return WebFetchIngestJob(
        url=require_web_fetch_non_empty_str(
            job.get("url"),
            "Job missing valid url for web_fetch_ingest",
        ),
        focus_query=resolve_web_fetch_focus_query(job.get("focus_query")),
        document_id=require_web_fetch_non_empty_str(
            job.get("document_id"),
            "Job missing valid document_id for web_fetch_ingest",
        ),
        conv_id=require_web_fetch_non_empty_str(
            job.get("conv_id"),
            "Job missing valid conv_id for web_fetch_ingest",
        ),
        retrieval_strategy=require_web_fetch_retrieval_strategy(job.get("retrieval_strategy")),
        top_k=require_web_fetch_top_k(job.get("top_k"), limits.max_top_k),
        similarity_threshold=require_web_fetch_similarity_threshold(
            job.get("similarity_threshold"),
        ),
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        embedding_model=require_web_fetch_non_empty_str(
            job.get("embedding_model"),
            "Job missing valid embedding_model for web_fetch_ingest",
        ),
        chunking_strategy=chunking_strategy,
        return_extract_mode=require_web_fetch_return_extract_mode(job.get("return_extract_mode")),
        return_max_chars=require_web_fetch_return_max_chars(job.get("return_max_chars")),
        user_id=resolve_web_fetch_user_id(job.get("user_id")),
    )
