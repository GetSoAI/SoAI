"""SoAI - Request queueing service with deduplication and priority management [backend/orchestrator/queueing/service.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio

from core.errors.error_types import ErrorType
from core.errors.exceptions import StateError
from core.orchestrator.protocols_queue import OrchestratorQueueStatusSnapshot
from core.orchestrator.queue_decisions import QueueDecision, build_cancel_task_decision
from core.orchestrator.request_priority import (
    RequestPriority,
    RequestPriorityAssignment,
    assign_request_priority,
)
from core.orchestrator.routing_config import RoutingConfig, require_routing_config
from core.orchestrator.runtime_config import OrchestratorRuntimeConfig
from core.tasks.enums import TaskStatus
from core.tasks.orchestration_context import OrchestrationContext
from core.tasks.task import Task
from core.tasks.task_cancellation import cancel
from core.types.json import JSONDict
from orchestrator.prompt_slot_lifecycle import release_prompt_slot_and_update_cache
from orchestrator.queueing.dedup_requeue import (
    QueueDeduplicationRequeue,
    QueueDeduplicationRequeueDependencies,
)
from orchestrator.queueing.deduplication import (
    QueueDeduplication,
    QueueDeduplicationConfig,
)
from orchestrator.queueing.dependencies import OrchestratorQueueDependencies
from orchestrator.queueing.execution_reservations import QueueExecutionReservations
from orchestrator.queueing.pending_registration import register_scheduler_pending_task
from orchestrator.queueing.priority.dependencies import QueuePriorityDependencies
from orchestrator.queueing.priority.manager import QueuePriority
from orchestrator.queueing.request_tracking.dependencies import (
    QueueRequestTrackingDependencies,
)
from orchestrator.queueing.request_tracking.tracker import QueueRequestTracking
from orchestrator.types import OrchestratorDependencies

__all__ = ("OrchestratorQueue",)


class OrchestratorQueue:
    _QUEUE_CANCEL_REASON = "Task was cancelled while queued."

    def __init__(self, deps: OrchestratorQueueDependencies) -> None:
        self.orchestrator_deps: OrchestratorDependencies = deps.orchestrator
        self._routing_config: RoutingConfig | None = deps.routing_config
        self.config = deps.config
        self.cycles = deps.cycles
        self.task_registry = deps.task_registry
        self.scheduling_clock = deps.scheduling_clock
        self.shutdown_event = deps.shutdown_event
        self.is_quiescent = deps.is_quiescent
        self.durable_queue_wakeup = asyncio.Event()
        self.tracking = QueueRequestTracking(
            QueueRequestTrackingDependencies(
                require_orchestration_context=self.require_orchestration_context,
            ),
        )
        self.execution_reservations = QueueExecutionReservations()
        self.priority = QueuePriority(
            QueuePriorityDependencies(
                config=deps.config,
                metrics=self.orchestrator_deps.metrics,
                cycles=self.cycles,
                shutdown_event=self.shutdown_event,
                get_total_backlog_size=self.get_total_backlog_size,
                require_orchestration_context=self.require_orchestration_context,
            ),
        )
        self.deduplication = QueueDeduplication(
            QueueDeduplicationConfig(
                enabled=deps.config.dedup_enabled,
                waiter_ttl_seconds=1800.0,
            ),
        )
        self.dedup_requeue = QueueDeduplicationRequeue(
            QueueDeduplicationRequeueDependencies(
                deduplication=self.deduplication,
                shutdown_event=self.shutdown_event,
                task_registry=self.task_registry,
                task_queue=self,
                task_index=self.tracking,
            ),
        )

    @property
    def routing_config(self) -> RoutingConfig:
        return require_routing_config(
            self._routing_config,
            missing_message="routing_config accessed before initialization",
            error_type=StateError,
        )

    @routing_config.setter
    def routing_config(self, value: RoutingConfig) -> None:
        self._routing_config = value

    def require_orchestration_context(self, task: Task) -> OrchestrationContext:
        return task.require_orchestration_context()

    async def assign_request_priority(self, payload: JSONDict) -> RequestPriorityAssignment:
        queued_at = await self.scheduling_clock.reserve_queued_at()
        routing_config = self.routing_config
        return assign_request_priority(
            payload,
            queued_at=queued_at,
            standard_aging_seconds=routing_config.standard_priority_aging_sec,
            flex_aging_seconds=routing_config.flex_priority_aging_sec,
        )

    async def update_config(self, config: OrchestratorRuntimeConfig) -> None:
        self.priority.apply_runtime_config(config)
        changed = self.deduplication.apply_config(
            QueueDeduplicationConfig(
                enabled=config.dedup_enabled,
                waiter_ttl_seconds=1800.0,
            ),
        )
        if changed:
            tasks = await self.dedup_requeue.drain_dedup_waiters(
                reason="Deduplication configuration updated; clearing cached results.",
            )
            if tasks:
                task_ids = [task.task_id for task in tasks]
                unresolved_waiter_ids = await self.dedup_requeue.requeue_stale_dedup_waiters(
                    task_ids,
                    reason="Deduplication configuration updated; clearing cached results.",
                )
                await self.deduplication.complete_resolution(
                    task_ids,
                    unresolved_waiter_ids,
                )

    async def get_total_backlog_size(self) -> int:
        pending_total = await self.tracking.get_total_pending_count()
        return self.priority.queue_state.queue_resource.current.qsize() + pending_total

    async def get_prefetched_priority_counts(self) -> dict[RequestPriority, int]:
        counts = self.priority.queue_state.priority_counts()
        pending_counts = await self.tracking.get_pending_priority_counts()
        for priority in RequestPriority:
            counts[priority] += pending_counts[priority]
        return counts

    def notify_durable_queue_wakeup(self) -> None:
        self.durable_queue_wakeup.set()

    def clear_durable_queue_wakeup(self) -> None:
        self.durable_queue_wakeup.clear()

    async def get_status_snapshot(self) -> OrchestratorQueueStatusSnapshot:
        pending_summary = await self.tracking.snapshot_pending_summary()
        queued_count = self.priority.queue_state.queue_resource.current.qsize()
        dedup_count = await self.deduplication.get_deduplicated_count()
        return {
            "queued_tasks_count": queued_count,
            "pending_tasks_by_uid": pending_summary,
            "deduplicated_tasks_count": dedup_count,
            "total_backlog_size": queued_count + sum(pending_summary.values()),
            "last_deferral_reasons": dict(self.tracking.last_deferral_reason),
        }

    async def is_task_cancelled(self, task: Task) -> bool:
        if task.status == TaskStatus.CANCELLED:
            return True
        if task.cancellation_requested_at_ms is not None:
            return True
        if not task.cancellation_id:
            return False
        return await self.orchestrator_deps.cancellation_history.is_cancelled(task.cancellation_id)

    async def cancel_if_cancelled(
        self,
        task: Task,
        reason: str | None = None,
    ) -> QueueDecision | None:
        if not await self.is_task_cancelled(task):
            return None
        cancel_reason = None
        if task.cancellation_id:
            cancel_reason = await self.orchestrator_deps.cancellation_history.get_reason(
                task.cancellation_id,
            )
        final_reason = cancel_reason or reason or self._QUEUE_CANCEL_REASON
        orchestration_context = task.orchestration_context
        await cancel(
            self.task_registry,
            task.task_id,
            final_reason,
            context=(
                orchestration_context.event.context
                if orchestration_context and orchestration_context.event
                else None
            ),
        )
        return build_cancel_task_decision(
            task=task,
            reason=final_reason,
            error_type=ErrorType.CONFLICT,
        )

    async def ensure_prompt_slot_and_cancel_if_cancelled(
        self,
        task: Task,
        reason: str | None = None,
    ) -> tuple[Task, QueueDecision | None]:
        context = self.require_orchestration_context(task)
        if self.priority.prompt_slots.enabled and (not context.prompt_slot_active):
            task = await self.priority.acquire_prompt_slot(task)
        decision = await self.cancel_if_cancelled(task, reason=reason)
        if decision is not None:
            task = await release_prompt_slot_and_update_cache(
                self.priority,
                self.task_registry,
                task,
            )
        return (task, decision)

    async def mark_task_pending(
        self,
        task: Task,
        routing_key: str,
        *,
        plugin_name: str | None = None,
    ) -> Task:
        return await register_scheduler_pending_task(
            self,
            task,
            routing_key,
            plugin_name=plugin_name,
            insert_left=False,
            refresh_before_transition=True,
            index_task=False,
            register_active=False,
        )
