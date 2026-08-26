"""SoAI - MCP elicitation task lifecycle helpers [backend/mcp/tools/elicitation_task_lifecycle.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from core.elicitation.notification_cleanup import (
    cleanup_elicitation_notification_noncritical,
)
from core.elicitation_interactions import extract_notification_id
from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception, log_handled_exception
from core.errors.exceptions import SoAITimeoutError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.protocols import LoggerProtocol
from core.tasks.enums import TaskStatus
from core.tasks.finalization import finalize
from core.timing.epoch import epoch_ms
from core.users.user_id import coerce_optional_user_id, is_strict_user_id
from mcp.tools.error import MCPToolError

if TYPE_CHECKING:
    from core.tasks.task import Task
    from mcp.tools.internal_protocols import MCPUtilityToolsProtocol

__all__ = (
    "cleanup_elicitation_notification",
    "wait_for_elicitation_task_completion",
)


async def cleanup_elicitation_notification(
    utility_tools: MCPUtilityToolsProtocol,
    logger: LoggerProtocol,
    *,
    interaction_type: str,
    operation: str,
    task: Task | None,
    task_id: str,
    conv_id: str,
) -> None:
    resolved_task = task
    if resolved_task is None:
        try:
            resolved_task = await utility_tools.task_registry.get(task_id)
        except RECOVERABLE_EXCEPTIONS as exception:
            log_handled_exception(
                logger,
                exception,
                message=(
                    "Failed to load elicitation task for notification cleanup (non-critical)."
                ),
                operation=operation,
                level="warning",
                details={
                    "conv_id": conv_id,
                    "task_id": task_id,
                    "interaction_type": interaction_type,
                },
            )
            return
    if resolved_task is None:
        return
    notification_id = extract_notification_id(resolved_task.metadata)
    if notification_id is None:
        return
    user_id = coerce_optional_user_id(resolved_task.user_id)
    if not is_strict_user_id(user_id):
        return
    await cleanup_elicitation_notification_noncritical(
        database_notifications=utility_tools.database_notifications,
        logger=logger,
        user_id=int(user_id),
        metadata=resolved_task.metadata,
        operation=operation,
        message=f"Failed to delete {interaction_type} notification (non-critical).",
        details={
            "conv_id": conv_id,
            "task_id": task_id,
            "notification_id": notification_id,
            "interaction_type": interaction_type,
        },
    )


async def wait_for_elicitation_task_completion(
    utility_tools: MCPUtilityToolsProtocol,
    *,
    interaction_type: str,
    operation: str,
    operation_notification_cleanup: str,
    task_id: str,
    conv_id: str,
    expires_at_ms: int | None,
    logger: LoggerProtocol,
) -> Task | None:
    try:
        if expires_at_ms is None or expires_at_ms <= 0:
            raise MCPToolError(
                -32602,
                "Server-owned user interaction timeout must be positive.",
            )
        remaining_ms = int(expires_at_ms) - epoch_ms()
        if remaining_ms <= 0:
            raise SoAITimeoutError("User interaction deadline expired.")
        completed = await utility_tools.task_registry.wait_for_completion(
            task_id,
            timeout=float(remaining_ms) / 1000.0,
        )
        await cleanup_elicitation_notification(
            utility_tools,
            logger,
            interaction_type=interaction_type,
            operation=operation_notification_cleanup,
            task=completed,
            task_id=task_id,
            conv_id=conv_id,
        )
        return completed
    except SoAITimeoutError as exception:
        finalized = await finalize(
            utility_tools.task_registry,
            task_id,
            TaskStatus.FAILED,
            error_code=-32603,
            error_message="Timed out waiting for user input.",
            status_message="Timed out",
        )
        await cleanup_elicitation_notification(
            utility_tools,
            logger,
            interaction_type=interaction_type,
            operation=operation_notification_cleanup,
            task=finalized,
            task_id=task_id,
            conv_id=conv_id,
        )
        if finalized is not None and finalized.status != TaskStatus.FAILED:
            return finalized
        raise MCPToolError(-32603, "Timed out waiting for user input.") from exception
    except asyncio.CancelledError:
        await finalize(
            utility_tools.task_registry,
            task_id,
            TaskStatus.CANCELLED,
            error_message="Cancelled while waiting for user input.",
            status_message="Cancelled",
        )
        await cleanup_elicitation_notification(
            utility_tools,
            logger,
            interaction_type=interaction_type,
            operation=operation_notification_cleanup,
            task=None,
            task_id=task_id,
            conv_id=conv_id,
        )
        raise
    except RECOVERABLE_EXCEPTIONS as exception:
        coerced = coerce_to_soai_error(exception, operation=operation)
        log_exception(
            logger,
            coerced,
            message=f"{interaction_type} failed while waiting for completion.",
            operation=operation,
            details={"conv_id": conv_id, "task_id": task_id},
            level="warning",
        )
        await finalize(
            utility_tools.task_registry,
            task_id,
            TaskStatus.FAILED,
            error_code=-32603,
            error_message=str(coerced),
            status_message=f"{interaction_type} failed",
        )
        await cleanup_elicitation_notification(
            utility_tools,
            logger,
            interaction_type=interaction_type,
            operation=operation_notification_cleanup,
            task=None,
            task_id=task_id,
            conv_id=conv_id,
        )
        raise MCPToolError(-32603, str(coerced)) from exception
