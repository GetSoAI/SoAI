"""SoAI - MCP server host-mode request client [backend/mcp/server/handlers/host_mode_client.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Coroutine
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.concurrency.background_task_scheduling import schedule_named_background_task
from core.di.validation import require_dependencies
from core.errors.exception_logging import log_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger

if TYPE_CHECKING:
    from core.concurrency.task_groups import ManagedTaskGroup
    from core.mcp.protocols_main import MCPRemoteProtocol
    from core.types.json import JSONDict, JSONValue
    from mcp.server.state import MCPServerState

__all__ = (
    "MCPHostModeClient",
    "MCPHostModeClientDependencies",
)

LOGGER_NAME = "SoAI.mcp.server.host_mode_client"
OPERATION = "mcp.server.host_mode.send_request"
OPERATION_MCP_HOST_MODE_CLIENT_SCHEDULE_BACKGROUND_TASK = (
    "mcp.server.host_mode_client.schedule_background_task"
)


@dataclass(frozen=True, slots=True)
class MCPHostModeClientDependencies:
    state: MCPServerState
    mcp_remote: MCPRemoteProtocol
    background_tasks: ManagedTaskGroup
    protocol_version: str
    host_mode_enabled: bool

    def __post_init__(self) -> None:
        require_dependencies(
            owner="MCPHostModeClientDependencies",
            background_tasks=self.background_tasks,
            host_mode_enabled=self.host_mode_enabled,
            mcp_remote=self.mcp_remote,
            protocol_version=self.protocol_version,
            state=self.state,
        )


class MCPHostModeClient:
    def __init__(self, deps: MCPHostModeClientDependencies) -> None:
        self._state = deps.state
        self._mcp_remote = deps.mcp_remote
        self._background_tasks = deps.background_tasks
        self._protocol_version = deps.protocol_version
        self._host_mode_enabled = deps.host_mode_enabled

    def track_background_task(self, task: asyncio.Task[None]) -> None:
        if task.done():
            return
        _ = self._background_tasks.track(task)

    def schedule_background_task(
        self,
        coro: Coroutine[None, None, None],
        *,
        name: str,
    ) -> asyncio.Task[None]:
        return schedule_named_background_task(
            coro,
            name=name,
            track_task=self.track_background_task,
            logger=get_logger(LOGGER_NAME),
            operation=OPERATION_MCP_HOST_MODE_CLIENT_SCHEDULE_BACKGROUND_TASK,
            empty_name_error_message="Host mode background task name must be a non-empty string.",
            close_failure_message="Failed to close host mode background coroutine (non-critical).",
        )

    def build_core_app_info(self) -> JSONDict:
        return {
            "name": "SoAI",
            "version": self._protocol_version,
        }

    async def send_host_mode_request(
        self,
        server_id: str,
        method: str,
        parameters: JSONDict | None = None,
    ) -> JSONValue:
        logger = get_logger(LOGGER_NAME)
        if not self._host_mode_enabled:
            logger.warning("Host mode request attempted but host mode is disabled")
            return None
        try:
            return await self._mcp_remote.send_host_mode_request(
                server_id,
                method,
                parameters or {},
            )
        except RECOVERABLE_EXCEPTIONS as exception:
            log_exception(
                logger,
                exception,
                message="Host mode request failed",
                operation=OPERATION,
                details={"method": method},
            )
            raise
