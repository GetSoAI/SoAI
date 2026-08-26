"""SoAI - CLI status network inspection [backend/app/cli/status/network.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import socket

import psutil

from app.cli.status.types import ListeningEndpoint
from core.errors.exception_logging import log_handled_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger
from core.network.hosts import is_bind_all_interfaces_host

__all__ = (
    "get_listening_endpoints_quick",
    "list_candidate_api_hosts",
)

LOGGER_NAME_APP_BOOTSTRAP = "SoAI.app.cli.bootstrap"
LOGGER_NAME_CLI_STATUS = "SoAI.app.cli.status"
OPERATION_APP_CLI_STATUS_GET_LISTENING_ENDPOINTS_QUICK = (
    "app.cli.status.get_listening_endpoints_quick"
)
OPERATION_CLI_STATUS_LIST_CANDIDATE_API_HOSTS = "cli.status.list_candidate_api_hosts"
STATUS_NETWORK_RECOVERABLE_EXCEPTIONS: tuple[type[Exception], ...] = (
    *RECOVERABLE_EXCEPTIONS,
    psutil.Error,
)


def list_candidate_api_hosts(*, bind_host: str) -> list[str]:
    if not is_bind_all_interfaces_host(bind_host):
        return [bind_host]

    candidates: list[str] = ["127.0.0.1", "localhost"]
    try:
        interfaces = psutil.net_if_addrs()
        for entries in interfaces.values():
            for entry in entries:
                if entry.family != socket.AF_INET:
                    continue
                address = entry.address
                if address.startswith("127."):
                    continue
                if address.startswith("169.254."):
                    continue
                if address not in candidates:
                    candidates.append(address)
    except STATUS_NETWORK_RECOVERABLE_EXCEPTIONS as exception:
        log_handled_exception(
            get_logger(LOGGER_NAME_CLI_STATUS),
            exception,
            message="Failed to list network interfaces for bind-all host resolution (non-critical).",
            operation=OPERATION_CLI_STATUS_LIST_CANDIDATE_API_HOSTS,
            level="debug",
        )

    return candidates


def get_listening_endpoints_quick(
    pid: int,
    *,
    port: int | None,
) -> list[ListeningEndpoint] | None:
    try:
        endpoints: list[ListeningEndpoint] = []
        for connection in psutil.net_connections("inet"):
            connection_pid = connection.pid
            if connection_pid != pid:
                continue
            if connection.status != "LISTEN":
                continue
            laddr = connection.laddr
            if isinstance(laddr, tuple):
                continue
            ip = laddr.ip
            local_port = laddr.port
            if port is not None and local_port != port:
                continue
            endpoint = ListeningEndpoint(ip=ip, port=local_port)
            if endpoint not in endpoints:
                endpoints.append(endpoint)
        return endpoints or None
    except STATUS_NETWORK_RECOVERABLE_EXCEPTIONS as exception:
        log_handled_exception(
            get_logger(LOGGER_NAME_APP_BOOTSTRAP),
            exception,
            message="Failed to collect listening sockets for status output (non-critical).",
            operation=OPERATION_APP_CLI_STATUS_GET_LISTENING_ENDPOINTS_QUICK,
            level="debug",
        )
        return None
