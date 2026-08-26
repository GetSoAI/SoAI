"""SoAI - Database tasks repository with query and lifecycle operations [backend/database/repositories/tasks/service.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from cryptography.fernet import Fernet

from core.database.task_requests import (
    CreateDurableInferenceTaskRequest,
    UnifiedTaskQueryRequest,
)
from core.mutations.storage_composition import MutationStorageComposition
from database.repositories.tasks import (
    active_queries,
    lifecycle,
    orchestrator_queue_acceptance,
    orchestrator_queue_scheduling_clock,
    queries,
)
from database.repositories.tasks.durable_acceptance_policy import (
    build_durable_acceptance_policy,
)
from database.repositories.tasks.service_active_queries import (
    count_running_orchestrated_inference_tasks_for_owner,
    query_active_cancellation_ids,
    query_active_tasks_by_type,
    query_active_tasks_for_cancellation_id,
)
from database.repositories.tasks.service_conversation_interactions import (
    claim_interaction_secret,
    consume_interaction_secret_after_tool_checkpoint,
    consume_interaction_secrets_after_turn_checkpoint,
    has_interaction_checkpoint,
    mark_interaction_secret_downstream_started,
)
from database.repositories.tasks.service_lifecycle import (
    cleanup_expired_unified_tasks,
    create_unified_task,
    delete_unified_task,
    finalize_unified_task,
    reconcile_terminal_background_responses,
    update_unified_task_status,
)
from database.repositories.tasks.service_mutation_admission import (
    accept_mutation_task,
    advance_mutation_execution,
    claim_mutation,
    claim_next_mutation,
    mutation_requires_fenced_finalization,
    quarantine_exhausted_mutations,
    query_expired_mutation_recovery_candidates,
    query_recovery_required_admissions,
    release_mutation_recovery,
    renew_mutation_claim,
    validate_mutation_claim,
)
from database.repositories.tasks.service_orchestrator_queue import (
    claim_orchestrator_queue_items,
    finalize_orchestrator_queue_item,
    get_unified_tasks_by_ids,
    mark_orchestrator_queue_item_prefetched_if_leased,
    mark_orchestrator_queue_item_running_if_leased,
    query_prefetched_orchestrated_task_ids,
    recover_expired_orchestrator_queue_items,
    release_orchestrator_queue_item_lease,
    requeue_orchestrated_inference_task,
)

if TYPE_CHECKING:
    from core.database.protocols import DatabaseCoreProtocol
    from core.types.json import JSONDict
    from database.repositories.dependencies import DatabaseRepositoryDependencies

__all__ = ("DatabaseTasks",)


class DatabaseTasks:
    def __init__(self, deps: DatabaseRepositoryDependencies) -> None:
        self._core = deps.core
        self._fernets = deps.fernet
        self._durable_acceptance_policy = build_durable_acceptance_policy(
            deps.config,
            database_path=self._core.writer.db_path,
        )
        self._mutation_storage = deps.mutation_storage

    @property
    def core(self) -> DatabaseCoreProtocol:
        return self._core

    @property
    def fernets(self) -> tuple[Fernet, ...]:
        return self._fernets

    @property
    def mutation_storage(self) -> MutationStorageComposition | None:
        return self._mutation_storage

    async def get_unified_task(self, task_id: str) -> JSONDict | None:
        return await self._core.reader.execute_read(queries.get_unified_task_query, task_id)

    get_unified_tasks_by_ids = get_unified_tasks_by_ids

    async def query_unified_tasks(self, request: UnifiedTaskQueryRequest) -> list[JSONDict]:
        return await self._core.reader.execute_read(queries.query_unified_tasks_query, request)

    create_unified_task = create_unified_task

    has_conversation_interaction_checkpoint = has_interaction_checkpoint
    claim_interaction_secret = claim_interaction_secret
    mark_interaction_secret_downstream_started = mark_interaction_secret_downstream_started
    consume_interaction_secret_after_tool_checkpoint = (
        consume_interaction_secret_after_tool_checkpoint
    )
    consume_interaction_secrets_after_turn_checkpoint = (
        consume_interaction_secrets_after_turn_checkpoint
    )

    async def accept_durable_inference_task(
        self,
        request: CreateDurableInferenceTaskRequest,
    ) -> int:
        return await self._core.writer.queue_write_operation(
            orchestrator_queue_acceptance.sync_accept_durable_inference_task,
            request,
            self._durable_acceptance_policy,
            enqueue_timeout=self._durable_acceptance_policy.acceptance_db_busy_timeout_sec,
        )

    async def reserve_orchestrator_queue_scheduling_time(self, candidate_at_ms: int) -> int:
        return await self._core.writer.queue_write_operation(
            orchestrator_queue_scheduling_clock.reserve_orchestrator_queue_scheduling_time,
            candidate_at_ms,
        )

    update_unified_task_status = update_unified_task_status
    finalize_unified_task = finalize_unified_task
    reconcile_terminal_background_responses = reconcile_terminal_background_responses
    delete_unified_task = delete_unified_task
    cleanup_expired_unified_tasks = cleanup_expired_unified_tasks

    async def query_stuck_active_tasks(
        self,
        cutoff_epoch_ms: int,
        exclude_owner_types: tuple[str, ...] = (),
        exclude_task_types: tuple[str, ...] = (),
        limit: int = 1000,
        *,
        after_updated_at_ms: int | None = None,
        after_task_id: str | None = None,
    ) -> list[JSONDict]:
        return await self._core.reader.execute_read(
            active_queries.query_stuck_active_tasks_query,
            cutoff_epoch_ms,
            exclude_owner_types,
            exclude_task_types,
            limit,
            after_updated_at_ms=after_updated_at_ms,
            after_task_id=after_task_id,
        )

    async def update_orchestration_state(
        self,
        task_id: str,
        orchestration_state: JSONDict | None,
    ) -> bool:
        return await self._core.writer.queue_write_operation(
            lifecycle.sync_update_orchestration_state,
            task_id,
            orchestration_state,
        )

    async def update_cancellation_requested_at_ms(
        self,
        task_id: str,
        cancellation_requested_at_ms: int,
    ) -> bool:
        return await self._core.writer.queue_write_operation(
            lifecycle.sync_update_cancellation_requested_at_ms,
            task_id,
            cancellation_requested_at_ms,
        )

    async def update_cancellation_requested_at_ms_for_cancellation_id(
        self,
        cancellation_id: str,
        cancellation_requested_at_ms: int,
    ) -> int:
        return await self._core.writer.queue_write_operation(
            lifecycle.sync_update_cancellation_requested_at_ms_for_cancellation_id,
            cancellation_id,
            cancellation_requested_at_ms,
        )

    claim_orchestrator_queue_items = claim_orchestrator_queue_items
    recover_expired_orchestrator_queue_items = recover_expired_orchestrator_queue_items
    release_orchestrator_queue_item_lease = release_orchestrator_queue_item_lease
    mark_orchestrator_queue_item_running_if_leased = mark_orchestrator_queue_item_running_if_leased
    mark_orchestrator_queue_item_prefetched_if_leased = (
        mark_orchestrator_queue_item_prefetched_if_leased
    )
    finalize_orchestrator_queue_item = finalize_orchestrator_queue_item
    requeue_orchestrated_inference_task = requeue_orchestrated_inference_task
    query_prefetched_orchestrated_task_ids = query_prefetched_orchestrated_task_ids

    query_active_tasks_for_cancellation_id = query_active_tasks_for_cancellation_id
    query_active_tasks_by_type = query_active_tasks_by_type
    count_running_orchestrated_inference_tasks_for_owner = (
        count_running_orchestrated_inference_tasks_for_owner
    )
    query_active_cancellation_ids = query_active_cancellation_ids

    accept_mutation_task = accept_mutation_task
    advance_mutation_execution = advance_mutation_execution
    claim_mutation = claim_mutation
    claim_next_mutation = claim_next_mutation
    mutation_requires_fenced_finalization = mutation_requires_fenced_finalization
    quarantine_exhausted_mutations = quarantine_exhausted_mutations
    query_expired_mutation_recovery_candidates = query_expired_mutation_recovery_candidates
    query_recovery_required_admissions = query_recovery_required_admissions
    release_mutation_recovery = release_mutation_recovery
    renew_mutation_claim = renew_mutation_claim
    validate_mutation_claim = validate_mutation_claim
