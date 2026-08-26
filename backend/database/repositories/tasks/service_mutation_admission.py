"""SoAI - Database task mutation admission service [backend/database/repositories/tasks/service_mutation_admission.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.database.mutation_requests import (
    MutationAdmissionOutcome,
    MutationAdmissionRequest,
    MutationClaim,
    MutationRecoveryCandidate,
    MutationRecoveryRequiredAdmission,
)
from core.database.task_requests import CreateUnifiedTaskRequest
from core.errors.exceptions import StateError
from database.repositories.tasks.internal_protocols import (
    DatabaseTasksQueueCoreOwnerProtocol,
)
from database.repositories.tasks.mutation_admission import sync_accept_mutation_task
from database.repositories.tasks.mutation_lifecycle import (
    sync_advance_mutation_execution,
    sync_claim_mutation,
    sync_claim_next_mutation,
    sync_mutation_requires_fenced_finalization,
    sync_renew_mutation_claim,
    sync_validate_mutation_claim,
)
from database.repositories.tasks.mutation_recovery import (
    sync_quarantine_exhausted_mutations,
    sync_query_expired_mutation_recovery_candidates,
    sync_query_recovery_required_admissions,
)

__all__ = (
    "accept_mutation_task",
    "advance_mutation_execution",
    "claim_mutation",
    "claim_next_mutation",
    "mutation_requires_fenced_finalization",
    "quarantine_exhausted_mutations",
    "query_expired_mutation_recovery_candidates",
    "query_recovery_required_admissions",
    "release_mutation_recovery",
    "renew_mutation_claim",
    "validate_mutation_claim",
)


async def advance_mutation_execution(
    self: DatabaseTasksQueueCoreOwnerProtocol,
    task_id: str,
    fencing_token: int,
    *,
    expected_phase: str,
    next_phase: str,
    execution_state: str,
    now_ms: int,
) -> bool:
    return await self.core.writer.queue_write_operation(
        sync_advance_mutation_execution,
        task_id,
        fencing_token,
        expected_phase,
        next_phase,
        execution_state,
        now_ms,
    )


async def accept_mutation_task(
    self: DatabaseTasksQueueCoreOwnerProtocol,
    task_request: CreateUnifiedTaskRequest,
    admission_request: MutationAdmissionRequest,
    *,
    server_time_ms: int,
) -> MutationAdmissionOutcome:
    return await self.core.writer.queue_write_operation(
        sync_accept_mutation_task,
        task_request,
        admission_request,
        server_time_ms,
        (None if self.mutation_storage is None else self.mutation_storage.admission_hook),
    )


async def claim_mutation(
    self: DatabaseTasksQueueCoreOwnerProtocol,
    request_id: str,
    worker_id: str,
    *,
    now_ms: int,
    lease_duration_ms: int,
) -> MutationClaim | None:
    return await self.core.writer.queue_write_operation(
        sync_claim_mutation,
        request_id,
        worker_id,
        now_ms,
        lease_duration_ms,
    )


async def claim_next_mutation(
    self: DatabaseTasksQueueCoreOwnerProtocol,
    worker_id: str,
    *,
    now_ms: int,
    lease_duration_ms: int,
) -> MutationClaim | None:
    return await self.core.writer.queue_write_operation(
        sync_claim_next_mutation,
        worker_id,
        now_ms,
        lease_duration_ms,
    )


async def query_expired_mutation_recovery_candidates(
    self: DatabaseTasksQueueCoreOwnerProtocol,
    *,
    now_ms: int,
    limit: int,
) -> tuple[MutationRecoveryCandidate, ...]:
    return await self.core.writer.queue_write_operation(
        sync_query_expired_mutation_recovery_candidates,
        now_ms,
        limit,
    )


async def quarantine_exhausted_mutations(
    self: DatabaseTasksQueueCoreOwnerProtocol,
    *,
    now_ms: int,
) -> tuple[str, ...]:
    return await self.core.writer.queue_write_operation(
        sync_quarantine_exhausted_mutations,
        now_ms,
    )


async def query_recovery_required_admissions(
    self: DatabaseTasksQueueCoreOwnerProtocol,
    *,
    operation_type: str | None = None,
) -> tuple[MutationRecoveryRequiredAdmission, ...]:
    return await self.core.writer.queue_write_operation(
        sync_query_recovery_required_admissions,
        operation_type,
    )


async def release_mutation_recovery(
    self: DatabaseTasksQueueCoreOwnerProtocol,
    request_id: str,
    target_identity: str,
    *,
    now_ms: int,
) -> bool:
    if self.mutation_storage is None:
        raise StateError("Edition mutation storage is unavailable.")
    recovery_release = self.mutation_storage.recovery_release
    if recovery_release is None:
        raise StateError("Edition mutation recovery release is unavailable.")
    return await self.core.writer.queue_write_operation(
        recovery_release,
        request_id,
        target_identity,
        now_ms,
    )


async def renew_mutation_claim(
    self: DatabaseTasksQueueCoreOwnerProtocol,
    request_id: str,
    fencing_token: int,
    worker_id: str,
    *,
    now_ms: int,
    lease_duration_ms: int,
) -> bool:
    return await self.core.writer.queue_write_operation(
        sync_renew_mutation_claim,
        request_id,
        fencing_token,
        worker_id,
        now_ms,
        lease_duration_ms,
    )


async def mutation_requires_fenced_finalization(
    self: DatabaseTasksQueueCoreOwnerProtocol,
    task_id: str,
) -> bool:
    return await self.core.writer.queue_write_operation(
        sync_mutation_requires_fenced_finalization,
        task_id,
    )


async def validate_mutation_claim(
    self: DatabaseTasksQueueCoreOwnerProtocol,
    task_id: str,
    fencing_token: int,
    *,
    now_ms: int,
) -> bool:
    return await self.core.writer.queue_write_operation(
        sync_validate_mutation_claim,
        task_id,
        fencing_token,
        now_ms,
    )
