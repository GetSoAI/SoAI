"""SoAI - Plugin queue dispatcher loop and dependencies [backend/orchestrator/scheduling/plugin_queue_dispatcher.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.concurrency.ephemeral_tasks import create_ephemeral_task
from core.concurrency.protocols import QueueGetNowaitProtocol
from core.concurrency.task_groups import (
    DEFAULT_CANCELLATION_TIMEOUT_SEC,
    cancel_and_await,
)
from core.di.validation import require_dependencies
from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception, log_handled_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.rate_limited_logger import RateLimitedLogger
from core.logging.trace import get_logger
from core.models.protocols import ModelInformationServiceProtocol
from core.orchestrator.protocols_queue import OrchestratorQueueProtocol
from core.plugins.protocols import PluginManagerProtocol
from core.runtime.soai_identifiers import build_soai_id, safe_or_hashed_segment
from core.state.protocols import StateAggregatorProtocol
from core.tasks.asyncio_task_spawner import spawn_tracked_task
from core.tasks.protocols import (
    CancellationHistoryProtocol,
    TaskCancellationBinderProtocol,
    TaskFinalizerTrackerProtocol,
    TaskRegistryProtocol,
)
from core.tasks.task import Task
from core.timing.constants import CONTROL_TIMEOUT_SEC, INTERACTIVE_TIMEOUT_SEC, LOCAL_IO_TIMEOUT_SEC
from orchestrator.internal_protocols import (
    OrchestratorCapacityProtocol,
    OrchestratorInferenceExecutorProtocol,
    OrchestratorTaskOutcomesProtocol,
)
from orchestrator.lifecycle.service_interfaces.internal_protocols import (
    OrchestratorLifecycleCoordinatorProtocol,
)
from orchestrator.scheduling.plugin_queue_dispatcher_worker_runtime import (
    resolve_plugin_queue_worker_count,
    run_plugin_queue_worker,
)

if TYPE_CHECKING:
    type _DispatchReadyStateCollection = set[str]
    type _PluginQueueCancellationBinder = TaskCancellationBinderProtocol
    type _PluginQueueFinalizerTracker = TaskFinalizerTrackerProtocol

__all__ = (
    "PluginQueueDispatcherDependencies",
    "PluginQueueDispatcherLoop",
)

LOGGER_NAME = "SoAI.orchestrator.scheduling.plugin_queue_dispatcher"
OPERATION_ORCHESTRATOR_PLUGIN_QUEUE_DISPATCHER_RESIZE_BINDING = (
    "orchestrator.plugin_queue_dispatcher.resize_binding"
)
OPERATION_ORCHESTRATOR_PLUGIN_QUEUE_DISPATCHER_SHUTDOWN_BINDING = (
    "orchestrator.plugin_queue_dispatcher.shutdown_binding"
)
OPERATION_ORCHESTRATOR_PLUGIN_QUEUE_DISPATCHER_WORKER_CRASH = (
    "orchestrator.plugin_queue_dispatcher.worker_crash"
)


@dataclass(frozen=True, slots=True)
class PluginQueueDispatcherDependencies:
    queue: OrchestratorQueueProtocol
    lifecycle: OrchestratorLifecycleCoordinatorProtocol
    inference_executor: OrchestratorInferenceExecutorProtocol
    outcomes: OrchestratorTaskOutcomesProtocol
    capacity: OrchestratorCapacityProtocol
    cancellation_history: CancellationHistoryProtocol
    cancellation_binder: _PluginQueueCancellationBinder
    finalizer_tracker: _PluginQueueFinalizerTracker
    task_registry: TaskRegistryProtocol
    state_aggregator: StateAggregatorProtocol
    plugin_manager: PluginManagerProtocol
    model_information_service: ModelInformationServiceProtocol
    shutdown_event: asyncio.Event
    dispatch_ready_states: _DispatchReadyStateCollection
    finalize_plugin_queue_shutdown: Callable[
        [str, QueueGetNowaitProtocol[Task] | None, list[Task]],
        Awaitable[None],
    ]
    claim_plugin_queue_dispatcher_idle_exit: Callable[[str], Awaitable[bool]]

    def __post_init__(self) -> None:
        require_dependencies(
            owner="PluginQueueDispatcherDependencies",
            cancellation_binder=self.cancellation_binder,
            cancellation_history=self.cancellation_history,
            capacity=self.capacity,
            dispatch_ready_states=self.dispatch_ready_states,
            finalize_plugin_queue_shutdown=self.finalize_plugin_queue_shutdown,
            claim_plugin_queue_dispatcher_idle_exit=self.claim_plugin_queue_dispatcher_idle_exit,
            finalizer_tracker=self.finalizer_tracker,
            lifecycle=self.lifecycle,
            inference_executor=self.inference_executor,
            plugin_manager=self.plugin_manager,
            model_information_service=self.model_information_service,
            outcomes=self.outcomes,
            queue=self.queue,
            shutdown_event=self.shutdown_event,
            state_aggregator=self.state_aggregator,
            task_registry=self.task_registry,
        )


class PluginQueueDispatcherLoop:
    def __init__(self, deps: PluginQueueDispatcherDependencies) -> None:
        self._deps = deps

    def _resolve_worker_count(self, plugin_name: str) -> int:
        return resolve_plugin_queue_worker_count(self._deps, plugin_name)

    async def run(self, plugin_name: str) -> None:
        logger = get_logger(LOGGER_NAME)
        stop_event = asyncio.Event()
        requeue_warner = RateLimitedLogger(interval_seconds=INTERACTIVE_TIMEOUT_SEC)
        workers_by_index: dict[int, asyncio.Task[None]] = {}
        active_tasks_by_worker: dict[int, Task] = {}
        idle_exit_claimed = False
        try:
            while (not self._deps.shutdown_event.is_set()) and (not stop_event.is_set()):
                had_workers = bool(workers_by_index)
                active_workers = 0
                for worker_index, worker_task in list(workers_by_index.items()):
                    if not worker_task.done():
                        active_workers += 1
                        continue
                    workers_by_index.pop(worker_index, None)
                    try:
                        worker_task.result()
                    except asyncio.CancelledError:
                        continue
                    except RECOVERABLE_EXCEPTIONS as exception:
                        coerced = coerce_to_soai_error(
                            exception,
                            operation="orchestrator.plugin_queue_dispatcher.worker_crash",
                        )
                        log_exception(
                            logger,
                            coerced,
                            message=f"Plugin queue worker crashed for '{plugin_name}'.",
                            operation=OPERATION_ORCHESTRATOR_PLUGIN_QUEUE_DISPATCHER_WORKER_CRASH,
                            level="error",
                        )
                if had_workers and active_workers == 0:
                    if active_tasks_by_worker:
                        continue
                    if await self._deps.claim_plugin_queue_dispatcher_idle_exit(plugin_name):
                        idle_exit_claimed = True
                        logger.trace(
                            "Plugin queue dispatcher for '%s' is idle. Shutting down.",
                            plugin_name,
                        )
                        return
                desired_workers = self._resolve_worker_count(plugin_name)
                for worker_index in range(desired_workers):
                    existing = workers_by_index.get(worker_index)
                    if existing is not None and (not existing.done()):
                        continue
                    workers_by_index[worker_index] = spawn_tracked_task(
                        run_plugin_queue_worker(
                            self._deps,
                            plugin_name=plugin_name,
                            worker_index=worker_index,
                            stop_event=stop_event,
                            active_tasks_by_worker=active_tasks_by_worker,
                            requeue_warner=requeue_warner,
                        ),
                        owner="plugin_queue_worker",
                        logger=logger,
                        metadata={"plugin": plugin_name, "worker_index": worker_index},
                        cancellation_id=build_soai_id(
                            (
                                "sys",
                                "orchestrator",
                                "plugin_queue_worker",
                                safe_or_hashed_segment(plugin_name),
                                safe_or_hashed_segment(str(worker_index)),
                            ),
                        ),
                        cancellation_binder=self._deps.cancellation_binder,
                        finalizer_tracker=self._deps.finalizer_tracker,
                        name=f"plugin-queue-worker-{plugin_name}-{worker_index}",
                    )
                swap_event: asyncio.Event | None = None
                try:
                    binding = await self._deps.capacity.get_existing_plugin_queue_binding(
                        plugin_name,
                    )
                    if binding is not None:
                        _, swap_event = binding
                except RECOVERABLE_EXCEPTIONS as exception:
                    log_handled_exception(
                        logger,
                        exception,
                        message="Failed to obtain plugin queue binding during resize check (non-critical).",
                        operation=OPERATION_ORCHESTRATOR_PLUGIN_QUEUE_DISPATCHER_RESIZE_BINDING,
                        level="debug",
                        details={"plugin": plugin_name},
                    )
                waiters: list[asyncio.Task[bool]] = [
                    create_ephemeral_task(
                        self._deps.shutdown_event.wait(),
                        name="plugin-queue-shutdown-waiter",
                    ),
                    create_ephemeral_task(
                        stop_event.wait(),
                        name="plugin-queue-stop-waiter",
                    ),
                ]
                if swap_event is not None:
                    waiters.append(
                        create_ephemeral_task(
                            swap_event.wait(),
                            name="plugin-queue-swap-waiter",
                        ),
                    )
                _done, pending = await asyncio.wait(
                    waiters,
                    timeout=LOCAL_IO_TIMEOUT_SEC,
                    return_when=asyncio.FIRST_COMPLETED,
                )
                for task in pending:
                    task.cancel()
                await cancel_and_await(pending, timeout_sec=DEFAULT_CANCELLATION_TIMEOUT_SEC)
        finally:
            logger.trace("Plugin queue dispatcher for '%s' is shutting down.", plugin_name)
            should_cancel_workers = self._deps.shutdown_event.is_set() or bool(workers_by_index)
            stop_event.set()
            if should_cancel_workers:
                await cancel_and_await(
                    list(workers_by_index.values()),
                    logger=logger,
                    task_label="plugin queue workers",
                    message=f"Cancelling {len(workers_by_index)} plugin queue workers...",
                    timeout_sec=CONTROL_TIMEOUT_SEC,
                )
            plugin_queue = None
            try:
                binding = await self._deps.capacity.get_existing_plugin_queue_binding(plugin_name)
                if binding is not None:
                    plugin_queue, _ = binding
            except RECOVERABLE_EXCEPTIONS as exception:
                log_handled_exception(
                    logger,
                    exception,
                    message="Failed to obtain plugin queue binding during shutdown (non-critical).",
                    operation=OPERATION_ORCHESTRATOR_PLUGIN_QUEUE_DISPATCHER_SHUTDOWN_BINDING,
                    level="debug",
                    details={"plugin": plugin_name},
                )
            if idle_exit_claimed:
                plugin_queue = None
            active_tasks = list(active_tasks_by_worker.values())
            active_tasks_by_worker.clear()
            await self._deps.finalize_plugin_queue_shutdown(
                plugin_name,
                plugin_queue,
                active_tasks,
            )
