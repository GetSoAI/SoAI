"""SoAI - Durable RAG job read queries [backend/database/repositories/files/rag_job_reads.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import aiosqlite

from core.files.database_types import RAGProcessingJobRecord
from database.core.query_execution import query_to_dicts
from database.repositories.files.rag_job_rows import (
    RAG_PROCESSING_JOB_COLUMNS,
    parse_rag_processing_job_row,
)

__all__ = (
    "get_rag_processing_job_query",
    "list_claimable_rag_processing_jobs_query",
)


async def get_rag_processing_job_query(
    database: aiosqlite.Connection,
    job_id: str,
) -> RAGProcessingJobRecord | None:
    rows = await query_to_dicts(
        database,
        f"SELECT {RAG_PROCESSING_JOB_COLUMNS} FROM rag_processing_jobs WHERE job_id = ?",
        (job_id,),
    )
    if not rows:
        return None
    return parse_rag_processing_job_row(rows[0])


async def list_claimable_rag_processing_jobs_query(
    database: aiosqlite.Connection,
    *,
    now_ms: int,
    limit: int,
) -> list[RAGProcessingJobRecord]:
    rows = await query_to_dicts(
        database,
        f"""
        SELECT {RAG_PROCESSING_JOB_COLUMNS}
        FROM rag_processing_jobs
        WHERE status IN ('queued', 'retryable')
           OR (status = 'running' AND lease_expires_at_ms IS NOT NULL AND lease_expires_at_ms < ?)
        ORDER BY updated_at_ms ASC, created_at_ms ASC
        LIMIT ?
        """,
        (now_ms, max(1, int(limit))),
    )
    return [parse_rag_processing_job_row(row) for row in rows]
