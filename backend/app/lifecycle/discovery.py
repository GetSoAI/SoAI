"""SoAI - Port discovery HTTP server for WebUI connectivity [backend/app/lifecycle/discovery.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Callable

from app.lifecycle.dependencies import DiscoveryServerDependencies
from app.lifecycle.discovery_callbacks import (
    build_discovery_release_token_callback,
    build_discovery_shutdown_server_callback,
)
from app.lifecycle.discovery_http_server import DiscoveryHTTPServer
from app.lifecycle.discovery_runtime import (
    DiscoveryServerThreadState,
    create_discovery_server_thread_state,
    serve_discovery_server,
    shutdown_discovery_server,
)
from app.lifecycle.discovery_tls import apply_discovery_transport_layer_security
from app.lifecycle.discovery_validation import resolve_discovery_cors_origin
from app.lifecycle.port_discovery_handler import (
    PortDiscoveryHandler,
    build_port_discovery_handler,
)
from core.bootstrap.discovery_ports import DISCOVERY_PORTS
from core.concurrency.cancellation import CancellationToken
from core.concurrency.ephemeral_tasks import create_ephemeral_task
from core.concurrency.protocols import CancellationTokenProtocol
from core.concurrency.task_finalization import cancel_and_await_task
from core.errors.exception_logging import log_exception
from core.errors.exceptions import ValidationError
from core.licensing.types import Edition
from core.meta.instance_identity import InstanceIdentity
from core.runtime.soai_identifiers import create_system_id
from core.tasks.cancellation_token_release import release_cancellation_token

__all__ = (
    "DiscoveryServer",
    "DiscoveryServerDependencies",
    "PortDiscoveryHandler",
    "resolve_discovery_cors_origin",
)

OPERATION_APPLICATION_LIFECYCLE_DISCOVERY_SERVER_START = (
    "application_lifecycle.discovery_server.start"
)


class DiscoveryServer:
    PORT_RANGE = DISCOVERY_PORTS

    def __init__(self, deps: DiscoveryServerDependencies) -> None:
        self._logger_supplier = deps.logger_supplier
        self._token_collection = deps.token_collection
        self._cancellation_history = deps.cancellation_history
        self._cancellation_event_bus = deps.cancellation_event_bus
        self._cancellation_binder = deps.cancellation_binder
        self._finalizer_tracker = deps.finalizer_tracker
        self._server: DiscoveryHTTPServer | None = None
        self._task: asyncio.Task[None] | None = None
        self._server_thread_state: DiscoveryServerThreadState | None = None

    def _set_state(
        self,
        server: DiscoveryHTTPServer | None,
        task: asyncio.Task[None] | None,
        server_thread_state: DiscoveryServerThreadState | None,
    ) -> None:
        self._server = server
        self._task = task
        self._server_thread_state = server_thread_state

    async def _clear_stale_state(self) -> None:
        server = self._server
        self._set_state(None, None, None)
        if server is not None:
            await asyncio.to_thread(server.server_close)

    async def _rollback_failed_start(
        self,
        *,
        server: DiscoveryHTTPServer | None,
        task: asyncio.Task[None] | None,
        server_thread_state: DiscoveryServerThreadState | None,
        release_token_callback: Callable[[asyncio.Task[None]], None] | None,
        token: CancellationTokenProtocol | None,
        cancellation_id: str,
    ) -> None:
        if server is not None and server_thread_state is not None:
            await shutdown_discovery_server(server, server_thread_state)
        if task is not None:
            if release_token_callback is not None:
                task.remove_done_callback(release_token_callback)
            await cancel_and_await_task(task)
        if server is not None:
            await asyncio.to_thread(server.server_close)
        if token is not None:
            await self._release_token(token, cancellation_id)

    async def start(
        self,
        host: str,
        main_api_port: int,
        scheme: str = "http",
        *,
        preferred_api_port: int,
        instance_identity: InstanceIdentity,
        edition: Edition,
        transport_layer_security_options: dict[str, str | int] | None = None,
    ) -> bool:
        if self._task is not None:
            if not self._task.done():
                return True
            await self._clear_stale_state()
        main_api_scheme = str(scheme or "http").strip()
        handler_class = build_port_discovery_handler(
            main_api_port=main_api_port,
            preferred_api_port=preferred_api_port,
            main_api_scheme=main_api_scheme,
            edition=edition,
            instance_identity=instance_identity,
        )
        logger = self._logger_supplier()
        occupied_ports: list[int] = []

        for port in self.PORT_RANGE:
            server: DiscoveryHTTPServer | None = None
            task: asyncio.Task[None] | None = None
            server_thread_state: DiscoveryServerThreadState | None = None
            release_token_callback: Callable[[asyncio.Task[None]], None] | None = None
            token: CancellationTokenProtocol | None = None
            cancellation_id = create_system_id(
                subsystem="discovery_server",
                owner=str(port),
                include_random_suffix=False,
            )
            try:
                server = DiscoveryHTTPServer((host, port), handler_class)
                apply_discovery_transport_layer_security(
                    server,
                    transport_layer_security_options,
                )
                event_loop = asyncio.get_running_loop()
                task_holder: dict[str, asyncio.Task[None] | None] = {"task": None}
                server_thread_state = create_discovery_server_thread_state()
                shutdown_callback = build_discovery_shutdown_server_callback(
                    server=server,
                    server_thread_state=server_thread_state,
                    port_number=port,
                    task_holder=task_holder,
                    cancellation_id=cancellation_id,
                    cancellation_binder=self._cancellation_binder,
                    event_loop=event_loop,
                    logger=logger,
                    finalizer_tracker=self._finalizer_tracker,
                )
                token = CancellationToken(
                    cancellation_id,
                    owner="port_discovery_server",
                    metadata={"port": port},
                    on_cancel=shutdown_callback,
                )
                add_result = await self._token_collection.add_token(cancellation_id, token)
                if add_result.added:
                    await self._cancellation_event_bus.publish_event(
                        "token_registered",
                        cancellation_id,
                    )
                existing_reason = await self._cancellation_history.get_reason(cancellation_id)
                task = create_ephemeral_task(
                    asyncio.to_thread(serve_discovery_server, server, server_thread_state),
                    name=f"port-discovery-server-{port}",
                )
                task_holder["task"] = task
                release_token_callback = build_discovery_release_token_callback(
                    event_loop=event_loop,
                    token=token,
                    cancellation_id=cancellation_id,
                    cancellation_binder=self._cancellation_binder,
                    release_token=self._release_token,
                    finalizer_tracker=self._finalizer_tracker,
                    logger=logger,
                )
                task.add_done_callback(release_token_callback)
                if existing_reason:
                    token.cancel(existing_reason)
                self._set_state(server, task, server_thread_state)
                if occupied_ports:
                    logger.warning(
                        "Discovery ports %s were already in use; discovery server fell back to port %s.",
                        ", ".join(str(occupied_port) for occupied_port in occupied_ports),
                        port,
                    )
                logger.info(
                    "Port discovery server started on %s://%s:%s (main API: %s://%s:%s).",
                    main_api_scheme,
                    host,
                    port,
                    main_api_scheme,
                    host,
                    main_api_port,
                )
                return True
            except OSError as error:
                if error.errno in [98, 48, 10048]:
                    occupied_ports.append(port)
                    continue
                await self._rollback_failed_start(
                    server=server,
                    task=task,
                    server_thread_state=server_thread_state,
                    release_token_callback=release_token_callback,
                    token=token,
                    cancellation_id=cancellation_id,
                )
                log_exception(
                    logger,
                    error,
                    message=f"Failed to start discovery server on port {port}",
                    operation=OPERATION_APPLICATION_LIFECYCLE_DISCOVERY_SERVER_START,
                )
                break
            except (
                RuntimeError,
                ValueError,
                ValidationError,
            ) as exception:
                await self._rollback_failed_start(
                    server=server,
                    task=task,
                    server_thread_state=server_thread_state,
                    release_token_callback=release_token_callback,
                    token=token,
                    cancellation_id=cancellation_id,
                )
                log_exception(
                    logger,
                    exception,
                    message=f"An unexpected error occurred while starting discovery server on port {port}",
                    operation=OPERATION_APPLICATION_LIFECYCLE_DISCOVERY_SERVER_START,
                )
                break
        logger.critical(
            "Could not start the port discovery server on any port in the 7950-7960 range (occupied ports: %s). The WebUI may fail to connect if the main API port is changed.",
            ", ".join(str(occupied_port) for occupied_port in occupied_ports) or "none",
        )
        return False

    async def _release_token(self, token: CancellationTokenProtocol, cancellation_id: str) -> None:
        await release_cancellation_token(
            token_collection=self._token_collection,
            cancellation_history=self._cancellation_history,
            cancellation_event_bus=self._cancellation_event_bus,
            cancellation_id=cancellation_id,
            token=token,
            publish_release_event=True,
        )

    def has_active_server(self) -> bool:
        return self._server is not None and self._task is not None and not self._task.done()

    async def stop(self) -> None:
        if not self._server or not self._task:
            return
        server = self._server
        server_thread_state = self._server_thread_state
        logger = self._logger_supplier()
        logger.debug("Shutting down port discovery server...")
        if not self._task.done():
            if server_thread_state is not None:
                await shutdown_discovery_server(server, server_thread_state)
            self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            logger.debug("Port discovery server has been shut down.")
        finally:
            await asyncio.to_thread(server.server_close)
            self._set_state(None, None, None)
