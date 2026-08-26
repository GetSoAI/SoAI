"""SoAI - Durable mutation task persistence protocol [backend/core/database/protocols_mutation_tasks.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import Protocol

from core.database.mutation_requests import (
    MutationAdmissionOutcome,
    MutationAdmissionRequest,
    MutationClaim,
    MutationRecoveryCandidate,
    MutationRecoveryRequiredAdmission,
)
from core.database.task_requests import CreateUnifiedTaskRequest

__all__ = ("DatabaseMutationTasksProtocol",)


class DatabaseMutationTasksProtocol(Protocol):
    async def accept_mutation_task(
        self,
        task_request: CreateUnifiedTaskRequest,
        admission_request: MutationAdmissionRequest,
        *,
        server_time_ms: int,
    ) -> MutationAdmissionOutcome: ...

    async def claim_mutation(
        self,
        request_id: str,
        worker_id: str,
        *,
        now_ms: int,
        lease_duration_ms: int,
    ) -> MutationClaim | None: ...

    async def claim_next_mutation(
        self,
        worker_id: str,
        *,
        now_ms: int,
        lease_duration_ms: int,
    ) -> MutationClaim | None: ...

    async def mutation_requires_fenced_finalization(self, task_id: str) -> bool: ...

    async def query_expired_mutation_recovery_candidates(
        self,
        *,
        now_ms: int,
        limit: int,
    ) -> tuple[MutationRecoveryCandidate, ...]: ...

    async def quarantine_exhausted_mutations(
        self,
        *,
        now_ms: int,
    ) -> tuple[str, ...]: ...

    async def query_recovery_required_admissions(
        self,
        *,
        operation_type: str | None = None,
    ) -> tuple[MutationRecoveryRequiredAdmission, ...]: ...

    async def release_mutation_recovery(
        self,
        request_id: str,
        target_identity: str,
        *,
        now_ms: int,
    ) -> bool: ...

    async def renew_mutation_claim(
        self,
        request_id: str,
        fencing_token: int,
        worker_id: str,
        *,
        now_ms: int,
        lease_duration_ms: int,
    ) -> bool: ...

    async def validate_mutation_claim(
        self,
        task_id: str,
        fencing_token: int,
        *,
        now_ms: int,
    ) -> bool: ...

    async def advance_mutation_execution(
        self,
        task_id: str,
        fencing_token: int,
        *,
        expected_phase: str,
        next_phase: str,
        execution_state: str,
        now_ms: int,
    ) -> bool: ...
