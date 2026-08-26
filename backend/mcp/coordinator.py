"""SoAI - MCP subsystem coordinator [backend/mcp/coordinator.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from core.di.validation import require_dependencies
from core.errors.exception_logging import log_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger
from core.mcp.protocols_main import MCPRemoteProtocol, MCPServerProtocol

__all__ = (
    "MCPServicesCoordinator",
    "MCPServicesCoordinatorDependencies",
)

OPERATION_MCP_COORDINATOR_SAFE_SHUTDOWN_REMOTE = "mcp.coordinator.safe_shutdown_remote"
OPERATION_MCP_COORDINATOR_SAFE_SHUTDOWN_SERVER = "mcp.coordinator.safe_shutdown_server"


LOGGER_NAME = "SoAI.mcp.coordinator"


@dataclass(frozen=True, slots=True)
class MCPServicesCoordinatorDependencies:
    remote: MCPRemoteProtocol
    server: MCPServerProtocol

    def __post_init__(self) -> None:
        require_dependencies(
            owner="MCPServicesCoordinatorDependencies",
            remote=self.remote,
            server=self.server,
        )


class MCPServicesCoordinator:
    def __init__(self, deps: MCPServicesCoordinatorDependencies) -> None:
        self._deps = deps
        self.shutdown_event = asyncio.Event()
        self.remote = deps.remote
        self.server = deps.server
        self._started = False
        self._lifecycle_lock = asyncio.Lock()

    async def start(self) -> None:
        async with self._lifecycle_lock:
            if self._started:
                return

            remote_started = False
            server_start_attempted = False
            try:
                await self.remote.start()
                remote_started = True
                server_start_attempted = True
                await self.server.start()
            except asyncio.CancelledError:
                await self._rollback_startup(
                    remote_started=remote_started,
                    server_start_attempted=server_start_attempted,
                    operation="mcp.coordinator.start",
                )
                raise
            except RECOVERABLE_EXCEPTIONS:
                await self._rollback_startup(
                    remote_started=remote_started,
                    server_start_attempted=server_start_attempted,
                    operation="mcp.coordinator.start",
                )
                raise

            self._started = True

    async def _rollback_startup(
        self,
        *,
        remote_started: bool,
        server_start_attempted: bool,
        operation: str,
    ) -> None:
        if server_start_attempted:
            await self._safe_shutdown_server(
                operation=operation,
                message="Failed shutting down MCPServer during coordinator rollback",
            )
        if remote_started:
            await self._safe_shutdown_remote(
                operation=operation,
                message="Failed shutting down MCPRemote during coordinator rollback",
            )

    async def _safe_shutdown_remote(self, *, operation: str, message: str) -> None:
        logger = get_logger(LOGGER_NAME)
        try:
            await self.remote.shutdown()
        except RECOVERABLE_EXCEPTIONS as exception:
            log_exception(
                logger,
                exception,
                message=message,
                operation=OPERATION_MCP_COORDINATOR_SAFE_SHUTDOWN_REMOTE,
                details={"shutdown_operation": operation},
                level="warning",
            )

    async def _safe_shutdown_server(self, *, operation: str, message: str) -> None:
        logger = get_logger(LOGGER_NAME)
        try:
            await self.server.shutdown()
        except RECOVERABLE_EXCEPTIONS as exception:
            log_exception(
                logger,
                exception,
                message=message,
                operation=OPERATION_MCP_COORDINATOR_SAFE_SHUTDOWN_SERVER,
                details={"shutdown_operation": operation},
                level="warning",
            )

    async def shutdown(self) -> None:
        self.shutdown_event.set()
        async with self._lifecycle_lock:
            await self._safe_shutdown_remote(
                operation="mcp.coordinator.shutdown",
                message="Failed shutting down MCPRemote from coordinator",
            )
            await self._safe_shutdown_server(
                operation="mcp.coordinator.shutdown",
                message="Failed shutting down MCPServer from coordinator",
            )
            self._started = False
