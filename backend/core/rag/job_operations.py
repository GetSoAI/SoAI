"""SoAI - Durable RAG job operation records [backend/core/rag/job_operations.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.files.database_types import RAGProcessingJobRecord
    from core.types.json import JSONDict

__all__ = (
    "RAG_JOB_LEASE_LOST_DETAIL_KEY",
    "RAGDocumentStatusJobUpdateRequest",
    "RAGDocumentStatusUpdateRequest",
    "RAGJobClaimOutcome",
    "RAGJobClaimResult",
    "RAGJobCreateRequest",
    "RAGJobFinalizeRequest",
    "RAGJobLeaseRequest",
    "RAGJobStatus",
    "rag_job_lease_lost_details",
)

RAG_JOB_LEASE_LOST_DETAIL_KEY = "durable_rag_job_lease_lost"


def rag_job_lease_lost_details() -> JSONDict:
    return {RAG_JOB_LEASE_LOST_DETAIL_KEY: True}


class RAGJobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    RETRYABLE = "retryable"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class RAGJobClaimResult(StrEnum):
    ACQUIRED = "acquired"
    BUSY = "busy"
    NOT_FOUND = "not_found"
    TERMINAL = "terminal"


@dataclass(frozen=True, slots=True)
class RAGDocumentStatusUpdateRequest:
    doc_id: str
    status: str
    status_details: str | None = None
    content_hash: str | None = None
    total_chunks: int | None = None
    processed_chunks: int | None = None
    embedding_model: str | None = None
    effective_embedding_model: str | None = None
    embedding_dimensions: int | None = None
    error_message: str | None = None


@dataclass(frozen=True, slots=True)
class RAGDocumentStatusJobUpdateRequest:
    status_update: RAGDocumentStatusUpdateRequest
    job_id: str
    lease_token: str


@dataclass(frozen=True, slots=True)
class RAGJobCreateRequest:
    job_id: str
    job_type: str
    conv_id: str
    user_id: int
    document_id: str | None
    task_id: str
    payload: JSONDict
    spool_path: str | None
    now_ms: int


@dataclass(frozen=True, slots=True)
class RAGJobLeaseRequest:
    job_id: str
    lease_token: str
    lease_owner: str
    lease_expires_at_ms: int
    now_ms: int


@dataclass(frozen=True, slots=True)
class RAGJobFinalizeRequest:
    job_id: str
    lease_token: str
    status: RAGJobStatus
    error_message: str | None
    now_ms: int


@dataclass(frozen=True, slots=True)
class RAGJobClaimOutcome:
    result: RAGJobClaimResult
    job: RAGProcessingJobRecord | None
