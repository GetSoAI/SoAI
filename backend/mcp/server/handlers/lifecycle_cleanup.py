"""SoAI - MCP lifecycle cleanup helpers [backend/mcp/server/handlers/lifecycle_cleanup.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

from core.concurrency.task_groups import ManagedTaskGroup
from core.errors.exception_logging import log_exception, log_handled_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger
from mcp.handlers.tools.web_fetch_screenshot import (
    shutdown_cached_web_fetch_screenshot_runtime,
)
from mcp.server.state import MCPServerState

__all__ = (
    "cancel_background_tasks_safely",
    "close_all_sessions_safely",
    "reset_server_shutdown_event",
    "shutdown_rag_safely",
    "shutdown_utility_tools_safely",
)

OPERATION_MCP_SERVER_HANDLERS_LIFECYCLE_CLEANUP_CANCEL_BACKGROUND_TASKS_SAFELY = (
    "mcp.server.handlers.lifecycle_cleanup.cancel_background_tasks_safely"
)
OPERATION_MCP_SERVER_HANDLERS_LIFECYCLE_CLEANUP_CLOSE_ALL_SESSIONS_SAFELY = (
    "mcp.server.handlers.lifecycle_cleanup.close_all_sessions_safely"
)
OPERATION_MCP_SERVER_HANDLERS_LIFECYCLE_CLEANUP_SHUTDOWN_RAG_SAFELY = (
    "mcp.server.handlers.lifecycle_cleanup.shutdown_rag_safely"
)
OPERATION_MCP_SERVER_HANDLERS_LIFECYCLE_CLEANUP_SHUTDOWN_UTILITY_TOOLS_SAFELY = (
    "mcp.server.handlers.lifecycle_cleanup.shutdown_utility_tools_safely"
)


LOGGER_NAME = "SoAI.mcp.server.lifecycle_cleanup"


def reset_server_shutdown_event(state: MCPServerState) -> None:
    state.shutdown_event = asyncio.Event()


async def cancel_background_tasks_safely(
    background_tasks: ManagedTaskGroup,
    *,
    message: str,
    operation: str,
) -> None:
    pending_count = background_tasks.pending()
    if pending_count <= 0:
        return
    logger = get_logger(LOGGER_NAME)
    try:
        await background_tasks.cancel(message=message)
    except RECOVERABLE_EXCEPTIONS as exception:
        log_exception(
            logger,
            exception,
            message="Failed to cancel MCP background tasks during lifecycle cleanup.",
            operation=OPERATION_MCP_SERVER_HANDLERS_LIFECYCLE_CLEANUP_CANCEL_BACKGROUND_TASKS_SAFELY,
            details={"pending_tasks": pending_count, "cleanup_operation": operation},
            level="warning",
        )


async def close_all_sessions_safely(
    close_all_sessions: Callable[[], Awaitable[None]],
    *,
    operation: str,
    message: str,
) -> None:
    logger = get_logger(LOGGER_NAME)
    try:
        await close_all_sessions()
    except RECOVERABLE_EXCEPTIONS as exception:
        log_exception(
            logger,
            exception,
            message=message,
            operation=OPERATION_MCP_SERVER_HANDLERS_LIFECYCLE_CLEANUP_CLOSE_ALL_SESSIONS_SAFELY,
            details={"cleanup_operation": operation},
            level="warning",
        )


async def shutdown_rag_safely(
    state: MCPServerState,
    *,
    operation: str,
    message: str,
) -> None:
    logger = get_logger(LOGGER_NAME)
    rag = state.mcp_rag
    if rag is not None:
        try:
            await rag.shutdown()
        except RECOVERABLE_EXCEPTIONS as exception:
            log_exception(
                logger,
                exception,
                message=message,
                operation=OPERATION_MCP_SERVER_HANDLERS_LIFECYCLE_CLEANUP_SHUTDOWN_RAG_SAFELY,
                details={"cleanup_operation": operation},
                level="warning",
            )
    try:
        await shutdown_cached_web_fetch_screenshot_runtime()
    except RECOVERABLE_EXCEPTIONS as exception:
        log_handled_exception(
            logger,
            exception,
            message="Failed to shut down MCP web fetch screenshot runtime (non-critical).",
            operation=OPERATION_MCP_SERVER_HANDLERS_LIFECYCLE_CLEANUP_SHUTDOWN_RAG_SAFELY,
            details={"cleanup_operation": operation},
            level="warning",
        )
    finally:
        state.mcp_rag = None


async def shutdown_utility_tools_safely(state: MCPServerState, *, operation: str) -> None:
    logger = get_logger(LOGGER_NAME)
    if state.utility_tools is None:
        return
    try:
        await state.utility_tools.shutdown()
    except RECOVERABLE_EXCEPTIONS as exception:
        log_handled_exception(
            logger,
            exception,
            message="Failed to shut down MCP utility tools (non-critical).",
            operation=OPERATION_MCP_SERVER_HANDLERS_LIFECYCLE_CLEANUP_SHUTDOWN_UTILITY_TOOLS_SAFELY,
            details={"cleanup_operation": operation},
            level="debug",
        )
    finally:
        state.utility_tools = None
