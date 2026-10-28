"""SoAI - Server and actor lifecycle coordinator [backend/app/lifecycle/coordinator.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass

from app.application_dependencies import ApplicationLifecycleModuleDependencies
from app.internal_protocols import (
    CloseableServerProtocol,
    LifecycleActorProtocol,
    UvicornServerProtocol,
)
from app.lifecycle.results import LifecycleFailure
from core.concurrency.ephemeral_tasks import create_ephemeral_task
from core.concurrency.task_groups import (
    DEFAULT_CANCELLATION_TIMEOUT_SEC,
)
from core.di.validation import require_dependencies
from core.errors.exception_logging import log_exception, log_handled_exception
from core.errors.exceptions import StateError, ValidationError
from core.logging.protocols import LoggerProtocol
from core.timing.constants import STANDARD_DELAY_SEC, TIGHT_POLL_INTERVAL_SEC

__all__ = (
    "LifecycleCoordinator",
    "LifecycleCoordinatorDependencies",
)

OPERATION_APPLICATION_LIFECYCLE_SHUTDOWN_SERVERS = "application_lifecycle.shutdown_servers"


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
        self._reported_server_task_failures: set[asyncio.Task[None]] = set()
        self._listener_shutdown_tasks: dict[CloseableServerProtocol, asyncio.Task[None]] = {}

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

    async def shutdown_servers(self, timeout: float) -> list[LifecycleFailure]:
        if not self._server_tasks:
            return []
        failures: list[LifecycleFailure] = []
        shutdown_deadline = time.monotonic() + timeout
        force_close_reserve = min(STANDARD_DELAY_SEC, timeout)
        cancellation_reserve = min(DEFAULT_CANCELLATION_TIMEOUT_SEC, force_close_reserve)
        for server in self._servers:
            server.should_exit = True
        pending = await self._wait_for_server_tasks(
            self._server_tasks,
            deadline=shutdown_deadline - force_close_reserve,
            failures=failures,
        )
        if pending:
            self._terminate_server_io(self._pending_servers(pending), failures=failures)
            pending = await self._wait_for_server_tasks(
                pending,
                deadline=shutdown_deadline - cancellation_reserve,
                failures=failures,
            )
        if pending:
            self._logger.info("Forcing shutdown of %s API server(s).", len(pending))
            for server in self._pending_servers(pending):
                server.force_exit = True
            for task in pending:
                task.cancel()
        self._terminate_server_io(self._servers, failures=failures)
        if pending:
            await self._wait_for_server_tasks(
                pending, deadline=shutdown_deadline, failures=failures
            )
        await self._wait_for_listener_closure(shutdown_deadline)
        retained_servers: list[UvicornServerProtocol] = []
        retained_tasks: list[asyncio.Task[None]] = []
        for server, task in zip(self._servers, self._server_tasks, strict=True):
            resources_open = any(listener.is_serving() for listener in server.servers or [])
            resources_open = resources_open or any(
                not closure_task.done()
                or closure_task.cancelled()
                or closure_task.exception() is not None
                for listener in server.servers or []
                for closure_task in (self._listener_shutdown_tasks[listener],)
            )
            resources_open = resources_open or any(
                not connection.transport.is_closing()
                or connection.transport.get_write_buffer_size() > 0
                for connection in server.server_state.connections
            )
            resources_open = resources_open or any(
                not request_task.done() for request_task in server.server_state.tasks
            )
            if not task.done() or resources_open:
                message = "API server shutdown could not verify that all owned resources closed."
                failures.append(LifecycleFailure("API Server", "shutdown", True, message))
                self._logger.error(message)
                retained_servers.append(server)
                retained_tasks.append(task)
            if task.done() and not task.cancelled():
                exception = task.exception()
                if exception is not None:
                    message = "API server task failed during shutdown."
                    failures.append(LifecycleFailure("API Server", "shutdown", True, message))
                    if task not in self._reported_server_task_failures:
                        self._reported_server_task_failures.add(task)
                        log_exception(
                            self._logger,
                            exception,
                            message=message,
                            operation=OPERATION_APPLICATION_LIFECYCLE_SHUTDOWN_SERVERS,
                        )
        self._servers = retained_servers
        self._server_tasks = retained_tasks
        self._reported_server_task_failures.intersection_update(retained_tasks)
        self._listener_shutdown_tasks = {
            listener: self._listener_shutdown_tasks[listener]
            for server in retained_servers
            for listener in server.servers or []
        }
        return failures

    async def _wait_for_server_tasks(
        self,
        tasks: list[asyncio.Task[None]] | set[asyncio.Task[None]],
        *,
        deadline: float,
        failures: list[LifecycleFailure],
    ) -> set[asyncio.Task[None]]:
        pending = set(tasks)
        while pending:
            remaining = max(deadline - time.monotonic(), 0.0)
            _done, pending = await asyncio.wait(pending, timeout=min(STANDARD_DELAY_SEC, remaining))
            if not pending or time.monotonic() >= deadline:
                break
            self._terminate_server_io(
                self._pending_servers(pending), drained_only=True, failures=failures
            )
        return pending

    async def _wait_for_listener_closure(self, deadline: float) -> None:
        for server in self._servers:
            for listener in server.servers or []:
                task = self._listener_shutdown_tasks.get(listener)
                if (
                    task is None
                    or task.cancelled()
                    or (task.done() and task.exception() is not None)
                ):
                    task = create_ephemeral_task(
                        listener.wait_closed(),
                        name="api-listener-closure",
                        log_exceptions=False,
                    )
                    self._listener_shutdown_tasks[listener] = task
                    task.add_done_callback(self._observe_listener_closure)
        if self._listener_shutdown_tasks:
            await asyncio.wait(
                self._listener_shutdown_tasks.values(),
                timeout=max(deadline - time.monotonic(), 0.0),
            )

    def _observe_listener_closure(self, task: asyncio.Task[None]) -> None:
        if task.cancelled():
            return
        exception = task.exception()
        if exception is not None:
            log_exception(
                self._logger,
                exception,
                message="API server listener closure failed.",
                operation=OPERATION_APPLICATION_LIFECYCLE_SHUTDOWN_SERVERS,
            )

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
        self,
        servers: list[UvicornServerProtocol],
        *,
        drained_only: bool = False,
        failures: list[LifecycleFailure] | None = None,
    ) -> int:
        terminated_connections = 0
        for server in servers:
            for listener in server.servers or []:
                try:
                    listener.close()
                except (OSError, RuntimeError) as error:
                    self._record_server_io_failure(
                        "API Server Listener",
                        "Failed to close an API server listener during shutdown.",
                        error,
                        failures,
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
                    self._record_server_io_failure(
                        "API Server Connection",
                        "Failed to abort an accepted API connection during shutdown.",
                        error,
                        failures,
                    )
        return terminated_connections

    def _record_server_io_failure(
        self,
        component_name: str,
        message: str,
        error: OSError | RuntimeError,
        failures: list[LifecycleFailure] | None,
    ) -> None:
        failure = LifecycleFailure(component_name, "shutdown", True, message)
        if failures is not None:
            if failure in failures:
                return
            failures.append(failure)
        log_handled_exception(
            self._logger,
            error,
            message=message,
            operation=OPERATION_APPLICATION_LIFECYCLE_SHUTDOWN_SERVERS,
            level="warning",
        )
