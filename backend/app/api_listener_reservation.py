"""SoAI - Race-free API listener reservation policy [backend/app/api_listener_reservation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import errno
import os
import socket
from contextlib import ExitStack
from dataclasses import dataclass

from core.errors.network_exceptions import ApiPortConflictError, ApiPortRangeExhaustedError
from core.logging.trace import get_logger
from core.network.port_ownership import resolve_tcp_port_owners
from core.runtime.api_endpoint import RuntimeApiEndpoint

__all__ = (
    "ApiListenerReservation",
    "reserve_api_listener",
)

DEFAULT_API_PORT = 5090
FALLBACK_API_PORT_STOP = 5099
LOGGER_NAME = "SoAI.app.api_listener_reservation"


@dataclass(slots=True)
class ApiListenerReservation:
    endpoint: RuntimeApiEndpoint
    sockets: tuple[socket.socket, ...]
    occupied_ports: tuple[int, ...]

    def transfer_sockets(self) -> list[socket.socket]:
        listener_sockets = list(self.sockets)
        self.sockets = ()
        return listener_sockets

    def close(self) -> None:
        listener_sockets = self.sockets
        self.sockets = ()
        for listener_socket in listener_sockets:
            listener_socket.close()


def reserve_api_listener(
    host: str,
    preferred_port: int,
    *,
    scheme: str = "http",
) -> ApiListenerReservation:
    candidate_ports = (
        range(DEFAULT_API_PORT, FALLBACK_API_PORT_STOP + 1)
        if preferred_port == DEFAULT_API_PORT
        else (preferred_port,)
    )
    occupied_ports: list[int] = []
    for candidate_port in candidate_ports:
        listener_sockets, occupied = _reserve_candidate(host, candidate_port)
        if occupied:
            occupied_ports.append(candidate_port)
            _log_port_conflict(host, candidate_port)
            if preferred_port != DEFAULT_API_PORT:
                raise ApiPortConflictError(
                    f"API listener port {preferred_port} is already in use on host {host}. Choose an available SERVER.HTTP.NETWORK.PORT or stop the owning process.",
                    details={"host": host, "port": preferred_port},
                )
            continue
        endpoint = RuntimeApiEndpoint(
            bind_host=host,
            scheme=scheme,
            preferred_port=preferred_port,
            effective_port=candidate_port,
        )
        return ApiListenerReservation(
            endpoint=endpoint,
            sockets=listener_sockets,
            occupied_ports=tuple(occupied_ports),
        )
    rendered_ports = ", ".join(str(port) for port in occupied_ports)
    raise ApiPortRangeExhaustedError(
        f"API listener ports are already in use on host {host}: {rendered_ports}. Free a port in the automatic fallback range or configure an explicit available port.",
        details={"host": host, "occupied_ports": occupied_ports},
    )


def _reserve_candidate(
    host: str,
    port: int,
) -> tuple[tuple[socket.socket, ...], bool]:
    address_records = socket.getaddrinfo(
        host,
        port,
        family=socket.AF_UNSPEC,
        type=socket.SOCK_STREAM,
        proto=0,
        flags=socket.AI_PASSIVE,
    )
    unique_records = list(dict.fromkeys(address_records))
    listener_sockets: list[socket.socket] = []
    with ExitStack() as socket_ownership:
        for (
            address_family,
            socket_type,
            protocol,
            _canonical_name,
            socket_address,
        ) in unique_records:
            try:
                listener_socket = socket.socket(address_family, socket_type, protocol)
                socket_ownership.callback(listener_socket.close)
                if os.name == "posix":
                    listener_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                if address_family == socket.AF_INET6:
                    listener_socket.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 1)
                listener_socket.setblocking(False)
                listener_socket.bind(socket_address)
                listener_socket.listen()
                listener_sockets.append(listener_socket)
            except OSError as exception:
                if exception.errno == errno.EADDRNOTAVAIL:
                    continue
                if exception.errno == errno.EADDRINUSE:
                    return (), True
                raise
        if not listener_sockets:
            raise OSError(errno.EADDRNOTAVAIL, f"Could not bind API listener host {host}.")
        socket_ownership.pop_all()
        return tuple(listener_sockets), False


def _log_port_conflict(host: str, port: int) -> None:
    logger = get_logger(LOGGER_NAME)
    owners = resolve_tcp_port_owners(port)
    if not owners:
        logger.warning(
            "API listener conflict detected on %s:%s; owning process details are unavailable.",
            host,
            port,
        )
        return
    for owner in owners:
        logger.warning(
            "API listener conflict detected on %s:%s; owner PID %s (%s) will not be terminated.",
            host,
            port,
            owner.pid,
            owner.process_name,
        )
