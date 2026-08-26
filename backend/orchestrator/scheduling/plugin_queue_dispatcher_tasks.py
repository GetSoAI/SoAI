"""SoAI - Plugin queue dispatcher task registration [backend/orchestrator/scheduling/plugin_queue_dispatcher_tasks.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import functools
from collections.abc import Callable

from core.logging.protocols import TraceLogger
from core.runtime.soai_identifiers import build_soai_id, safe_or_hashed_segment
from core.tasks.asyncio_task_spawner import spawn_tracked_task
from orchestrator.scheduling.dispatching_dependencies import (
    SchedulerDispatchingDependencies,
)
from orchestrator.scheduling.plugin_queue_dispatcher import PluginQueueDispatcherLoop

__all__ = ("ensure_plugin_queue_dispatcher",)


async def ensure_plugin_queue_dispatcher(
    *,
    deps: SchedulerDispatchingDependencies,
    plugin_queue_dispatcher_loop: PluginQueueDispatcherLoop,
    dispatcher_lock: asyncio.Lock,
    plugin_queue_dispatchers: dict[str, asyncio.Task[None]],
    cleanup_plugin_queue_dispatcher: Callable[[str, asyncio.Task[None]], None],
    plugin_name: str,
    logger: TraceLogger,
) -> None:
    async with dispatcher_lock:
        dispatcher = plugin_queue_dispatchers.get(plugin_name)
        if dispatcher and dispatcher.done():
            plugin_queue_dispatchers.pop(plugin_name, None)
            dispatcher = None
        if dispatcher is not None:
            return
        logger.trace(
            "Spawning new plugin queue dispatcher for plugin '%s'.",
            plugin_name,
        )
        dispatcher_task = spawn_tracked_task(
            plugin_queue_dispatcher_loop.run(plugin_name),
            owner="plugin_queue_dispatcher",
            logger=logger,
            metadata={"plugin": plugin_name},
            cancellation_id=build_soai_id(
                (
                    "sys",
                    "orchestrator",
                    "plugin_queue",
                    safe_or_hashed_segment(plugin_name),
                ),
            ),
            cancellation_binder=deps.cancellation_binder,
            finalizer_tracker=deps.finalizer_tracker,
            name=f"orchestrator-plugin-queue-{plugin_name}",
        )
        plugin_queue_dispatchers[plugin_name] = dispatcher_task
        dispatcher_task.add_done_callback(
            functools.partial(cleanup_plugin_queue_dispatcher, plugin_name),
        )
