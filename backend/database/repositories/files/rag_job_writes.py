"""SoAI - Durable RAG job write transactions [backend/database/repositories/files/rag_job_writes.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.rag.job_operations import (
    RAGJobClaimOutcome,
    RAGJobClaimResult,
    RAGJobCreateRequest,
    RAGJobFinalizeRequest,
    RAGJobLeaseRequest,
    RAGJobStatus,
)
from core.serialization.json import serialize_json_compact_stable_strict
from core.types.json import is_json_dict
from database.core.query_execution import sync_fetch_changes_count, sync_fetch_one_as_dict
from database.repositories.files.rag_job_rows import (
    RAG_PROCESSING_JOB_COLUMNS,
    parse_rag_processing_job_row,
)

if TYPE_CHECKING:
    from core.files.database_types import RAGProcessingJobRecord

__all__ = (
    "sync_acquire_rag_job_lease",
    "sync_create_rag_job",
    "sync_finalize_rag_job",
    "sync_release_rag_job_lease",
    "sync_renew_rag_job_lease",
)

_TERMINAL_JOB_STATUSES = frozenset(
    (RAGJobStatus.COMPLETED.value, RAGJobStatus.FAILED.value, RAGJobStatus.CANCELLED.value),
)


def _select_job(conn: sqlite3.Connection, job_id: str) -> RAGProcessingJobRecord | None:
    row = sync_fetch_one_as_dict(
        conn.execute(
            f"SELECT {RAG_PROCESSING_JOB_COLUMNS} FROM rag_processing_jobs WHERE job_id = ?",
            (job_id,),
        ),
    )
    if row is None:
        return None
    return parse_rag_processing_job_row(row)


def sync_create_rag_job(conn: sqlite3.Connection, request: RAGJobCreateRequest) -> bool:
    if not is_json_dict(request.payload):
        raise ValidationError("RAG job payload must be a JSON object.")
    conn.execute(
        """
        INSERT INTO rag_processing_jobs (
            job_id, job_type, conv_id, user_id, document_id, task_id, status, payload_json,
            spool_path, lease_token, lease_owner, lease_expires_at_ms, attempt_count,
            last_error, created_at_ms, updated_at_ms, completed_at_ms
        ) VALUES (?, ?, ?, ?, ?, ?, 'queued', ?, ?, NULL, NULL, NULL, 0, NULL, ?, ?, NULL)
        """,
        (
            request.job_id,
            request.job_type,
            request.conv_id,
            request.user_id,
            request.document_id,
            request.task_id,
            serialize_json_compact_stable_strict(request.payload),
            request.spool_path,
            request.now_ms,
            request.now_ms,
        ),
    )
    return sync_fetch_changes_count(conn) > 0


def sync_acquire_rag_job_lease(
    conn: sqlite3.Connection,
    request: RAGJobLeaseRequest,
) -> RAGJobClaimOutcome:
    conn.execute(
        """
        UPDATE rag_processing_jobs
        SET status = 'running', lease_token = ?, lease_owner = ?, lease_expires_at_ms = ?,
            attempt_count = attempt_count + 1, updated_at_ms = ?
        WHERE job_id = ?
          AND (
              status IN ('queued', 'retryable')
              OR (
                  status = 'running'
                  AND lease_expires_at_ms IS NOT NULL
                  AND lease_expires_at_ms < ?
              )
          )
        """,
        (
            request.lease_token,
            request.lease_owner,
            request.lease_expires_at_ms,
            request.now_ms,
            request.job_id,
            request.now_ms,
        ),
    )
    if sync_fetch_changes_count(conn) > 0:
        return RAGJobClaimOutcome(RAGJobClaimResult.ACQUIRED, _select_job(conn, request.job_id))
    current = _select_job(conn, request.job_id)
    if current is None:
        return RAGJobClaimOutcome(RAGJobClaimResult.NOT_FOUND, None)
    if current["status"] in _TERMINAL_JOB_STATUSES:
        return RAGJobClaimOutcome(RAGJobClaimResult.TERMINAL, current)
    return RAGJobClaimOutcome(RAGJobClaimResult.BUSY, current)


def sync_renew_rag_job_lease(
    conn: sqlite3.Connection,
    job_id: str,
    lease_token: str,
    lease_expires_at_ms: int,
    now_ms: int,
) -> bool:
    conn.execute(
        """
        UPDATE rag_processing_jobs
        SET lease_expires_at_ms = ?, updated_at_ms = ?
        WHERE job_id = ? AND lease_token = ? AND status = 'running'
        """,
        (lease_expires_at_ms, now_ms, job_id, lease_token),
    )
    return sync_fetch_changes_count(conn) > 0


def sync_release_rag_job_lease(
    conn: sqlite3.Connection,
    job_id: str,
    lease_token: str,
    now_ms: int,
) -> None:
    conn.execute(
        """
        UPDATE rag_processing_jobs
        SET status = 'retryable', lease_token = NULL, lease_owner = NULL,
            lease_expires_at_ms = NULL, updated_at_ms = ?
        WHERE job_id = ? AND lease_token = ? AND status = 'running'
        """,
        (now_ms, job_id, lease_token),
    )


def sync_finalize_rag_job(conn: sqlite3.Connection, request: RAGJobFinalizeRequest) -> bool:
    if request.status not in (
        RAGJobStatus.COMPLETED,
        RAGJobStatus.FAILED,
        RAGJobStatus.CANCELLED,
    ):
        raise ValidationError(f"Invalid RAG terminal job status: {request.status.value}")
    conn.execute(
        """
        UPDATE rag_processing_jobs
        SET status = ?, last_error = ?, lease_token = NULL, lease_owner = NULL,
            lease_expires_at_ms = NULL, updated_at_ms = ?, completed_at_ms = ?
        WHERE job_id = ? AND lease_token = ? AND status = 'running'
          AND lease_expires_at_ms IS NOT NULL AND lease_expires_at_ms >= ?
        """,
        (
            request.status.value,
            request.error_message,
            request.now_ms,
            request.now_ms,
            request.job_id,
            request.lease_token,
            request.now_ms,
        ),
    )
    return sync_fetch_changes_count(conn) > 0
