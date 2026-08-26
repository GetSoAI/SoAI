"""SoAI - Orchestrator queue protocol contracts [backend/core/orchestrator/protocols_queue.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections import deque
from collections.abc import Callable, Sequence
from enum import Enum
from typing import TYPE_CHECKING, Protocol, TypedDict

from core.concurrency.protocols import TaskDoneQueueProtocol
from core.orchestrator.routing_config import RoutingConfig
from core.orchestrator.runtime_config import OrchestratorRuntimeConfig
from core.tasks.enums import TaskStatus
from core.tasks.orchestration_context import OrchestrationContext
from core.tasks.task import Task

if TYPE_CHECKING:
    from core.events.protocols import EventBusProtocol
    from core.metrics.protocols import MetricsManagerProtocol
    from core.models.protocols import (
        ModelInformationServiceProtocol,
        ModelParameterServiceProtocol,
        ParameterManagerProtocol,
    )
    from core.orchestrator.queue_decisions import QueueDecision
    from core.orchestrator.request_priority import RequestPriority, RequestPriorityAssignment
    from core.tasks.protocols import CancellationHistoryProtocol, TaskRegistryProtocol
    from core.types.json import JSONDict

__all__ = (
    "DedupRegistrationResultProtocol",
    "OrchestratorDependenciesProtocol",
    "OrchestratorQueueProtocol",
    "OrchestratorQueueStatusSnapshot",
    "PromptSlotSnapshot",
    "QueueCycleManagerProtocol",
    "QueueCycleType",
    "QueueDeduplicationRequeueViewProtocol",
    "QueueDeduplicationViewProtocol",
    "QueueExecutionReservationsProtocol",
    "QueuePriorityViewProtocol",
    "QueueTrackingViewProtocol",
)


class OrchestratorQueueStatusSnapshot(TypedDict):
    queued_tasks_count: int
    pending_tasks_by_uid: dict[str, int]
    deduplicated_tasks_count: int
    total_backlog_size: int
    last_deferral_reasons: dict[str, str]


class QueueCycleType(Enum):
    PRIORITY = "priority"
    PLUGIN = "plugin"


class OrchestratorDependenciesProtocol(Protocol):
    @property
    def bus(self) -> EventBusProtocol: ...
    @property
    def metrics(self) -> MetricsManagerProtocol: ...
    @property
    def cancellation_history(self) -> CancellationHistoryProtocol: ...
    @property
    def model_information_service(self) -> ModelInformationServiceProtocol: ...
    @property
    def model_parameter_service(self) -> ModelParameterServiceProtocol: ...
    @property
    def param_manager(self) -> ParameterManagerProtocol: ...


class QueueTrackingViewProtocol(Protocol):
    last_deferral_reason: dict[str, str]

    async def has_pending_tasks(self) -> bool: ...
    async def get_pending_keys(self) -> set[str]: ...
    async def get_pending_universal_ids_for_plugins(self, plugin_names: set[str]) -> set[str]: ...
    async def unregister_pending_queue(self, key: str) -> deque[Task]: ...
    async def set_deferral_reason(self, key: str | None, reason: str) -> None: ...
    async def index_task(self, task: Task) -> None: ...
    async def update_task(self, task: Task) -> None: ...
    async def get_task_by_id(self, task_id: str) -> Task | None: ...
    async def forget_task(self, task_id: str) -> None: ...
    async def has_task_ownership(self, task: Task) -> bool: ...
    async def register_active_task(self, task: Task) -> None: ...
    async def register_indexed_active_task(self, task: Task) -> None: ...
    async def register_pending_task(
        self,
        task: Task,
        routing_key: str,
        *,
        plugin_name: str | None,
        insert_left: bool,
    ) -> None: ...
    async def cleanup_completed_task(self, task: Task) -> None: ...
    async def peek_pending_task(
        self,
        key: str,
    ) -> tuple[Task | None, str | None, TaskStatus | None]: ...
    async def unregister_pending_task_token_for_key(self, task: Task, key: str) -> None: ...
    async def get_tasks_for_cancellation_id(self, cancellation_id: str) -> list[Task]: ...
    async def get_cancellation_ids_snapshot(self) -> set[str]: ...
    async def get_pending_universal_ids_snapshot(self) -> dict[str, set[str]]: ...
    async def move_pending_task(
        self,
        task: Task,
        from_key: str,
        to_key: str,
        *,
        insert_left: bool = False,
    ) -> bool: ...
    async def add_pending_universal_id_for_plugin(
        self,
        plugin_name: str,
        universal_id: str,
    ) -> None: ...
    async def count_prompt_slot_active_tasks(self) -> int: ...
    async def get_total_pending_count(self) -> int: ...
    async def get_pending_priority_counts(self) -> dict[RequestPriority, int]: ...


class PromptSlotSnapshot(TypedDict):
    enabled: bool
    limit: int
    held: int
    waiters: int


class QueuePriorityViewProtocol(Protocol):
    @property
    def prompt_queuing_enabled(self) -> bool: ...
    async def enqueue_task(self, task: Task) -> None: ...
    async def take_task(self) -> Task | None: ...
    async def acquire_prompt_slot(self, task: Task) -> Task: ...
    def release_prompt_slot(self, task: Task) -> Task: ...
    def get_prompt_slot_snapshot(self) -> PromptSlotSnapshot: ...


class QueueExecutionReservationsProtocol(Protocol):
    async def reserve(self, tracking_id: str, universal_id: str) -> None: ...
    async def release(self, tracking_id: str) -> None: ...
    async def snapshot(self, universal_ids: Sequence[str]) -> dict[str, int]: ...


class QueueCycleManagerProtocol(Protocol):
    async def abandon_cycle(
        self,
        task_id: str,
        cycle_type: QueueCycleType,
    ) -> bool: ...
    async def migrate_cycle(
        self,
        task_id: str,
        cycle_type: QueueCycleType,
        target_queue: TaskDoneQueueProtocol,
    ) -> None: ...
    async def close_cycle(
        self,
        task: Task,
        cycle_type: QueueCycleType,
        *,
        context_label: str = "",
        for_requeue: bool = False,
    ) -> bool: ...
    async def open_cycle_and_enqueue_nowait(
        self,
        task_id: str,
        cycle_type: QueueCycleType,
        queue: TaskDoneQueueProtocol,
        enqueue: Callable[[], None],
    ) -> None: ...

    def get_open_counts(self) -> dict[str, int]: ...


class DedupRegistrationResultProtocol(Protocol):
    @property
    def is_waiter(self) -> bool: ...

    @property
    def lead_task_id(self) -> str | None: ...


class QueueDeduplicationViewProtocol(Protocol):
    @property
    def enabled(self) -> bool: ...
    async def get_deduplicated_count(self) -> int: ...
    def calculate_dedup_hash(
        self,
        context: OrchestrationContext,
        *,
        routing_config: RoutingConfig,
    ) -> str: ...
    async def register_or_reuse(
        self,
        *,
        dedup_hash: str,
        task_id: str,
    ) -> DedupRegistrationResultProtocol: ...
    async def resolve_future(
        self,
        dedup_hash: str,
        *,
        result: JSONDict | None = None,
        exception: BaseException | None = None,
    ) -> list[str]: ...


class QueueDeduplicationRequeueViewProtocol(Protocol):
    async def drain_dedup_waiters(self, *, reason: str) -> list[Task]: ...
    async def dedup_cleanup_loop(self) -> None: ...
    async def requeue_stale_dedup_waiters(
        self, task_ids: list[str], *, reason: str
    ) -> list[str]: ...


class OrchestratorQueueProtocol(Protocol):
    @property
    def orchestrator_deps(self) -> OrchestratorDependenciesProtocol: ...
    @property
    def task_registry(self) -> TaskRegistryProtocol: ...
    @property
    def config(self) -> OrchestratorRuntimeConfig: ...
    @property
    def shutdown_event(self) -> asyncio.Event: ...
    @property
    def is_quiescent(self) -> asyncio.Event: ...
    @property
    def durable_queue_wakeup(self) -> asyncio.Event: ...
    @property
    def tracking(self) -> QueueTrackingViewProtocol: ...
    @property
    def priority(self) -> QueuePriorityViewProtocol: ...
    @property
    def execution_reservations(self) -> QueueExecutionReservationsProtocol: ...
    @property
    def cycles(self) -> QueueCycleManagerProtocol: ...
    @property
    def deduplication(self) -> QueueDeduplicationViewProtocol: ...
    @property
    def routing_config(self) -> RoutingConfig: ...
    @routing_config.setter
    def routing_config(self, value: RoutingConfig) -> None: ...
    @property
    def dedup_requeue(self) -> QueueDeduplicationRequeueViewProtocol: ...
    async def get_status_snapshot(self) -> OrchestratorQueueStatusSnapshot: ...
    async def mark_task_pending(
        self,
        task: Task,
        routing_key: str,
        *,
        plugin_name: str | None = None,
    ) -> Task: ...
    async def is_task_cancelled(self, task: Task) -> bool: ...
    async def ensure_prompt_slot_and_cancel_if_cancelled(
        self,
        task: Task,
        reason: str | None = None,
    ) -> tuple[Task, QueueDecision | None]: ...
    async def cancel_if_cancelled(
        self,
        task: Task,
        reason: str | None = None,
    ) -> QueueDecision | None: ...
    def require_orchestration_context(self, task: Task) -> OrchestrationContext: ...
    async def assign_request_priority(self, payload: JSONDict) -> RequestPriorityAssignment: ...
    def notify_durable_queue_wakeup(self) -> None: ...
    def clear_durable_queue_wakeup(self) -> None: ...
    async def get_total_backlog_size(self) -> int: ...
    async def get_prefetched_priority_counts(self) -> dict[RequestPriority, int]: ...
    async def update_config(self, config: OrchestratorRuntimeConfig) -> None: ...
