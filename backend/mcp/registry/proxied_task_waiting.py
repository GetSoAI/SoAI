"""SoAI - MCP proxied task handling for tool tasks [backend/mcp/registry/proxied_task_waiting.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.concurrency.locks import bounded_lock_for_cleanup
from core.errors.exception_logging import log_exception, log_handled_exception
from core.errors.exceptions import SoAITimeoutError, ValidationError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger
from core.tasks.status_transitions import update_progress
from core.tasks.task import Task
from core.tasks.task_cancellation import cancel
from mcp.registry.internal_protocols import MCPRegistryManagerProtocol

__all__ = ("await_proxied_task_completion",)

LOGGER_NAME = "SoAI.mcp.registry.proxied_task_waiting"
OPERATION_MCP_REGISTRY_CANCEL_TIMED_OUT_PROXIED_TASK = (
    "mcp.registry.proxied_task_waiting.cancel_timed_out_proxied_task"
)
OPERATION_MCP_REGISTRY_UPDATE_PARENT_PROGRESS_FOR_PROXIED_TASK = (
    "mcp.registry.proxied_task_waiting.update_parent_progress_for_proxied_task"
)


async def await_proxied_task_completion(
    manager: MCPRegistryManagerProtocol,
    *,
    parent_task_id: str,
    proxied_task_id: str,
) -> Task:
    logger = get_logger(LOGGER_NAME)
    try:
        await update_progress(
            manager.task_registry,
            parent_task_id,
            progress_current=2,
            status_message=f"Queued background task {proxied_task_id}",
        )
    except RECOVERABLE_EXCEPTIONS as exception:
        log_handled_exception(
            logger,
            exception,
            message="Unable to update progress for proxied task parent (non-critical).",
            operation=OPERATION_MCP_REGISTRY_UPDATE_PARENT_PROGRESS_FOR_PROXIED_TASK,
            details={
                "parent_task_id": parent_task_id,
                "proxied_task_id": proxied_task_id,
            },
            level="debug",
        )
    async with manager.state.task.proxied_task_map_lock:
        manager.state.task.proxied_task_map[proxied_task_id] = parent_task_id
    try:
        try:
            child = await manager.task_registry.wait_for_completion(
                proxied_task_id,
                timeout=float(manager.tasks_proxy_timeout_sec),
            )
        except (SoAITimeoutError, TimeoutError) as exception:
            try:
                await cancel(
                    manager.task_registry,
                    proxied_task_id,
                    reason=f"Parent task {parent_task_id} timed out waiting for completion",
                )
            except RECOVERABLE_EXCEPTIONS as cancel_exception:
                log_exception(
                    logger,
                    cancel_exception,
                    message="Failed to cancel timed-out proxied task.",
                    operation=OPERATION_MCP_REGISTRY_CANCEL_TIMED_OUT_PROXIED_TASK,
                    details={
                        "proxied_task_id": proxied_task_id,
                        "parent_task_id": parent_task_id,
                    },
                    level="warning",
                )
            raise SoAITimeoutError(
                f"Background task timed out after {manager.tasks_proxy_timeout_sec}s: {proxied_task_id}",
            ) from exception
    finally:
        async with bounded_lock_for_cleanup(
            manager.state.task.proxied_task_map_lock,
        ) as lock_result:
            if lock_result.acquired:
                if manager.state.task.proxied_task_map.get(proxied_task_id) == parent_task_id:
                    manager.state.task.proxied_task_map.pop(proxied_task_id, None)
    if child is None:
        raise ValidationError(f"Background task not found: {proxied_task_id}")
    return child
