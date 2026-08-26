"""SoAI - Scheduler dispatch queue handoff admission [backend/orchestrator/scheduling/dispatching_queue_handoff.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Callable

from core.errors.exception_logging import log_handled_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.protocols import TraceLogger
from core.tasks.errors import TASK_STATE_PERSISTENCE_FAILED_MESSAGE
from core.tasks.orchestration_persistence import persist_with_logging
from core.tasks.task import Task
from orchestrator.capacity.plugin_queue.errors import PluginQueueFullError
from orchestrator.queueing.cycle_errors import QueueCycleAlreadyOpenError
from orchestrator.scheduling.dispatch_rejections import (
    fail_released_dispatch_task,
    fail_released_purged_dispatch,
    release_dispatch_admission_ownership,
)
from orchestrator.scheduling.dispatching_dependencies import (
    SchedulerDispatchingDependencies,
)
from orchestrator.scheduling.dispatching_post_enqueue_status import (
    mark_task_dispatched_after_enqueue,
)
from orchestrator.scheduling.dispatching_recoverable_failure import (
    resolve_dispatch_recoverable_exception,
    resolve_plugin_queue_full_exception,
    resolve_queue_cycle_already_open_exception,
)
from orchestrator.scheduling.plugin_queue_dispatcher import PluginQueueDispatcherLoop
from orchestrator.scheduling.plugin_queue_dispatcher_tasks import (
    ensure_plugin_queue_dispatcher,
)
from orchestrator.scheduling.purge_state import SchedulerPurgeState

__all__ = ("admit_dispatch_queue_handoff",)

OPERATION = "orchestrator.dispatch_task_to_plugin_queue"
OPERATION_PERSIST_DISPATCH = "orchestrator.dispatch_task_to_plugin"


async def admit_dispatch_queue_handoff(
    *,
    deps: SchedulerDispatchingDependencies,
    plugin_queue_dispatcher_loop: PluginQueueDispatcherLoop,
    dispatcher_lock: asyncio.Lock,
    plugin_queue_dispatchers: dict[str, asyncio.Task[None]],
    purge_state: SchedulerPurgeState,
    cleanup_plugin_queue_dispatcher: Callable[[str, asyncio.Task[None]], None],
    task: Task,
    plugin_name: str,
    logger: TraceLogger,
) -> None:
    enqueued = False
    ownership_released_on_cancel = False

    async def enqueue_task() -> None:
        nonlocal enqueued, ownership_released_on_cancel
        try:
            success, _ = await persist_with_logging(
                deps.task_registry,
                task.task_id,
                logger=logger,
                operation=OPERATION_PERSIST_DISPATCH,
            )
            if not success:
                await fail_released_dispatch_task(
                    deps,
                    task,
                    TASK_STATE_PERSISTENCE_FAILED_MESSAGE,
                    allow_failover=False,
                )
                return
            await deps.ensure_plugin_capacity(plugin_name)
            await deps.capacity.enqueue_plugin_task(plugin_name, task)
            enqueued = True
            await ensure_plugin_queue_dispatcher(
                deps=deps,
                plugin_queue_dispatcher_loop=plugin_queue_dispatcher_loop,
                dispatcher_lock=dispatcher_lock,
                plugin_queue_dispatchers=plugin_queue_dispatchers,
                cleanup_plugin_queue_dispatcher=cleanup_plugin_queue_dispatcher,
                plugin_name=plugin_name,
                logger=logger,
            )
            await mark_task_dispatched_after_enqueue(
                deps.task_registry,
                task,
                plugin_name=plugin_name,
            )
        except asyncio.CancelledError:
            if not enqueued:
                await release_dispatch_admission_ownership(deps, task)
                ownership_released_on_cancel = True
            raise
        except PluginQueueFullError:
            await resolve_plugin_queue_full_exception(
                deps=deps,
                task=task,
                plugin_name=plugin_name,
                logger=logger,
            )
        except QueueCycleAlreadyOpenError as exception:
            await resolve_queue_cycle_already_open_exception(
                deps=deps,
                task=task,
                plugin_name=plugin_name,
                exception=exception,
                enqueued=enqueued,
                logger=logger,
            )
        except RECOVERABLE_EXCEPTIONS as exception:
            log_handled_exception(
                logger,
                exception,
                message="Dispatch admission recovered from a handled exception.",
                operation=OPERATION,
                details={"task_id": task.task_id, "plugin": plugin_name},
                level="debug",
            )
            await resolve_dispatch_recoverable_exception(
                deps=deps,
                task=task,
                plugin_name=plugin_name,
                exception=exception,
                enqueued=enqueued,
                logger=logger,
            )

    try:
        purge_snapshot = await purge_state.run_when_not_purging(plugin_name, enqueue_task)
        if purge_snapshot.is_purging:
            await fail_released_purged_dispatch(
                deps=deps,
                task=task,
                plugin_name=plugin_name,
                purge_snapshot=purge_snapshot,
            )
    except asyncio.CancelledError:
        if not enqueued and not ownership_released_on_cancel:
            await release_dispatch_admission_ownership(deps, task)
        raise
