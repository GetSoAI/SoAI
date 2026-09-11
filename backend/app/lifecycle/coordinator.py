"""SoAI - Server and actor lifecycle coordinator [backend/app/lifecycle/coordinator.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass

from app.application_dependencies import ApplicationLifecycleModuleDependencies
from app.internal_protocols import LifecycleActorProtocol, UvicornServerProtocol
from core.concurrency.task_groups import (
    DEFAULT_CANCELLATION_TIMEOUT_SEC,
    cancel_and_await,
)
from core.di.validation import require_dependencies
from core.errors.exception_logging import log_exception, log_handled_exception
from core.errors.exceptions import StateError, ValidationError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.colors import get_log_level_colors
from core.logging.protocols import LoggerProtocol
from core.logging.trace import get_logger
from core.timing.constants import STANDARD_DELAY_SEC, TIGHT_POLL_INTERVAL_SEC

__all__ = (
    "LifecycleCoordinator",
    "LifecycleCoordinatorDependencies",
)

LOGGER_NAME = "SoAI.app.lifecycle.coordinator"
OPERATION_APPLICATION_LIFECYCLE_SHUTDOWN_SERVERS = "application_lifecycle.shutdown_servers"
OPERATION_APPLICATION_LIFECYCLE_SHUTDOWN_SERVERS_BANNER = (
    "application_lifecycle.shutdown_servers.banner"
)


@dataclass(frozen=True, slots=True)
class LifecycleCoordinatorDependencies:
    logger: LoggerProtocol
    module_dependencies: ApplicationLifecycleModuleDependencies

    def __post_init__(self) -> None:
        require_dependencies(
            owner="LifecycleCoordinatorDependencies",
            logger=self.logger,
            module_dependencies=self.module_dependencies,
        )
        if not isinstance(
            self.module_dependencies,
            ApplicationLifecycleModuleDependencies,
        ):
            raise ValidationError("ApplicationLifecycleModuleDependencies are required.")


class LifecycleCoordinator:

    def __init__(self, deps: LifecycleCoordinatorDependencies) -> None:
        self._logger = deps.logger
        self._actors: list[LifecycleActorProtocol] = []
        self._servers: list[UvicornServerProtocol] = []
        self._server_tasks: list[asyncio.Task[None]] = []
        self._module_dependencies = deps.module_dependencies

    def register_actor(self, actor: LifecycleActorProtocol) -> None:
        if actor is not None:
            self._actors.append(actor)

    def actor_count(self) -> int:
        return len(self._actors)

    def register_server(self, server: UvicornServerProtocol, task: asyncio.Task[None]) -> None:
        self._servers.append(server)
        self._server_tasks.append(task)

    def has_servers(self) -> bool:
        return bool(self._servers)

    def server_count(self) -> int:
        return len(self._servers)

    async def shutdown_servers(self, timeout: float) -> None:
        if not self._server_tasks:
            return
        shutdown_deadline = time.monotonic() + timeout
        force_close_reserve = min(STANDARD_DELAY_SEC, timeout)
        graceful_timeout = max(timeout - force_close_reserve, 0.0)
        self._logger.debug(
            "Attempting graceful shutdown of %s API server(s) with a %.1fs timeout...",
            len(self._server_tasks),
            timeout,
        )
        for server in self._servers:
            server.should_exit = True
        pending = await self._wait_for_server_tasks(
            self._server_tasks,
            timeout=graceful_timeout,
            error_message="Unexpected error while awaiting API server shutdown",
        )
        pending_servers: list[UvicornServerProtocol] = []
        if pending:
            pending_servers = self._pending_servers(pending)
            terminated_connections = self._terminate_server_io(pending_servers)
            self._logger.debug(
                "Graceful API server drain window elapsed for %s server(s). Terminated %s accepted connection(s) before the shutdown deadline.",
                len(pending),
                terminated_connections,
            )
            pending = await self._wait_for_server_tasks(
                pending,
                timeout=max(shutdown_deadline - time.monotonic(), 0.0),
                error_message=(
                    "Unexpected error while awaiting API server shutdown after "
                    "connection termination"
                ),
            )
            pending_servers = self._pending_servers(pending)
        if pending:
            try:
                banner = self._module_dependencies.log_banner_system_factory(
                    get_logger(LOGGER_NAME),
                    self._module_dependencies.banner_width,
                )
                banner.emit_custom(
                    color=get_log_level_colors().get("CRITICAL", ""),
                    message="Forcing SoAI shutdown!",
                    level=logging.CRITICAL,
                )
            except RECOVERABLE_EXCEPTIONS as exception:
                log_handled_exception(
                    self._logger,
                    exception,
                    message="Failed to emit shutdown banner (non-critical).",
                    operation=OPERATION_APPLICATION_LIFECYCLE_SHUTDOWN_SERVERS_BANNER,
                    level="debug",
                )
            self._logger.critical(
                "%s API server(s) did not shut down gracefully within %.1fs. Setting force_exit and terminating.",
                len(pending),
                timeout,
            )
            for server in pending_servers:
                server.force_exit = True
            for task in pending:
                task.cancel()
        self._terminate_server_io(self._servers)
        await cancel_and_await(
            self._server_tasks,
            logger=self._logger,
            task_label="API server tasks",
            timeout_sec=DEFAULT_CANCELLATION_TIMEOUT_SEC,
        )
        self._server_tasks.clear()
        self._servers.clear()

    async def _wait_for_server_tasks(
        self,
        tasks: list[asyncio.Task[None]] | set[asyncio.Task[None]],
        *,
        timeout: float,
        error_message: str,
    ) -> set[asyncio.Task[None]]:
        deadline = time.monotonic() + timeout
        pending = set(tasks)
        try:
            while pending:
                remaining = max(deadline - time.monotonic(), 0.0)
                _done, pending = await asyncio.wait(
                    pending, timeout=min(STANDARD_DELAY_SEC, remaining)
                )
                if not pending or time.monotonic() >= deadline:
                    break
                self._terminate_server_io(self._pending_servers(pending), drained_only=True)
        except (RuntimeError, ValueError) as error:
            log_exception(
                self._logger,
                error,
                message=error_message,
                operation=OPERATION_APPLICATION_LIFECYCLE_SHUTDOWN_SERVERS,
            )
            return set(tasks)
        return pending

    def _pending_servers(
        self,
        pending: set[asyncio.Task[None]],
    ) -> list[UvicornServerProtocol]:
        return [
            server
            for server, task in zip(self._servers, self._server_tasks, strict=True)
            if task in pending
        ]

    async def wait_until_started(self, timeout: float) -> None:
        if not self._servers:
            return
        await asyncio.wait_for(
            asyncio.gather(
                *[
                    self.wait_for_server_started(server, task)
                    for server, task in zip(self._servers, self._server_tasks, strict=True)
                ],
                return_exceptions=False,
            ),
            timeout=timeout,
        )

    def require_servers_serving(self) -> None:
        for server, task in zip(self._servers, self._server_tasks, strict=True):
            if task.done():
                raise StateError("API server task exited before readiness.")
            if not server.started:
                raise StateError("API server is not started before readiness.")
            uvicorn_servers = server.servers or []
            if not uvicorn_servers:
                continue
            if not any(uvicorn_server.is_serving() for uvicorn_server in uvicorn_servers):
                raise StateError("API server sockets are not serving before readiness.")

    async def wait_for_server_started(
        self,
        server: UvicornServerProtocol,
        task: asyncio.Task[None],
    ) -> None:
        while not server.started:
            if task.done():
                if task.cancelled():
                    raise StateError("API server task was cancelled before startup confirmation.")
                exception = task.exception()
                if exception is not None:
                    raise StateError(
                        "API server task exited before startup confirmation.",
                    ) from exception
                raise StateError("API server task exited before startup confirmation.")
            await asyncio.sleep(TIGHT_POLL_INTERVAL_SEC)

    def _terminate_server_io(
        self, servers: list[UvicornServerProtocol], *, drained_only: bool = False
    ) -> int:
        terminated_connections = 0
        for server in servers:
            for uv_server in server.servers or []:
                try:
                    uv_server.close()
                except (OSError, RuntimeError) as error:
                    log_handled_exception(
                        self._logger,
                        error,
                        message="Failed to close an API server listener during shutdown.",
                        operation=OPERATION_APPLICATION_LIFECYCLE_SHUTDOWN_SERVERS,
                        level="warning",
                    )
            for connection in list(server.server_state.connections):
                try:
                    if drained_only and (
                        not connection.transport.is_closing()
                        or connection.transport.get_write_buffer_size() > 0
                    ):
                        continue
                    connection.transport.abort()
                    terminated_connections += 1
                except (OSError, RuntimeError) as error:
                    log_handled_exception(
                        self._logger,
                        error,
                        message="Failed to abort an accepted API connection during shutdown.",
                        operation=OPERATION_APPLICATION_LIFECYCLE_SHUTDOWN_SERVERS,
                        level="warning",
                    )
        return terminated_connections
