"""SoAI - Scheduler loop runtime execution [backend/orchestrator/scheduling/loop_runtime.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.di.validation import require_dependencies
from core.errors.exception_logging import log_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger
from core.orchestrator.scheduler_work import SCHEDULER_WORK_TYPE_SHUTDOWN
from core.tasks.asyncio_task_spawner import spawn_tracked_task
from core.tasks.task_cancellation_ops import generate_system_cancellation_id
from orchestrator.scheduling.loop_error_handling import handle_scheduler_loop_failure

if TYPE_CHECKING:
    from core.orchestrator.protocols_queue import OrchestratorQueueProtocol
    from orchestrator.scheduling.decisions import SchedulerDecisions
    from orchestrator.scheduling.work_queue import SchedulerWorkQueueState
    from orchestrator.types import OrchestratorDependencies

__all__ = ("SchedulerLoopRuntimeDependencies", "run_scheduler_loop")

LOGGER_NAME = "SoAI.orchestrator.scheduling.loop_runtime"
OPERATION = "orchestrator.scheduling.service.orchestrator_scheduler.scheduler_loop"


@dataclass(frozen=True, slots=True)
class SchedulerLoopRuntimeDependencies:
    orchestrator_deps: OrchestratorDependencies
    queue: OrchestratorQueueProtocol
    decisions: SchedulerDecisions
    work_queue_state: SchedulerWorkQueueState
    shutdown_event: asyncio.Event

    def __post_init__(self) -> None:
        require_dependencies(
            owner="SchedulerLoopRuntimeDependencies",
            decisions=self.decisions,
            orchestrator_deps=self.orchestrator_deps,
            queue=self.queue,
            shutdown_event=self.shutdown_event,
            work_queue_state=self.work_queue_state,
        )


async def run_scheduler_loop(
    deps: SchedulerLoopRuntimeDependencies,
    *,
    get_scheduler_safety_net_delay: Callable[[], float | None],
) -> None:
    logger = get_logger(LOGGER_NAME)
    while not deps.shutdown_event.is_set():
        try:
            try:
                first_item, work_items, last_log_time = (
                    await deps.work_queue_state.await_work_batch()
                )
            except TimeoutError:
                continue
            if deps.shutdown_event.is_set() or first_item.work_type == SCHEDULER_WORK_TYPE_SHUTDOWN:
                break
            now = time.monotonic()
            if now - last_log_time > 2.0:
                logger.trace(
                    "Scheduler woken up. Processing %s distinct work items.",
                    len(work_items),
                )
                deps.work_queue_state.update_log_time(now)
            await deps.decisions.evaluate_and_execute(work_items)
            if await deps.queue.tracking.has_pending_tasks():
                await _schedule_safety_net_cycle(deps, get_scheduler_safety_net_delay)
        except asyncio.CancelledError:
            break
        except RECOVERABLE_EXCEPTIONS as exception:
            log_exception(
                logger,
                exception,
                message="Scheduler loop failed; continuing.",
                operation=OPERATION,
                level="warning",
            )
            handle_scheduler_loop_failure(logger, deps.orchestrator_deps, exception)
        except (RuntimeError, TypeError) as exception:
            handle_scheduler_loop_failure(logger, deps.orchestrator_deps, exception)
            raise


async def _schedule_safety_net_cycle(
    deps: SchedulerLoopRuntimeDependencies,
    get_scheduler_safety_net_delay: Callable[[], float | None],
) -> None:
    delay = get_scheduler_safety_net_delay() or 0.5
    if delay <= 0:
        delay = 0.1
    should_spawn = await deps.work_queue_state.schedule_safety_net()
    if not should_spawn:
        return
    logger = get_logger(LOGGER_NAME)
    _ = spawn_tracked_task(
        deps.work_queue_state.safety_net_cycle(delay),
        name="scheduler-safety-net-cycle",
        owner="scheduler_safety_net",
        logger=logger,
        cancellation_binder=deps.orchestrator_deps.task_cancellation_binder,
        finalizer_tracker=deps.orchestrator_deps.task_finalizer_tracker,
        cancellation_id=generate_system_cancellation_id("scheduler_safety_net"),
    )
