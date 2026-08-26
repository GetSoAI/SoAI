"""SoAI - Database task persistence protocol [backend/core/database/protocols_tasks.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import Protocol

from core.database.protocols_mutation_tasks import DatabaseMutationTasksProtocol
from core.database.task_requests import (
    CreateDurableInferenceTaskRequest,
    CreateUnifiedTaskRequest,
    DurableQueueClaim,
    UnifiedTaskFinalizationWriteResult,
    UnifiedTaskQueryRequest,
)
from core.orchestrator.request_priority import RequestPriority
from core.tasks.interaction_mutations import ConversationInteractionMutation
from core.tasks.interaction_secrets import (
    ClaimedInteractionSecret,
    InteractionSecretClaimIdentity,
)
from core.types.json import JSONDict

__all__ = ("DatabaseTasksProtocol",)


class DatabaseTasksProtocol(DatabaseMutationTasksProtocol, Protocol):
    async def create_unified_task(self, request: CreateUnifiedTaskRequest) -> bool: ...

    async def has_conversation_interaction_checkpoint(
        self,
        *,
        input_id: str,
        task_id: str,
    ) -> bool: ...

    async def claim_interaction_secret(
        self,
        *,
        task_id: str,
        user_id: int,
        conv_id: str,
        claim_owner: str,
    ) -> ClaimedInteractionSecret | None: ...

    async def mark_interaction_secret_downstream_started(
        self,
        *,
        identity: InteractionSecretClaimIdentity,
        tool_call_id: str,
    ) -> bool: ...

    async def consume_interaction_secret_after_tool_checkpoint(
        self,
        *,
        task_id: str,
    ) -> bool: ...

    async def consume_interaction_secrets_after_turn_checkpoint(
        self,
        *,
        turn_id: str,
        iteration_index: int,
    ) -> int: ...

    async def accept_durable_inference_task(
        self,
        request: CreateDurableInferenceTaskRequest,
    ) -> int: ...

    async def reserve_orchestrator_queue_scheduling_time(self, candidate_at_ms: int) -> int: ...

    async def get_unified_task(self, task_id: str) -> JSONDict | None: ...

    async def get_unified_tasks_by_ids(self, task_ids: tuple[str, ...]) -> list[JSONDict]: ...

    async def update_unified_task_status(
        self,
        task_id: str,
        status: str,
        status_message: str | None = None,
        progress_current: int | None = None,
        progress_total: int | None = None,
        progress_details: str | None = None,
    ) -> bool: ...

    async def finalize_unified_task(
        self,
        task_id: str,
        status: str,
        result: str | None = None,
        error_code: int | None = None,
        error_type: str | None = None,
        error_message: str | None = None,
        status_message: str | None = None,
        mutation_fencing_token: int | None = None,
        interaction_mutation: ConversationInteractionMutation | None = None,
    ) -> UnifiedTaskFinalizationWriteResult: ...

    async def reconcile_terminal_background_responses(self) -> int: ...

    async def update_cancellation_requested_at_ms(
        self,
        task_id: str,
        cancellation_requested_at_ms: int,
    ) -> bool: ...

    async def update_cancellation_requested_at_ms_for_cancellation_id(
        self,
        cancellation_id: str,
        cancellation_requested_at_ms: int,
    ) -> int: ...

    async def update_orchestration_state(
        self,
        task_id: str,
        orchestration_state: JSONDict | None,
    ) -> bool: ...

    async def query_unified_tasks(self, request: UnifiedTaskQueryRequest) -> list[JSONDict]: ...

    async def delete_unified_task(self, task_id: str) -> bool: ...

    async def cleanup_expired_unified_tasks(self) -> int: ...

    async def query_stuck_active_tasks(
        self,
        cutoff_epoch_ms: int,
        exclude_owner_types: tuple[str, ...] = (),
        exclude_task_types: tuple[str, ...] = (),
        limit: int = 1000,
        *,
        after_updated_at_ms: int | None = None,
        after_task_id: str | None = None,
    ) -> list[JSONDict]: ...

    async def claim_orchestrator_queue_items(
        self,
        *,
        now_ms: int,
        lease_owner: str,
        lease_ttl_ms: int,
        limit: int,
        request_priority: RequestPriority,
    ) -> list[DurableQueueClaim]: ...

    async def recover_expired_orchestrator_queue_items(self, *, now_ms: int) -> int: ...

    async def release_orchestrator_queue_item_lease(
        self,
        task_id: str,
        *,
        available_at_ms: int,
    ) -> bool: ...

    async def mark_orchestrator_queue_item_running_if_leased(
        self,
        task_id: str,
        *,
        lease_owner: str,
    ) -> bool: ...

    async def mark_orchestrator_queue_item_prefetched_if_leased(
        self,
        task_id: str,
        *,
        lease_owner: str,
    ) -> bool: ...

    async def finalize_orchestrator_queue_item(self, task_id: str, status: str) -> None: ...

    async def requeue_orchestrated_inference_task(
        self,
        task_id: str,
        *,
        available_at_ms: int,
        status_message: str | None = None,
    ) -> bool: ...

    async def query_prefetched_orchestrated_task_ids(self, *, limit: int = 10000) -> list[str]: ...

    async def query_active_tasks_for_cancellation_id(
        self,
        cancellation_id: str,
        *,
        after_created_at_ms: int = 0,
        after_task_id: str = "",
        limit: int = 1000,
    ) -> list[JSONDict]: ...

    async def query_active_tasks_by_type(
        self,
        task_type: str,
        *,
        after_created_at_ms: int = 0,
        after_task_id: str = "",
        limit: int = 1000,
    ) -> list[JSONDict]: ...

    async def count_running_orchestrated_inference_tasks_for_owner(
        self,
        owner_type: str,
        owner_id: str,
    ) -> int: ...

    async def query_active_cancellation_ids(
        self,
        *,
        include_internal: bool,
        limit: int = 200000,
    ) -> list[str]: ...
