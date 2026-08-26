"""SoAI - Uvicorn server launch runtime [backend/app/server_uvicorn_runtime.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import socket
import ssl
from collections.abc import Callable, Generator
from contextlib import contextmanager
from typing import TYPE_CHECKING, override

from uvicorn import Server
from uvicorn.config import Config
from websockets.exceptions import InvalidState

from app.application_dependencies import ApplicationLogging, ApplicationServerModuleDependencies
from app.internal_protocols import LifecycleCoordinatorProtocol, UvicornServerProtocol
from app.uvicorn_http_timeout_protocol import SoAIHttpToolsProtocol
from app.uvicorn_websocket_timeout_protocol import SoAIWebSocketsSansIOProtocol
from core.errors.exception_logging import log_handled_exception
from core.logging.protocols import LoggerProtocol
from core.runtime.soai_identifiers import build_soai_id, safe_or_hashed_segment
from core.security.tls_policy import apply_server_tls_policy
from core.tasks.protocols import (
    TaskCancellationBinderProtocol,
    TaskFinalizerTrackerProtocol,
)

if TYPE_CHECKING:
    from fastapi import FastAPI

__all__ = (
    "SoAIUvicornServer",
    "start_uvicorn_server_runtime",
)

OPERATION_UVICORN_SERVER_SHUTDOWN = "app.server_uvicorn_runtime.shutdown"
SOAI_WEBSOCKET_MAX_MESSAGE_BYTES = 16 * 1024 * 1024


class SoAIUvicornServer(Server):
    @contextmanager
    @override
    def capture_signals(self) -> Generator[None, None, None]:
        yield


async def start_uvicorn_server_runtime(
    *,
    app: FastAPI,
    host: str,
    port: int,
    sockets: list[socket.socket],
    proxy_headers_enabled: bool,
    trusted_proxy_networks: tuple[str, ...],
    transport_layer_security_options: dict[str, str | int],
    logging: ApplicationLogging,
    lifecycle_coordinator: LifecycleCoordinatorProtocol,
    cancellation_binder: TaskCancellationBinderProtocol,
    finalizer_tracker: TaskFinalizerTrackerProtocol,
    module_dependencies: ApplicationServerModuleDependencies,
) -> None:
    server_configuration_options = _build_uvicorn_configuration_options(
        host=host,
        port=port,
        proxy_headers_enabled=proxy_headers_enabled,
        trusted_proxy_networks=trusted_proxy_networks,
        transport_layer_security_options=transport_layer_security_options,
    )
    server_configuration = module_dependencies.uvicorn.Config(app, **server_configuration_options)
    server_instance = module_dependencies.uvicorn_server_factory(server_configuration)
    server_task = module_dependencies.spawn_tracked_task(
        _serve_uvicorn_until_shutdown(server_instance, sockets, logging.logger),
        name=f"uvicorn-{host}:{port}",
        logger=logging.logger,
        cancellation_binder=cancellation_binder,
        finalizer_tracker=finalizer_tracker,
        cancellation_id=build_soai_id(
            (
                "sys",
                "uvicorn",
                safe_or_hashed_segment(str(host)),
                safe_or_hashed_segment(str(port)),
            ),
        ),
        owner="uvicorn_server",
        metadata={"host": host, "port": port},
    )
    lifecycle_coordinator.register_server(server_instance, server_task)
    await lifecycle_coordinator.wait_until_started(30.0)


async def _serve_uvicorn_until_shutdown(
    server: UvicornServerProtocol,
    sockets: list[socket.socket],
    logger: LoggerProtocol,
) -> None:
    try:
        await server.serve(sockets=sockets)
    except InvalidState as exception:
        if not (server.should_exit or server.force_exit):
            raise
        log_handled_exception(
            logger,
            exception,
            message="Uvicorn websocket connection was already closing during shutdown.",
            operation=OPERATION_UVICORN_SERVER_SHUTDOWN,
            details={
                "should_exit": bool(server.should_exit),
                "force_exit": bool(server.force_exit),
            },
            level="debug",
        )
    finally:
        for listener_socket in sockets:
            listener_socket.close()


def _build_uvicorn_configuration_options(
    *,
    host: str,
    port: int,
    proxy_headers_enabled: bool,
    trusted_proxy_networks: tuple[str, ...],
    transport_layer_security_options: dict[str, str | int],
) -> dict[
    str,
    str
    | int
    | bool
    | None
    | type[SoAIHttpToolsProtocol]
    | type[SoAIWebSocketsSansIOProtocol]
    | Callable[[Config, Callable[[], ssl.SSLContext]], ssl.SSLContext],
]:
    forwarded_allow_addresses = None
    if proxy_headers_enabled and trusted_proxy_networks:
        forwarded_allow_addresses = ",".join(trusted_proxy_networks)
    server_configuration_options: dict[
        str,
        str
        | int
        | bool
        | None
        | type[SoAIHttpToolsProtocol]
        | type[SoAIWebSocketsSansIOProtocol]
        | Callable[[Config, Callable[[], ssl.SSLContext]], ssl.SSLContext],
    ] = {
        "host": host,
        "port": port,
        "log_config": None,
        "access_log": False,
        "lifespan": "off",
        "proxy_headers": proxy_headers_enabled,
        "http": SoAIHttpToolsProtocol,
        "ws": SoAIWebSocketsSansIOProtocol,
        "ws_max_size": SOAI_WEBSOCKET_MAX_MESSAGE_BYTES,
        "ws_per_message_deflate": False,
        "ws_ping_interval": None,
        "server_header": False,
    }
    if forwarded_allow_addresses:
        server_configuration_options["forwarded_allow_ips"] = forwarded_allow_addresses
    server_configuration_options.update(transport_layer_security_options)
    if "ssl_certfile" in transport_layer_security_options:
        server_configuration_options["ssl_context_factory"] = _build_soai_ssl_context
    return server_configuration_options


def _build_soai_ssl_context(
    _configuration: Config,
    default_factory: Callable[[], ssl.SSLContext],
) -> ssl.SSLContext:
    return apply_server_tls_policy(default_factory())
