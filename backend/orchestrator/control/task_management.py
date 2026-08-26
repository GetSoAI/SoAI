"""SoAI - Orchestrator task cancellation management [backend/orchestrator/control/task_management.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.concurrency.queue_ops import put_nowait_with_overwrite
from core.di.validation import require_dependencies
from core.errors.error_types import ErrorType
from core.errors.exception_logging import log_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.events.types_base import Event, PayloadEvent
from core.events.types_tasks import CancelAllTasksCommand, CancelTaskCommand
from core.logging.trace import get_logger
from core.tasks.cancellation_commands import cancel_via_registry
from core.tasks.cancellation_ids import is_system_cancellation_id
from core.tasks.enums import TaskStatus
from core.tasks.failure_events import send_error_event_and_finalize
from core.tasks.finalization import finalize
from core.tasks.protocols import TaskRegistryProtocol
from core.tasks.protocols_query import TaskRegistryQueryView
from orchestrator.control.cancellation_targets import load_orchestrated_cancel_targets
from orchestrator.internal_protocols import (
    OrchestratorActiveInferenceProtocol,
    OrchestratorTaskOutcomesProtocol,
)
from orchestrator.queueing.internal_protocols import QueueServiceView
from orchestrator.types import OrchestratorDependencies

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "OrchestratorTaskManagementDependencies",
    "handle_cancel_all_tasks",
    "handle_cancel_task",
)

LOGGER_NAME = "SoAI.orchestrator.control.task_management"
OPERATION_ORCHESTRATOR_HANDLE_CANCEL_ALL_TASKS = "orchestrator.handle_cancel_all_tasks"
OPERATION_ORCHESTRATOR_HANDLE_CANCEL_TASK = "orchestrator.handle_cancel_task"


@dataclass(frozen=True, slots=True)
class OrchestratorTaskManagementDependencies:
    orchestrator: OrchestratorDependencies
    queue: QueueServiceView
    active_inferences: OrchestratorActiveInferenceProtocol
    outcomes: OrchestratorTaskOutcomesProtocol
    task_registry: TaskRegistryProtocol
    task_registry_queries: TaskRegistryQueryView

    def __post_init__(self) -> None:
        require_dependencies(
            owner="OrchestratorTaskManagementDependencies",
            active_inferences=self.active_inferences,
            orchestrator=self.orchestrator,
            outcomes=self.outcomes,
            queue=self.queue,
            task_registry=self.task_registry,
            task_registry_queries=self.task_registry_queries,
        )


async def handle_cancel_all_tasks(
    command: Event,
    *,
    deps: OrchestratorTaskManagementDependencies,
) -> None:
    logger = get_logger(LOGGER_NAME)
    if not isinstance(command, CancelAllTasksCommand):
        return
    reason = (command.reason or "Bulk cancellation requested.").strip()
    include_internal = bool(command.include_internal)
    command_context = command.context
    try:
        targeted_cancellation_ids = await deps.queue.tracking.get_cancellation_ids_snapshot()
        cancel_result = await deps.orchestrator.cancellation_coordinator.cancel_all_scopes(
            reason,
            include_internal=include_internal,
        )
        targeted_cancellation_ids.update(
            {
                cancellation_id
                for cancellation_id in cancel_result.cancellation_ids
                if isinstance(cancellation_id, str) and cancellation_id
            },
        )
        db_cancellation_ids = await deps.task_registry_queries.query_active_cancellation_ids(
            include_internal=include_internal,
        )
        targeted_cancellation_ids.update(db_cancellation_ids)
        targeted_cancellation_ids.discard("")
        skipped_internal = 0
        if not include_internal:
            allowed_cancellation_ids = {
                cancellation_id
                for cancellation_id in targeted_cancellation_ids
                if not is_system_cancellation_id(cancellation_id)
            }
            skipped_internal = len(targeted_cancellation_ids) - len(allowed_cancellation_ids)
            targeted_cancellation_ids = allowed_cancellation_ids
        published = 0
        for cancellation_id in sorted(targeted_cancellation_ids):
            try:
                await deps.orchestrator.bus.publish(
                    event=CancelTaskCommand(
                        cancellation_id=cancellation_id,
                        reason=reason,
                        context=command_context,
                    ),
                )
                published += 1
            except RECOVERABLE_EXCEPTIONS as pub_exc:
                log_exception(
                    logger,
                    pub_exc,
                    message="Failed to publish CancelTaskCommand during bulk cancel",
                    operation=OPERATION_ORCHESTRATOR_HANDLE_CANCEL_ALL_TASKS,
                    details={"cancellation_id": cancellation_id},
                )
        response: JSONDict = {
            "message": "Bulk cancellation issued.",
            "reason": reason,
            "include_internal": include_internal,
            "cancel_tasks_published": published,
            "skipped_internal": skipped_internal,
            "targeted_cancellation_ids": sorted(targeted_cancellation_ids),
            "registry_summary": {
                "cancellations_targeted": cancel_result.cancellations_targeted,
                "cancellation_ids": list(cancel_result.cancellation_ids),
                "excluded_cancellation_ids": list(cancel_result.excluded_cancellation_ids),
                "newly_cancelled_ids": list(cancel_result.newly_cancelled_ids),
                "reason": cancel_result.reason,
                "include_internal": cancel_result.include_internal,
            },
        }
        reply_channel = command.reply_channel
        if reply_channel is not None:
            reply_event = PayloadEvent(payload=response)
            if not put_nowait_with_overwrite(
                reply_channel,
                reply_event,
                overwrite_attempts=2,
            ).delivered:
                logger.error(
                    "Failed to deliver bulk cancellation response: reply channel unavailable.",
                )
                await send_error_event_and_finalize(
                    reply_channel,
                    "Failed to deliver bulk cancellation response.",
                    ErrorType.SERVER_ERROR,
                    registry=deps.task_registry,
                )
    except RECOVERABLE_EXCEPTIONS as exception:
        log_exception(
            logger,
            exception,
            message="Failed to process CancelAllTasksCommand",
            operation=OPERATION_ORCHESTRATOR_HANDLE_CANCEL_ALL_TASKS,
        )
        reply_channel = command.reply_channel
        if reply_channel is not None:
            await send_error_event_and_finalize(
                reply_channel,
                f"Failed to process bulk cancellation: {exception}",
                ErrorType.SERVER_ERROR,
                registry=deps.task_registry,
            )


async def handle_cancel_task(event: Event, *, deps: OrchestratorTaskManagementDependencies) -> None:
    logger = get_logger(LOGGER_NAME)
    if not isinstance(event, CancelTaskCommand):
        return
    try:
        cancel_args = await cancel_via_registry(
            event,
            deps.orchestrator.cancellation_coordinator,
            deps.orchestrator.cancellation_history,
        )
        if not cancel_args:
            return
        cancellation_id, reason = cancel_args
        targets = await load_orchestrated_cancel_targets(
            cancellation_id=cancellation_id,
            tracking=deps.queue.tracking,
            task_registry=deps.task_registry,
            task_registry_queries=deps.task_registry_queries,
        )
        if not targets:
            return
        for task in targets:
            if task.status.is_terminal():
                continue
            if task.orchestration_context is None:
                await deps.queue.tracking.forget_task(task.task_id)
                await finalize(
                    deps.task_registry,
                    task.task_id,
                    TaskStatus.CANCELLED,
                    error_message=reason,
                    status_message=reason,
                )
                continue
            tracking_id = deps.queue.require_orchestration_context(task).tracking_id
            if await deps.active_inferences.is_tracking_id_active(tracking_id):
                await deps.active_inferences.cancel_inflight_task(
                    tracking_id=tracking_id,
                    reason=reason,
                )
                continue
            logger.info("Task [%s] marked for cancellation. Cleaning up.", task.task_id)
            await deps.outcomes.cancel_task(task=task, reason=reason)
    except RECOVERABLE_EXCEPTIONS as exception:
        cancellation_id_value = event.cancellation_id
        log_exception(
            logger,
            exception,
            message="Failed to process CancelTaskCommand",
            operation=OPERATION_ORCHESTRATOR_HANDLE_CANCEL_TASK,
            details={"cancellation_id": cancellation_id_value},
        )
