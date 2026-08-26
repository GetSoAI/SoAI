"""SoAI - MCP search task cancellation and finalization helpers [backend/mcp/search/task_lifecycle.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Awaitable
from typing import TYPE_CHECKING

from core.concurrency.ephemeral_tasks import create_ephemeral_task
from core.logging.trace import get_logger
from core.tasks.cancellation_token_scope import cancellation_token_scope
from core.tasks.enums import TaskStatus
from core.tasks.noncritical_finalization import finalize_noncritical
from core.tasks.protocols import (
    CancellationEventBusProtocol,
    CancellationHistoryProtocol,
    TaskRegistryProtocol,
    TokenCollectionProtocol,
)
from core.tasks.task import Task

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "await_with_task_cancellation",
    "complete_task",
    "fail_task",
)

LOGGER_NAME = "SoAI.mcp.search.task_lifecycle"


async def await_with_task_cancellation[Result](
    token_collection: TokenCollectionProtocol,
    cancellation_history: CancellationHistoryProtocol,
    cancellation_event_bus: CancellationEventBusProtocol,
    task: Task,
    operation_coro: Awaitable[Result],
    operation: str,
) -> Result:
    logger = get_logger(LOGGER_NAME)
    cancel_id = task.cancellation_id
    if asyncio.iscoroutine(operation_coro):
        runner: asyncio.Task[Result] = create_ephemeral_task(operation_coro)
    else:

        async def _await_wrapper(awaitable_value: Awaitable[Result]) -> Result:
            return await awaitable_value

        runner = create_ephemeral_task(_await_wrapper(operation_coro))
    try:

        def _cancel_runner(_reason: str) -> None:
            _ = _reason
            runner.cancel()

        async with cancellation_token_scope(
            token_collection,
            cancellation_history,
            cancellation_event_bus,
            cancellation_id=cancel_id,
            owner=f"mcp_search:{operation}",
            metadata={"task_id": task.task_id, "operation": operation},
            on_cancel=_cancel_runner,
        ):
            return await runner
    finally:
        if not runner.done():
            runner.cancel()
            try:
                await runner
            except asyncio.CancelledError:
                logger.debug("Search task cancelled during cleanup (non-critical).")


async def complete_task(
    task_registry: TaskRegistryProtocol,
    task_id: str,
    result: JSONDict | None = None,
    message: str = "Search completed",
) -> None:
    logger = get_logger(LOGGER_NAME)
    await finalize_noncritical(
        task_registry,
        task_id,
        TaskStatus.COMPLETED,
        result=result,
        status_message=message,
        logger=logger,
        operation="mcp.search.task_lifecycle.complete_task",
        log_message="Failed to finalize search task (non-critical).",
        details={"task_id": task_id},
    )


async def fail_task(task_registry: TaskRegistryProtocol, task_id: str, error_message: str) -> None:
    logger = get_logger(LOGGER_NAME)
    await finalize_noncritical(
        task_registry,
        task_id,
        TaskStatus.FAILED,
        error_code=500,
        error_message=error_message,
        logger=logger,
        operation="mcp.search.task_lifecycle.fail_task",
        log_message="Failed to finalize failed search task (non-critical).",
        details={"task_id": task_id},
    )
