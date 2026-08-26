"""SoAI - Durable RAG job methods for DatabaseFiles [backend/database/repositories/files/service_rag_jobs.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.rag.job_operations import (
    RAGDocumentStatusJobUpdateRequest,
    RAGJobClaimOutcome,
    RAGJobCreateRequest,
    RAGJobFinalizeRequest,
    RAGJobLeaseRequest,
)
from core.types.json import JSONDict
from database.repositories.files.internal_protocols import DatabaseFilesRagProtocol
from database.repositories.files.rag_chunks import sync_replace_rag_chunks_for_job
from database.repositories.files.rag_document_status_updates import (
    sync_update_rag_document_status_for_job,
)
from database.repositories.files.rag_job_writes import (
    sync_acquire_rag_job_lease,
    sync_create_rag_job,
    sync_finalize_rag_job,
    sync_release_rag_job_lease,
    sync_renew_rag_job_lease,
)
from database.repositories.files.rag_maintenance_locks import (
    sync_acquire_rag_maintenance_lock,
    sync_release_rag_maintenance_lock,
    sync_renew_rag_maintenance_lock,
)

__all__ = (
    "acquire_rag_job_lease",
    "acquire_rag_maintenance_lock",
    "create_rag_processing_job",
    "finalize_rag_processing_job",
    "release_rag_job_lease",
    "release_rag_maintenance_lock",
    "renew_rag_job_lease",
    "renew_rag_maintenance_lock",
    "replace_rag_chunks_for_job",
    "update_rag_document_status_for_job",
)


async def update_rag_document_status_for_job(
    self: DatabaseFilesRagProtocol,
    request: RAGDocumentStatusJobUpdateRequest,
) -> tuple[list[JSONDict], JSONDict | None]:
    return await self.core.writer.queue_write_operation(
        sync_update_rag_document_status_for_job,
        request,
    )


async def replace_rag_chunks_for_job(
    self: DatabaseFilesRagProtocol,
    *,
    job_id: str,
    lease_token: str,
    document_id: str,
    chunks: list[JSONDict],
) -> bool:
    return await self.core.writer.queue_write_operation(
        sync_replace_rag_chunks_for_job,
        job_id,
        lease_token,
        document_id,
        chunks,
    )


async def create_rag_processing_job(
    self: DatabaseFilesRagProtocol,
    request: RAGJobCreateRequest,
) -> bool:
    return await self.core.writer.queue_write_operation(
        sync_create_rag_job,
        request,
    )


async def acquire_rag_job_lease(
    self: DatabaseFilesRagProtocol,
    request: RAGJobLeaseRequest,
) -> RAGJobClaimOutcome:
    return await self.core.writer.queue_write_operation(
        sync_acquire_rag_job_lease,
        request,
    )


async def renew_rag_job_lease(
    self: DatabaseFilesRagProtocol,
    job_id: str,
    lease_token: str,
    lease_expires_at_ms: int,
    now_ms: int,
) -> bool:
    return await self.core.writer.queue_write_operation(
        sync_renew_rag_job_lease,
        job_id,
        lease_token,
        lease_expires_at_ms,
        now_ms,
    )


async def release_rag_job_lease(
    self: DatabaseFilesRagProtocol,
    job_id: str,
    lease_token: str,
    now_ms: int,
) -> None:
    await self.core.writer.queue_write_operation(
        sync_release_rag_job_lease,
        job_id,
        lease_token,
        now_ms,
    )


async def finalize_rag_processing_job(
    self: DatabaseFilesRagProtocol,
    request: RAGJobFinalizeRequest,
) -> bool:
    return await self.core.writer.queue_write_operation(
        sync_finalize_rag_job,
        request,
    )


async def acquire_rag_maintenance_lock(
    self: DatabaseFilesRagProtocol,
    *,
    conv_id: str,
    lock_type: str,
    owner_task_id: str,
    lease_token: str,
    lease_owner: str,
    lease_expires_at_ms: int,
    now_ms: int,
) -> bool:
    return await self.core.writer.queue_write_operation(
        sync_acquire_rag_maintenance_lock,
        conv_id,
        lock_type,
        owner_task_id,
        lease_token,
        lease_owner,
        lease_expires_at_ms,
        now_ms,
    )


async def release_rag_maintenance_lock(
    self: DatabaseFilesRagProtocol,
    *,
    conv_id: str,
    lease_token: str,
) -> None:
    await self.core.writer.queue_write_operation(
        sync_release_rag_maintenance_lock,
        conv_id,
        lease_token,
    )


async def renew_rag_maintenance_lock(
    self: DatabaseFilesRagProtocol,
    *,
    conv_id: str,
    lease_token: str,
    lease_expires_at_ms: int,
    now_ms: int,
) -> bool:
    return await self.core.writer.queue_write_operation(
        sync_renew_rag_maintenance_lock,
        conv_id,
        lease_token,
        lease_expires_at_ms,
        now_ms,
    )
