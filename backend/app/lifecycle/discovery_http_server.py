"""SoAI - Bounded discovery HTTP server transport [backend/app/lifecycle/discovery_http_server.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import socket
import ssl
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import BoundedSemaphore
from typing import TYPE_CHECKING, override

from core.timing.constants import LOCAL_IO_TIMEOUT_SEC

__all__ = (
    "DISCOVERY_CONNECTION_TIMEOUT_SECONDS",
    "DISCOVERY_MAX_WORKERS",
    "DISCOVERY_REQUEST_QUEUE_SIZE",
    "DiscoveryHTTPServer",
)

if TYPE_CHECKING:
    type DiscoveryClientAddress = tuple[str, int] | tuple[str, int, int, int]
    type DiscoveryRequest = socket.socket | tuple[bytes, socket.socket]

DISCOVERY_CONNECTION_TIMEOUT_SECONDS = LOCAL_IO_TIMEOUT_SEC
DISCOVERY_MAX_WORKERS = 16
DISCOVERY_REQUEST_QUEUE_SIZE = 32


def _accept_discovery_request(
    server_socket: socket.socket,
) -> tuple[socket.socket, DiscoveryClientAddress]:
    accept_request = server_socket.accept
    return accept_request()


def _try_acquire_worker_slot(worker_slots: BoundedSemaphore) -> bool:
    acquire_slot = worker_slots.acquire
    return bool(acquire_slot(blocking=False))


class DiscoveryHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    block_on_close = False
    request_queue_size = DISCOVERY_REQUEST_QUEUE_SIZE

    def __init__(
        self,
        server_address: tuple[str, int],
        request_handler_class: type[BaseHTTPRequestHandler],
    ) -> None:
        super().__init__(server_address, request_handler_class)
        self._worker_slots: BoundedSemaphore = BoundedSemaphore(DISCOVERY_MAX_WORKERS)
        self._tls_context: ssl.SSLContext | None = None

    def set_transport_layer_security_context(self, context: ssl.SSLContext) -> None:
        self._tls_context = context

    @override
    def get_request(self) -> tuple[socket.socket, DiscoveryClientAddress]:
        request, client_address = _accept_discovery_request(self.socket)
        request.settimeout(float(DISCOVERY_CONNECTION_TIMEOUT_SECONDS))
        return request, client_address

    @override
    def process_request(
        self,
        request: DiscoveryRequest,
        client_address: DiscoveryClientAddress,
    ) -> None:
        if not isinstance(request, socket.socket):
            super().process_request(request, client_address)
            return
        if not _try_acquire_worker_slot(self._worker_slots):
            self.shutdown_request(request)
            return
        try:
            super().process_request(request, client_address)
        except RuntimeError:
            self._worker_slots.release()
            raise

    @override
    def process_request_thread(
        self,
        request: DiscoveryRequest,
        client_address: DiscoveryClientAddress,
    ) -> None:
        if not isinstance(request, socket.socket):
            super().process_request_thread(request, client_address)
            return
        try:
            transport_request = self._wrap_request_transport(request)
            if transport_request is None:
                return
            super().process_request_thread(transport_request, client_address)
        finally:
            self._worker_slots.release()

    def _wrap_request_transport(self, request: socket.socket) -> socket.socket | None:
        tls_context = self._tls_context
        if tls_context is None:
            return request
        try:
            return tls_context.wrap_socket(
                request,
                server_side=True,
                do_handshake_on_connect=True,
            )
        except OSError:
            self.shutdown_request(request)
            return None
