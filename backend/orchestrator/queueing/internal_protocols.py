"""SoAI - Queue management internal protocol definitions [backend/orchestrator/queueing/internal_protocols.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections import deque
from typing import TYPE_CHECKING, Protocol, override

from core.orchestrator.protocols_queue import (
    DedupRegistrationResultProtocol,
    OrchestratorQueueProtocol,
    QueueCycleManagerProtocol,
    QueueDeduplicationRequeueViewProtocol,
    QueueDeduplicationViewProtocol,
    QueueExecutionReservationsProtocol,
    QueuePriorityViewProtocol,
    QueueTrackingViewProtocol,
)
from core.orchestrator.queue_decisions import QueueDecision
from core.tasks.enums import TaskStatus
from core.tasks.orchestration_context import OrchestrationContext
from core.tasks.protocols import TaskRegistryProtocol
from core.tasks.task import Task
from orchestrator.queueing.priority.sentinel import ShutdownSentinel

if TYPE_CHECKING:
    from core.orchestrator.request_priority import RequestPriority, RequestPriorityAssignment
    from core.orchestrator.routing_config import RoutingConfig
    from core.types.json import JSONDict
    from orchestrator.queueing.deduplication import QueueDeduplicationConfig

__all__ = (
    "QueuePriorityProtocol",
    "QueueRequestTrackingProtocol",
    "QueueServiceView",
)


class QueuePriorityProtocol(QueuePriorityViewProtocol, Protocol):
    @property
    def task_queue(self) -> asyncio.Queue[Task | type[ShutdownSentinel]]: ...

    async def drain_task_queue(self) -> list[Task]: ...

    def signal_shutdown(self, worker_count: int) -> None: ...

    @override
    async def acquire_prompt_slot(self, task: Task) -> Task: ...

    @override
    def release_prompt_slot(self, task: Task) -> Task: ...

    @override
    async def enqueue_task(self, task: Task) -> None: ...

    @override
    @override
    async def take_task(self) -> Task | None: ...


class QueueRequestTrackingProtocol(QueueTrackingViewProtocol, Protocol):
    last_deferral_reason: dict[str, str]

    @override
    async def get_pending_priority_counts(self) -> dict[RequestPriority, int]: ...

    @override
    async def index_task(self, task: Task) -> None: ...

    @override
    async def update_task(self, task: Task) -> None: ...

    @override
    async def get_task_by_id(self, task_id: str) -> Task | None: ...

    @override
    async def forget_task(self, task_id: str) -> None: ...

    @override
    async def has_task_ownership(self, task: Task) -> bool: ...

    @override
    async def get_tasks_for_cancellation_id(self, cancellation_id: str) -> list[Task]: ...

    @override
    async def get_cancellation_ids_snapshot(self) -> set[str]: ...

    @override
    async def has_pending_tasks(self) -> bool: ...

    @override
    async def get_pending_keys(self) -> set[str]: ...

    @override
    async def get_pending_universal_ids_snapshot(self) -> dict[str, set[str]]: ...

    @override
    async def get_pending_universal_ids_for_plugins(self, plugin_names: set[str]) -> set[str]: ...

    @override
    async def peek_pending_task(
        self,
        key: str,
    ) -> tuple[Task | None, str | None, TaskStatus | None]: ...

    @override
    async def move_pending_task(
        self,
        task: Task,
        from_key: str,
        to_key: str,
        *,
        insert_left: bool = False,
    ) -> bool: ...

    @override
    async def add_pending_universal_id_for_plugin(
        self,
        plugin_name: str,
        universal_id: str,
    ) -> None: ...

    @override
    async def unregister_pending_queue(self, key: str) -> deque[Task]: ...

    @override
    async def unregister_pending_task_token_for_key(self, task: Task, key: str) -> None: ...

    @override
    async def register_active_task(self, task: Task) -> None: ...

    @override
    async def register_indexed_active_task(self, task: Task) -> None: ...

    @override
    async def register_pending_task(
        self,
        task: Task,
        routing_key: str,
        *,
        plugin_name: str | None,
        insert_left: bool,
    ) -> None: ...

    @override
    async def cleanup_completed_task(self, task: Task) -> None: ...

    @override
    async def set_deferral_reason(self, key: str | None, reason: str) -> None: ...

    async def snapshot_pending_summary(self) -> dict[str, int]: ...

    @override
    async def get_total_pending_count(self) -> int: ...

    async def get_tasks_by_ids(self, task_ids: set[str]) -> list[Task]: ...

    async def get_tasks_by_status(self, status: TaskStatus) -> list[Task]: ...


class QueueDeduplicationProtocol(QueueDeduplicationViewProtocol, Protocol):
    @property
    @override
    def enabled(self) -> bool: ...

    def apply_config(self, config: QueueDeduplicationConfig) -> bool: ...

    @override
    async def get_deduplicated_count(self) -> int: ...

    @override
    def calculate_dedup_hash(
        self,
        context: OrchestrationContext,
        *,
        routing_config: RoutingConfig,
    ) -> str: ...

    @override
    async def register_or_reuse(
        self,
        *,
        dedup_hash: str,
        task_id: str,
    ) -> DedupRegistrationResultProtocol: ...

    async def remove_waiter(self, *, dedup_hash: str, task_id: str) -> None: ...

    @override
    async def resolve_future(
        self,
        dedup_hash: str,
        *,
        result: JSONDict | None = None,
        exception: BaseException | None = None,
    ) -> list[str]: ...

    async def complete_resolution(
        self, waiter_ids: list[str], unresolved_waiter_ids: list[str]
    ) -> None: ...

    async def drain_waiters(self, *, reason: str) -> set[str]: ...

    async def cleanup_expired_entries(self) -> tuple[list[str], str | None]: ...


class QueueDeduplicationRequeueProtocol(QueueDeduplicationRequeueViewProtocol, Protocol): ...


class QueueServiceView(OrchestratorQueueProtocol, Protocol):
    @property
    @override
    def task_registry(self) -> TaskRegistryProtocol: ...

    @property
    @override
    def shutdown_event(self) -> asyncio.Event: ...

    @property
    @override
    def is_quiescent(self) -> asyncio.Event: ...

    @property
    @override
    def tracking(self) -> QueueRequestTrackingProtocol: ...

    @property
    @override
    def priority(self) -> QueuePriorityProtocol: ...

    @property
    @override
    def execution_reservations(self) -> QueueExecutionReservationsProtocol: ...

    @property
    @override
    def cycles(self) -> QueueCycleManagerProtocol: ...

    @property
    @override
    def deduplication(self) -> QueueDeduplicationProtocol: ...

    @property
    @override
    def dedup_requeue(self) -> QueueDeduplicationRequeueProtocol: ...

    @override
    def require_orchestration_context(self, task: Task) -> OrchestrationContext: ...

    @override
    async def assign_request_priority(self, payload: JSONDict) -> RequestPriorityAssignment: ...

    @override
    async def get_prefetched_priority_counts(self) -> dict[RequestPriority, int]: ...

    @override
    async def is_task_cancelled(self, task: Task) -> bool: ...

    @override
    async def mark_task_pending(
        self,
        task: Task,
        routing_key: str,
        *,
        plugin_name: str | None = None,
    ) -> Task: ...

    @override
    async def cancel_if_cancelled(
        self,
        task: Task,
        reason: str | None = None,
    ) -> QueueDecision | None: ...

    @override
    async def ensure_prompt_slot_and_cancel_if_cancelled(
        self,
        task: Task,
        reason: str | None = None,
    ) -> tuple[Task, QueueDecision | None]: ...
