"""SoAI - Scheduler dispatching purge operations [backend/orchestrator/scheduling/dispatching_purge.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable

from core.concurrency.task_groups import cancel_and_await
from core.logging.trace import get_logger
from core.tasks.enums import TaskStatus
from core.tasks.task import Task
from orchestrator.internal_protocols import OrchestratorTaskOutcomesProtocol

__all__ = (
    "cancel_all_plugin_queue_dispatchers",
    "cancel_and_drain_plugin_queue",
)

LOGGER_NAME = "SoAI.orchestrator.scheduling.dispatching_purge"


async def cancel_all_plugin_queue_dispatchers(
    *,
    dispatcher_lock: asyncio.Lock,
    plugin_queue_dispatchers: dict[str, asyncio.Task[None]],
) -> None:
    logger = get_logger(LOGGER_NAME)
    async with dispatcher_lock:
        dispatchers = [
            dispatcher
            for dispatcher in plugin_queue_dispatchers.values()
            if dispatcher is not None and not dispatcher.done()
        ]
    if dispatchers:
        dispatcher_count = len(dispatchers)
        cancel_message = f"Cancelling {dispatcher_count} plugin queue dispatcher tasks..."
        await cancel_and_await(
            dispatchers,
            logger=logger,
            task_label="plugin queue dispatchers",
            message=cancel_message,
            log_level=logging.WARNING,
        )


async def cancel_and_drain_plugin_queue(
    *,
    dispatcher_lock: asyncio.Lock,
    plugin_queue_dispatchers: dict[str, asyncio.Task[None]],
    plugin_name: str,
    reason: str,
    drain_plugin_queue: Callable[[str], Awaitable[list[Task]]],
    outcomes: OrchestratorTaskOutcomesProtocol,
) -> None:
    logger = get_logger(LOGGER_NAME)
    normalized_reason = (
        str(reason or "").strip() or f"Plugin queue for '{plugin_name}' is being purged."
    )
    if not plugin_name:
        return
    dispatcher: asyncio.Task[None] | None = None
    async with dispatcher_lock:
        dispatcher = plugin_queue_dispatchers.get(plugin_name)
        if dispatcher and dispatcher.done():
            plugin_queue_dispatchers.pop(plugin_name, None)
            dispatcher = None
    if dispatcher:
        await cancel_and_await(
            [dispatcher],
            logger=logger,
            task_label="plugin queue dispatcher",
            message=f"Cancelling plugin queue dispatcher for '{plugin_name}'...",
            log_level=logging.WARNING,
        )
    drained = await drain_plugin_queue(plugin_name)
    drained_tasks = [item for item in drained if isinstance(item, Task)]
    if drained_tasks:
        fail_tasks = [
            outcomes.fail_task(
                task,
                normalized_reason,
                allow_failover=True,
            )
            for task in drained_tasks
            if task is not None and task.status != TaskStatus.CANCELLED
        ]
        await asyncio.gather(*fail_tasks, return_exceptions=False)
