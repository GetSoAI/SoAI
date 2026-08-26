"""SoAI - MCP worker processing queue job type constants [backend/mcp/worker/processing/job_types.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

__all__ = (
    "DOCUMENT_UPLOAD_JOB_TYPE",
    "RAG_DOCUMENT_JOB_TYPES",
    "RAG_PROCESSING_JOB_TYPES",
    "REINDEX_JOB_TYPE",
    "WEB_FETCH_INGEST_JOB_TYPE",
)

DOCUMENT_UPLOAD_JOB_TYPE: str = "document_upload"
WEB_FETCH_INGEST_JOB_TYPE: str = "web_fetch_ingest"
REINDEX_JOB_TYPE: str = "reindex"
RAG_DOCUMENT_JOB_TYPES: frozenset[str] = frozenset(
    (DOCUMENT_UPLOAD_JOB_TYPE, WEB_FETCH_INGEST_JOB_TYPE),
)
RAG_PROCESSING_JOB_TYPES: frozenset[str] = frozenset(
    (DOCUMENT_UPLOAD_JOB_TYPE, WEB_FETCH_INGEST_JOB_TYPE, REINDEX_JOB_TYPE),
)
