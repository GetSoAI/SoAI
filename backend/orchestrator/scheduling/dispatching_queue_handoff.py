"""SoAI - Scheduler dispatch queue handoff admission [backend/orchestrator/scheduling/dispatching_queue_handoff.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Callable

from core.concurrency.cancellation_cleanup import (
    current_task_has_pending_cancellation,
    uncancel_then_cleanup,
    wait_for_task_completion,
)
from core.concurrency.ephemeral_tasks import create_ephemeral_task
from core.concurrency.lock_registry import TTLAsyncLockRegistry
from core.errors.exception_logging import log_handled_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from core.logging.protocols import TraceLogger
from core.tasks.task import Task
from core.tasks.type_catalog import is_orchestrated_inference_task_type
from orchestrator.capacity.plugin_queue.errors import PluginQueueFullError
from orchestrator.queueing.cycle_errors import QueueCycleAlreadyOpenError
from orchestrator.requeue_attempts import (
    build_scheduler_requeue_attempt_spec,
    execute_requeue_attempt,
)
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
from orchestrator.scheduling.owner_dispatch_admission import admit_owner_dispatch
from orchestrator.scheduling.plugin_queue_dispatcher import PluginQueueDispatcherLoop
from orchestrator.scheduling.plugin_queue_dispatcher_tasks import (
    ensure_plugin_queue_dispatcher,
)
from orchestrator.scheduling.purge_state import SchedulerPurgeState

__all__ = ("admit_dispatch_queue_handoff",)

OPERATION = "orchestrator.dispatch_task_to_plugin_queue"


async def admit_dispatch_queue_handoff(
    *,
    deps: SchedulerDispatchingDependencies,
    plugin_queue_dispatcher_loop: PluginQueueDispatcherLoop,
    dispatcher_lock: asyncio.Lock,
    owner_admission_locks: TTLAsyncLockRegistry[tuple[str, str]],
    plugin_queue_dispatchers: dict[str, asyncio.Task[None]],
    purge_state: SchedulerPurgeState,
    cleanup_plugin_queue_dispatcher: Callable[[str, asyncio.Task[None]], None],
    task: Task,
    plugin_name: str,
    logger: TraceLogger,
) -> None:
    enqueued = False
    ownership_released_on_cancel = False
    owner_admitted = False

    async def enqueue_task() -> None:
        nonlocal task, enqueued, ownership_released_on_cancel, owner_admitted
        try:
            admission_operation = create_ephemeral_task(
                admit_owner_dispatch(deps, task, plugin_name, logger),
                name="orchestrator-owner-dispatch-admission",
                log_exceptions=False,
            )
            admitted_task: Task | None = None
            try:
                await uncancel_then_cleanup(admission_operation)
            finally:
                await wait_for_task_completion(
                    admission_operation, retain_resources_until_complete=True
                )
                if not admission_operation.cancelled():
                    admitted_task = admission_operation.result()
                    if admitted_task is not None:
                        task = admitted_task
                        owner_admitted = is_orchestrated_inference_task_type(task.task_type)
            if admitted_task is None:
                return
            if current_task_has_pending_cancellation():
                raise asyncio.CancelledError()
            await deps.ensure_plugin_capacity(plugin_name)
            await deps.capacity.enqueue_plugin_task(plugin_name, task)
            enqueued = True
            dispatcher_start_operation = create_ephemeral_task(
                ensure_plugin_queue_dispatcher(
                    deps=deps,
                    plugin_queue_dispatcher_loop=plugin_queue_dispatcher_loop,
                    dispatcher_lock=dispatcher_lock,
                    plugin_queue_dispatchers=plugin_queue_dispatchers,
                    cleanup_plugin_queue_dispatcher=cleanup_plugin_queue_dispatcher,
                    plugin_name=plugin_name,
                    logger=logger,
                ),
                name="orchestrator-dispatch-worker-start",
                log_exceptions=False,
            )
            try:
                await uncancel_then_cleanup(dispatcher_start_operation)
            finally:
                await wait_for_task_completion(
                    dispatcher_start_operation, retain_resources_until_complete=True
                )
                if not dispatcher_start_operation.cancelled():
                    dispatcher_start_operation.result()
            if current_task_has_pending_cancellation():
                raise asyncio.CancelledError()
            if not owner_admitted:
                await mark_task_dispatched_after_enqueue(
                    deps.task_registry,
                    task,
                    plugin_name=plugin_name,
                )
        except asyncio.CancelledError:
            if not enqueued:
                if owner_admitted:
                    requeue_operation = create_ephemeral_task(
                        execute_requeue_attempt(
                            deps.queue,
                            deps.task_registry,
                            task,
                            spec=build_scheduler_requeue_attempt_spec(
                                logger=logger,
                                operation="orchestrator.dispatch_task_to_plugin_queue.cancelled_requeue",
                            ),
                            outcomes=deps.outcomes,
                        ),
                        name="orchestrator-cancelled-dispatch-requeue",
                        log_exceptions=False,
                    )
                    try:
                        await uncancel_then_cleanup(requeue_operation)
                    finally:
                        await wait_for_task_completion(
                            requeue_operation, retain_resources_until_complete=True
                        )
                        if not requeue_operation.cancelled():
                            requeue_operation.result()
                else:
                    await uncancel_then_cleanup(release_dispatch_admission_ownership(deps, task))
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
        except HANDLED_RUNTIME_EXCEPTIONS as exception:
            if not enqueued:
                await fail_released_dispatch_task(
                    deps, task, "Dispatch admission failed.", allow_failover=False
                )
                raise
            await resolve_dispatch_recoverable_exception(
                deps=deps,
                task=task,
                plugin_name=plugin_name,
                exception=exception,
                enqueued=True,
                logger=logger,
            )

    try:
        async with owner_admission_locks.lock((task.owner_type, task.owner_id)):
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
            await uncancel_then_cleanup(release_dispatch_admission_ownership(deps, task))
        raise
