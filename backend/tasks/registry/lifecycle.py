"""SoAI - Task registry lifecycle wiring [backend/tasks/registry/lifecycle.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import functools

from core.events.subscriptions import subscribe_many
from core.events.types_tasks import CancelTaskCommand
from core.logging.trace import get_logger
from core.runtime.soai_identifiers import create_system_id
from core.tasks.asyncio_task_spawner import spawn_tracked_task
from core.tasks.protocols import (
    TaskCancellationBinderProtocol,
    TaskFinalizerTrackerProtocol,
    TaskRegistryProtocol,
)
from tasks.registry.cancellation_handlers import handle_cancel_task_command
from tasks.registry.maintenance import run_cleanup_loop

__all__ = (
    "initialize_task_registry_subscriptions",
    "start_task_registry_cleanup_loop",
)

LOGGER_NAME = "SoAI.tasks.registry.lifecycle"


def initialize_task_registry_subscriptions(registry: TaskRegistryProtocol) -> None:
    subscribe_many(
        registry.event_bus,
        {
            CancelTaskCommand: functools.partial(handle_cancel_task_command, registry=registry),
        },
    )


def start_task_registry_cleanup_loop(
    registry: TaskRegistryProtocol,
    *,
    current_cleanup_task: asyncio.Task[None] | None,
    cancellation_binder: TaskCancellationBinderProtocol,
    finalizer_tracker: TaskFinalizerTrackerProtocol,
) -> asyncio.Task[None]:
    if current_cleanup_task is not None and not current_cleanup_task.done():
        return current_cleanup_task
    logger = get_logger(LOGGER_NAME)
    return spawn_tracked_task(
        run_cleanup_loop(registry, logger=logger),
        name="task-registry-cleanup",
        logger=logger,
        cancellation_binder=cancellation_binder,
        cancellation_id=create_system_id(
            subsystem="task_registry",
            owner="cleanup",
            include_random_suffix=False,
        ),
        owner="task_registry_cleanup",
        finalizer_tracker=finalizer_tracker,
    )
