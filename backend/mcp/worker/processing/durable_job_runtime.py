"""SoAI - Durable RAG worker lease runtime [backend/mcp/worker/processing/durable_job_runtime.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.errors.exceptions import SoAIError, StateError
from core.rag.job_operations import (
    RAG_JOB_LEASE_LOST_DETAIL_KEY,
    RAGJobClaimResult,
    RAGJobFinalizeRequest,
    RAGJobLeaseRequest,
    RAGJobStatus,
    rag_job_lease_lost_details,
)
from core.timing.durations import seconds_to_ms
from core.timing.epoch import epoch_ms
from core.types.json import is_json_dict
from mcp.worker.processing.job_parsing import ParsedProcessingJob

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from mcp.worker.internal_protocols import MCPWorkerProtocol

__all__ = (
    "DurableProcessingLease",
    "acquire_durable_processing_lease",
    "finalize_durable_processing_job",
    "is_durable_processing_lease_lost",
    "durable_processing_lease_ttl_seconds",
    "release_durable_processing_lease",
    "renew_durable_processing_lease",
)

_DEFAULT_LEASE_TTL_SECONDS = 900


@dataclass(frozen=True, slots=True)
class DurableProcessingLease:
    job_id: str
    lease_token: str
    payload: JSONDict
    parsed: ParsedProcessingJob


def durable_processing_lease_ttl_seconds(worker: MCPWorkerProtocol) -> int:
    ttl_seconds = worker.config.get_int("TOOLS.RAG.PROCESSING_JOB_LEASE_TTL_SEC")
    return ttl_seconds if ttl_seconds > 0 else _DEFAULT_LEASE_TTL_SECONDS


def _lease_expires_at_ms(worker: MCPWorkerProtocol) -> int:
    return int(epoch_ms()) + seconds_to_ms(durable_processing_lease_ttl_seconds(worker))


async def acquire_durable_processing_lease(
    worker: MCPWorkerProtocol,
    parsed: ParsedProcessingJob,
    *,
    worker_id: int,
) -> DurableProcessingLease | None:
    if parsed.job_id is None:
        return None
    lease_token = uuid.uuid4().hex
    now_ms = int(epoch_ms())
    outcome = await worker.database_files.acquire_rag_job_lease(
        RAGJobLeaseRequest(
            job_id=parsed.job_id,
            lease_token=lease_token,
            lease_owner=f"mcp-processing-worker-{worker_id}",
            lease_expires_at_ms=_lease_expires_at_ms(worker),
            now_ms=now_ms,
        ),
    )
    if outcome.result is not RAGJobClaimResult.ACQUIRED:
        return None
    job = outcome.job
    if job is None or not is_json_dict(job["payload"]):
        raise StateError(f"Durable RAG job has invalid payload: {parsed.job_id}")
    payload = dict(job["payload"])
    payload["job_id"] = parsed.job_id
    payload["lease_token"] = lease_token
    payload["task_id"] = job["task_id"]
    if job["spool_path"] is not None:
        payload["temp_file"] = job["spool_path"]
    reparsed = ParsedProcessingJob(
        payload=payload,
        task_id=job["task_id"],
        job_type=job["job_type"],
        temp_file=job["spool_path"],
        job_id=parsed.job_id,
        lease_token=lease_token,
    )
    return DurableProcessingLease(
        job_id=parsed.job_id,
        lease_token=lease_token,
        payload=payload,
        parsed=reparsed,
    )


async def release_durable_processing_lease(
    worker: MCPWorkerProtocol,
    lease: DurableProcessingLease | None,
) -> None:
    if lease is None:
        return
    await worker.database_files.release_rag_job_lease(
        lease.job_id,
        lease.lease_token,
        int(epoch_ms()),
    )


async def renew_durable_processing_lease(
    worker: MCPWorkerProtocol,
    *,
    job_id: str,
    lease_token: str,
) -> None:
    renewed = await worker.database_files.renew_rag_job_lease(
        job_id,
        lease_token,
        _lease_expires_at_ms(worker),
        int(epoch_ms()),
    )
    if not renewed:
        raise StateError(
            "RAG job lease is no longer current.",
            details=rag_job_lease_lost_details(),
        )


def is_durable_processing_lease_lost(error: SoAIError) -> bool:
    details = error.details
    if details is None:
        return False
    return details.get(RAG_JOB_LEASE_LOST_DETAIL_KEY) is True


async def finalize_durable_processing_job(
    worker: MCPWorkerProtocol,
    lease: DurableProcessingLease | None,
    *,
    status: RAGJobStatus,
    error_message: str | None,
) -> bool:
    if lease is None:
        return True
    return await worker.database_files.finalize_rag_processing_job(
        RAGJobFinalizeRequest(
            job_id=lease.job_id,
            lease_token=lease.lease_token,
            status=status,
            error_message=error_message,
            now_ms=int(epoch_ms()),
        ),
    )
