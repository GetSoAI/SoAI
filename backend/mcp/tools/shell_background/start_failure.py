"""SoAI - Shell background start failure cleanup [backend/mcp/tools/shell_background/start_failure.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.concurrency.cancellation_cleanup import (
    uncancel_and_wait,
    uncancel_then_cleanup,
)
from core.execution.owned_execution_tasks import finalize_owned_execution_task
from core.tool_calls.deferred_tool_call_acceptance import (
    persist_deferred_tool_call_start_failure,
)
from core.tool_calls.status_values import (
    TOOL_CALL_STATUS_CANCELLED,
    TOOL_CALL_STATUS_ERROR,
)
from mcp.tools.shell_session_cleanup import (
    ShellSessionCleanupDeps,
    close_shell_session_resources,
)

if TYPE_CHECKING:
    from core.tasks.protocols import TaskRegistryProtocol
    from core.tool_calls.current_tool_call import CurrentToolCallIdentity
    from core.tool_calls.protocols import DatabaseToolCallsProtocol

__all__ = (
    "cleanup_cancelled_shell_background_start",
    "cleanup_failed_shell_background_start",
)


async def cleanup_cancelled_shell_background_start(
    *,
    task_registry: TaskRegistryProtocol,
    database_tool_calls: DatabaseToolCallsProtocol,
    identity: CurrentToolCallIdentity,
    cleanup_deps: ShellSessionCleanupDeps,
    owner_task_id: str,
    shell_session_id: int,
    terminal_session_id: str,
    error_message: str,
) -> None:
    await uncancel_then_cleanup(
        finalize_owned_execution_task(
            task_registry,
            owner_task_id=owner_task_id,
            final_status=TOOL_CALL_STATUS_CANCELLED,
            status_message="Cancelled",
            error_message=error_message,
        ),
    )
    await uncancel_then_cleanup(
        persist_deferred_tool_call_start_failure(
            database_tool_calls=database_tool_calls,
            storage_call_id=identity.storage_call_id,
            error_message=error_message,
        ),
    )
    await uncancel_then_cleanup(
        close_shell_session_resources(
            cleanup_deps,
            operation="mcp.tools.shell_background.service.start_cancelled",
            shell_session_id=shell_session_id,
            terminal_session_id=terminal_session_id,
        ),
    )


async def cleanup_failed_shell_background_start(
    *,
    task_registry: TaskRegistryProtocol,
    database_tool_calls: DatabaseToolCallsProtocol,
    identity: CurrentToolCallIdentity,
    cleanup_deps: ShellSessionCleanupDeps,
    owner_task_id: str,
    shell_session_id: int,
    terminal_session_id: str,
) -> None:
    await uncancel_and_wait(
        finalize_owned_execution_task(
            task_registry,
            owner_task_id=owner_task_id,
            final_status=TOOL_CALL_STATUS_ERROR,
            status_message="Failed",
            error_message="Shell background watch failed to start.",
        ),
    )
    await uncancel_and_wait(
        persist_deferred_tool_call_start_failure(
            database_tool_calls=database_tool_calls,
            storage_call_id=identity.storage_call_id,
            error_message="Shell background watch failed to start.",
        ),
    )
    await uncancel_and_wait(
        close_shell_session_resources(
            cleanup_deps,
            operation="mcp.tools.shell_background.service.start_failed",
            shell_session_id=shell_session_id,
            terminal_session_id=terminal_session_id,
        ),
    )
