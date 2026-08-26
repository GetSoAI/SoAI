"""SoAI - MCP host interaction expiry loop [backend/mcp/server/handlers/host_interaction_expiry.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from core.errors.exception_logging import log_handled_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.tasks.enums import TaskStatus
from core.tasks.type_catalog import TASK_TYPE_MCP_ELICITATION, TASK_TYPE_MCP_SAMPLING
from core.timing.epoch import epoch_ms
from mcp.server.handlers.task_interactions import expire_host_interaction

if TYPE_CHECKING:
    from core.logging.protocols import LoggerProtocol
    from core.mcp.protocols_runtime import MCPRemoteHostProtocol
    from core.tasks.protocols_query import TaskRegistryQueryView
    from mcp.host.internal_protocols import MCPServerHostProtocol

__all__ = ("run_host_interaction_expiry_loop",)

_HOST_TASK_TYPES = (TASK_TYPE_MCP_ELICITATION, TASK_TYPE_MCP_SAMPLING)
OPERATION_HOST_INTERACTION_EXPIRY_QUERY = "mcp.server.host_interaction_expiry.query"
OPERATION_HOST_INTERACTION_EXPIRY_RESOLVE = "mcp.server.host_interaction_expiry"


async def run_host_interaction_expiry_loop(
    *,
    shutdown_event: asyncio.Event,
    task_registry_queries: TaskRegistryQueryView,
    server_ref: MCPServerHostProtocol,
    remote: MCPRemoteHostProtocol,
    logger: LoggerProtocol,
    timeout_ms: int,
) -> None:
    sleep_seconds = max(0.5, min(5.0, float(timeout_ms) / 1000.0))
    while not shutdown_event.is_set():
        await asyncio.sleep(sleep_seconds)
        if shutdown_event.is_set():
            return
        now_ms = epoch_ms()
        for task_type in _HOST_TASK_TYPES:
            try:
                tasks = await task_registry_queries.query_active(
                    task_type=task_type,
                    limit=1000,
                )
            except RECOVERABLE_EXCEPTIONS as exception:
                log_handled_exception(
                    logger,
                    exception,
                    message="Failed to query MCP host interactions for expiry.",
                    operation=OPERATION_HOST_INTERACTION_EXPIRY_QUERY,
                    level="warning",
                    details={"task_type": task_type},
                )
                continue
            for task in tasks:
                if (
                    task.owner_type != "mcp_client"
                    or task.status != TaskStatus.INPUT_REQUIRED
                    or task.ttl_expires_at_ms is None
                    or task.ttl_expires_at_ms > now_ms
                ):
                    continue
                try:
                    await expire_host_interaction(server_ref, remote, task)
                except RECOVERABLE_EXCEPTIONS as exception:
                    log_handled_exception(
                        logger,
                        exception,
                        message="Failed to expire MCP host interaction.",
                        operation=OPERATION_HOST_INTERACTION_EXPIRY_RESOLVE,
                        level="warning",
                        details={"task_id": task.task_id, "task_type": task.task_type},
                    )
