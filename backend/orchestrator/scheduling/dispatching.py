"""SoAI - Task dispatching to plugin queues and workers [backend/orchestrator/scheduling/dispatching.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import logging

from core.concurrency.protocols import QueueGetNowaitProtocol
from core.concurrency.task_groups import cancel_and_await
from core.logging.rate_limited_logger import RateLimitedLogger
from core.logging.trace import get_logger
from core.runtime.soai_identifiers import build_soai_id, safe_or_hashed_segment
from core.tasks.asyncio_task_spawner import spawn_tracked_task
from core.tasks.task import Task
from core.timing.constants import CONTROL_TIMEOUT_SEC
from core.types.json import JSONDict
from orchestrator.scheduling import dispatching_admission, dispatching_purge
from orchestrator.scheduling.dispatch_shutdown import finalize_plugin_queue_shutdown
from orchestrator.scheduling.dispatching_dependencies import (
    SchedulerDispatchingDependencies,
)
from orchestrator.scheduling.plugin_queue_dispatcher import (
    PluginQueueDispatcherDependencies,
    PluginQueueDispatcherLoop,
)
from orchestrator.scheduling.purge_state import PurgeStateSnapshot, SchedulerPurgeState
from orchestrator.scheduling.waiter_dispatching import dispatch_waiters_for_ready_model

__all__ = ("SchedulerDispatching",)

LOGGER_NAME = "SoAI.orchestrator.scheduling.dispatching"


class SchedulerDispatching:
    def __init__(self, deps: SchedulerDispatchingDependencies) -> None:
        self._deps = deps
        self._dispatcher_lock = asyncio.Lock()
        self._plugin_queue_dispatchers: dict[str, asyncio.Task[None]] = {}
        self._purge_state = SchedulerPurgeState()
        self._dispatch_waiters_not_ready_warners: dict[str, RateLimitedLogger] = {}
        self._dispatch_not_ready_warners: dict[str, RateLimitedLogger] = {}
        self._plugin_queue_dispatcher_loop = PluginQueueDispatcherLoop(
            PluginQueueDispatcherDependencies(
                queue=self._deps.queue,
                lifecycle=self._deps.lifecycle,
                inference_executor=self._deps.inference_executor,
                outcomes=self._deps.outcomes,
                capacity=self._deps.capacity,
                cancellation_history=self._deps.cancellation_history,
                cancellation_binder=self._deps.cancellation_binder,
                finalizer_tracker=self._deps.finalizer_tracker,
                task_registry=self._deps.task_registry,
                state_aggregator=self._deps.state_aggregator,
                plugin_manager=self._deps.plugin_manager,
                model_information_service=self._deps.model_information_service,
                shutdown_event=self._deps.shutdown_event,
                dispatch_ready_states=self._deps.dispatch_ready_states,
                finalize_plugin_queue_shutdown=self._finalize_plugin_queue_shutdown,
                claim_plugin_queue_dispatcher_idle_exit=self._claim_plugin_queue_dispatcher_idle_exit,
            ),
        )

    async def shutdown(self) -> None:
        logger = get_logger(LOGGER_NAME)
        async with self._dispatcher_lock:
            dispatchers = list(self._plugin_queue_dispatchers.values())
            self._plugin_queue_dispatchers.clear()
        if dispatchers:
            await cancel_and_await(
                dispatchers,
                logger=logger,
                task_label="plugin queue dispatchers",
                message=f"Cancelling {len(dispatchers)} plugin queue dispatcher tasks...",
                log_level=logging.WARNING,
                timeout_sec=CONTROL_TIMEOUT_SEC,
            )

    async def begin_global_purge(self, *, reason: str) -> None:
        await self._purge_state.begin_global_purge(reason=reason)

    async def finish_global_purge(self) -> None:
        await self._purge_state.finish_global_purge()

    async def begin_plugin_purge(self, plugin_name: str, *, reason: str) -> None:
        await self._purge_state.begin_plugin_purge(plugin_name, reason=reason)

    async def finish_plugin_purge(self, plugin_name: str) -> None:
        await self._purge_state.finish_plugin_purge(plugin_name)

    async def cancel_all_plugin_queue_dispatchers(self) -> None:
        await dispatching_purge.cancel_all_plugin_queue_dispatchers(
            dispatcher_lock=self._dispatcher_lock,
            plugin_queue_dispatchers=self._plugin_queue_dispatchers,
        )

    async def cancel_and_drain_plugin_queue(self, plugin_name: str, *, reason: str) -> None:
        await dispatching_purge.cancel_and_drain_plugin_queue(
            dispatcher_lock=self._dispatcher_lock,
            plugin_queue_dispatchers=self._plugin_queue_dispatchers,
            plugin_name=plugin_name,
            reason=reason,
            drain_plugin_queue=self._deps.capacity.drain_plugin_queue,
            outcomes=self._deps.outcomes,
        )

    async def get_status_snapshot(self) -> JSONDict:
        async with self._dispatcher_lock:
            dispatcher_count = len(self._plugin_queue_dispatchers)
        return {"scheduler_dispatcher_count": dispatcher_count}

    async def dispatch_waiters(
        self,
        pending_key: str,
        plugin_name: str,
        model_info: JSONDict,
    ) -> None:
        await dispatch_waiters_for_ready_model(
            deps=self._deps,
            dispatch_waiters_not_ready_warners=self._dispatch_waiters_not_ready_warners,
            pending_key=pending_key,
            plugin_name=plugin_name,
            model_info=model_info,
        )

    async def dispatch_task_to_plugin_queue(self, task: Task, plugin_name: str) -> None:
        await dispatching_admission.dispatch_task_to_plugin_queue(
            deps=self._deps,
            plugin_queue_dispatcher_loop=self._plugin_queue_dispatcher_loop,
            dispatch_not_ready_warners=self._dispatch_not_ready_warners,
            dispatcher_lock=self._dispatcher_lock,
            plugin_queue_dispatchers=self._plugin_queue_dispatchers,
            purge_state=self._purge_state,
            cleanup_plugin_queue_dispatcher=self._cleanup_plugin_queue_dispatcher,
            task=task,
            plugin_name=plugin_name,
        )

    def _cleanup_plugin_queue_dispatcher(self, plugin_name: str, task: asyncio.Task[None]) -> None:
        logger = get_logger(LOGGER_NAME)
        _ = spawn_tracked_task(
            self._async_cleanup_plugin_queue_dispatcher(plugin_name, task),
            owner="plugin_queue_cleanup",
            logger=logger,
            metadata={"plugin": plugin_name},
            cancellation_id=build_soai_id(
                (
                    "sys",
                    "orchestrator",
                    "plugin_queue_cleanup",
                    safe_or_hashed_segment(plugin_name),
                ),
            ),
            cancellation_binder=self._deps.cancellation_binder,
            finalizer_tracker=self._deps.finalizer_tracker,
            name=f"orchestrator-plugin-queue-cleanup-{plugin_name}",
        )

    async def _async_cleanup_plugin_queue_dispatcher(
        self,
        plugin_name: str,
        task: asyncio.Task[None],
    ) -> None:
        logger = get_logger(LOGGER_NAME)
        async with self._dispatcher_lock:
            current_dispatcher = self._plugin_queue_dispatchers.get(plugin_name)
            if current_dispatcher is task:
                self._plugin_queue_dispatchers.pop(plugin_name, None)
        self._dispatch_waiters_not_ready_warners.pop(plugin_name, None)
        self._dispatch_not_ready_warners.pop(plugin_name, None)
        logger.trace(
            "Plugin queue dispatcher for '%s' has shut down and been cleaned up.",
            plugin_name,
        )

    async def _snapshot_purge_state(self, plugin_name: str) -> PurgeStateSnapshot:
        return await self._purge_state.snapshot(plugin_name)

    async def _claim_plugin_queue_dispatcher_idle_exit(self, plugin_name: str) -> bool:
        current_task = asyncio.current_task()
        async with self._dispatcher_lock:
            registered_dispatcher = self._plugin_queue_dispatchers.get(plugin_name)
            if registered_dispatcher is not current_task:
                return False
            if not await self._deps.capacity.is_queue_empty(plugin_name):
                return False
            self._plugin_queue_dispatchers.pop(plugin_name, None)
            return True

    async def _finalize_plugin_queue_shutdown(
        self,
        plugin_name: str,
        queue: QueueGetNowaitProtocol[Task] | None,
        active_tasks: list[Task],
    ) -> None:
        await finalize_plugin_queue_shutdown(
            plugin_name=plugin_name,
            queue=queue,
            active_tasks=active_tasks,
            deps=self._deps,
            snapshot_purge_state=self._snapshot_purge_state,
            plugin_queue_dispatchers=self._plugin_queue_dispatchers,
            dispatcher_lock=self._dispatcher_lock,
        )
