"""SoAI - Plugin lifecycle active cancellation registration [backend/plugins/lifecycle_active_cancellation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from core.concurrency.protocols import CancellationTokenProtocol
from core.errors.exception_logging import log_exception
from core.errors.exceptions import ValidationError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger
from plugins.lifecycle_cancellation import deregister_active_cancellation
from plugins.lifecycle_dependencies import (
    ActiveCancellationRecord,
    PluginLifecycleDependencies,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("register_active_cancellation",)

LOGGER_NAME = "SoAI.plugins.lifecycle_active_cancellation"
OPERATION = "plugins.lifecycle.register_active_cancellation.bind_task"


async def register_active_cancellation(
    deps: PluginLifecycleDependencies,
    active_cancellation_lock: asyncio.Lock,
    active_cancellation_tasks: dict[str, dict[str, ActiveCancellationRecord]],
    *,
    service_name: str,
    cancellation_id: str,
    task: asyncio.Task[None],
    task_type: str,
    plugin_name: str | None = None,
    metadata: JSONDict | None = None,
) -> tuple[CancellationTokenProtocol, str]:
    logger = get_logger(LOGGER_NAME)
    deps.lifecycle.require_enabled(service_name)
    if not cancellation_id:
        raise ValidationError(
            "Active cancellation registration requires a non-empty cancellation_id.",
        )
    owner = plugin_name or (task_type or "plugin-manager")
    token_metadata: JSONDict = {"task_type": task_type}
    if plugin_name:
        token_metadata["plugin"] = plugin_name
    if metadata:
        token_metadata.update({key: value for key, value in metadata.items() if value is not None})
    try:
        if deps.lifecycle.shutdown_event.is_set():
            raise asyncio.CancelledError
        token = await deps.cancellation_binder.bind_task(
            cancellation_id,
            task,
            owner=owner,
            metadata=token_metadata,
        )
        if token.is_cancelled() and not task.done():
            task.cancel()
        normalized_id = token.cancellation_id
        task_key = f"{task_type or 'task'}:{id(task)}"
        async with active_cancellation_lock:
            deps.lifecycle.require_enabled(service_name)
            if deps.lifecycle.shutdown_event.is_set():
                raise asyncio.CancelledError
            tasks = active_cancellation_tasks.get(normalized_id)
            if tasks is None:
                tasks = {}
                active_cancellation_tasks[normalized_id] = tasks
            tasks[task_key] = ActiveCancellationRecord(
                task=task,
                token=token,
                task_type=task_type,
                plugin_name=plugin_name,
                metadata=token_metadata,
            )
    except asyncio.CancelledError:
        if not task.done() and task is not asyncio.current_task():
            task.cancel()
        raise
    except RECOVERABLE_EXCEPTIONS as exception:
        log_exception(
            logger,
            exception,
            message="Failed to bind task to cancellation registry. Cancelling task.",
            operation=OPERATION,
            details={
                "cancellation_id": cancellation_id,
                "task_type": task_type,
                "plugin": plugin_name or "",
            },
            level="warning",
        )
        if not task.done() and task is not asyncio.current_task():
            task.cancel()
        raise

    async def deregister() -> None:
        await deregister_active_cancellation(
            deps,
            active_cancellation_lock,
            active_cancellation_tasks,
            normalized_id,
            task_key,
        )

    def _finalizer(_completed: asyncio.Task[None]) -> None:
        finalizer_logger = get_logger(LOGGER_NAME)
        _ = deps.create_managed_task(
            deregister(),
            logger=finalizer_logger,
            name=f"plugin-active-cancellation-finalize-{normalized_id}",
            finalizer_tracker=deps.lifecycle.finalizer_tracker,
        )

    task.add_done_callback(_finalizer)
    return (token, task_key)
