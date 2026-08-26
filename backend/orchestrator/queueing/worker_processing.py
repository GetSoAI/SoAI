"""SoAI - Orchestrator queueing worker processing loop [backend/orchestrator/queueing/worker_processing.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

from core.errors.exception_logging import log_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.events.types_system import SoAIMainState, SystemMainStateOverrideEvent
from core.logging.trace import get_logger
from core.orchestrator.queue_decisions import (
    QueueDecision,
    build_dispatch_candidate_decision,
    build_fail_task_decision,
    build_plan_required_decision,
)
from core.tasks.task import Task
from orchestrator.model_info_resolution import resolve_orchestrator_model
from orchestrator.queueing.internal_protocols import QueueServiceView
from orchestrator.queueing.parameter_snapshot import rebuild_requeued_parameter_state

__all__ = (
    "process_task_from_queue",
    "worker_loop",
)

LOGGER_NAME = "SoAI.orchestrator.queueing.worker_processing"
OPERATION_ORCHESTRATOR_PROCESS_TASK_FROM_QUEUE = "orchestrator.process_task_from_queue"
OPERATION_ORCHESTRATOR_QUEUE_WORKER_LOOP = "orchestrator_queue.worker_loop"


async def worker_loop(
    queue: QueueServiceView,
    worker_id: int,
    decision_handler: Callable[[QueueDecision], Awaitable[None]],
) -> None:
    logger = get_logger(LOGGER_NAME)
    while not queue.shutdown_event.is_set():
        task: Task | None = None
        try:
            task = await queue.priority.take_task()
            if task is None:
                break
            decisions = await process_task_from_queue(queue, task)
            for decision in decisions:
                await decision_handler(decision)
        except asyncio.CancelledError:
            if task is not None and isinstance(task, Task):
                await decision_handler(
                    build_fail_task_decision(
                        task=task,
                        reason="Task was cancelled by system.",
                        allow_failover=False,
                    ),
                )
            else:
                logger.debug(
                    "Worker loop cancelled while waiting for task. Worker shutting down cleanly.",
                )
            break
        except RECOVERABLE_EXCEPTIONS as exception:
            log_exception(
                logger,
                exception,
                message=f"Critical error in orchestrator worker-{worker_id} loop",
                operation=OPERATION_ORCHESTRATOR_QUEUE_WORKER_LOOP,
                details={"worker_id": worker_id},
                level="critical",
            )
            if task is not None and isinstance(task, Task):
                await decision_handler(
                    build_fail_task_decision(
                        task=task,
                        reason=f"Worker loop error: {exception}",
                        allow_failover=False,
                    ),
                )
            await queue.orchestrator_deps.bus.publish(
                SystemMainStateOverrideEvent(
                    state=SoAIMainState.ERROR,
                    duration_sec=10,
                    reason=f"Critical error in Orchestrator worker: {exception}",
                ),
            )


async def process_task_from_queue(queue: QueueServiceView, task: Task) -> list[QueueDecision]:
    logger = get_logger(LOGGER_NAME)
    decisions: list[QueueDecision] = []
    try:
        await queue.tracking.register_active_task(task)
        task, cancel_decision = await queue.ensure_prompt_slot_and_cancel_if_cancelled(task)
        if cancel_decision:
            decisions.append(cancel_decision)
            return decisions
        context = task.require_orchestration_context()
        if context.is_requeued and (not context.parameter_snapshot):
            logger.debug(
                "Rebuilding parameter snapshot for re-queued failover task [%s].",
                task.task_id,
            )
            task, parameter_snapshot = await rebuild_requeued_parameter_state(queue, task)
            if not parameter_snapshot:
                decisions.append(
                    build_fail_task_decision(
                        task=task,
                        reason="Could not build parameter snapshot for failover model.",
                        allow_failover=False,
                    ),
                )
                return decisions
            cancel_decision = await queue.cancel_if_cancelled(task)
            if cancel_decision:
                decisions.append(cancel_decision)
                return decisions
            context = task.require_orchestration_context()
        if not context.execution_universal_ids:
            if context.event is None:
                decisions.append(
                    build_fail_task_decision(
                        task=task,
                        reason="Task has no inference event for planning.",
                        allow_failover=False,
                    ),
                )
                return decisions
            decisions.append(build_plan_required_decision(task))
            return decisions
        universal_id = context.execution_universal_ids[0]
        cancel_decision = await queue.cancel_if_cancelled(task)
        if cancel_decision:
            decisions.append(cancel_decision)
            return decisions
        resolved_model, error_reason = await resolve_orchestrator_model(
            queue.orchestrator_deps.model_information_service,
            universal_id=universal_id,
            require_canonical_universal_id=False,
        )
        if resolved_model is None:
            decisions.append(
                build_fail_task_decision(
                    task=task,
                    reason=error_reason or f"Model info for {universal_id} is invalid.",
                    allow_failover=False,
                ),
            )
            return decisions
        decisions.append(
            build_dispatch_candidate_decision(
                task=task,
                model_info=resolved_model.model_info,
                plugin_name=resolved_model.plugin_name,
                routing_key=resolved_model.universal_id,
                from_queue=True,
            ),
        )
        return decisions
    except RECOVERABLE_EXCEPTIONS as exception:
        log_exception(
            logger,
            exception,
            message=f"Critical error processing task [{task.task_id}]",
            operation=OPERATION_ORCHESTRATOR_PROCESS_TASK_FROM_QUEUE,
        )
        decisions.append(
            build_fail_task_decision(
                task=task,
                reason=f"Worker error: {exception}",
                allow_failover=False,
            ),
        )
        return decisions
