"""SoAI - TLS network address discovery [backend/features/api/middleware/tls_network.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import psutil

from core.errors.exception_logging import log_handled_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger
from core.network.hosts import is_bind_all_interfaces_host
from core.network.interface_addresses import list_connect_addresses
from core.network.urls import build_host_port_url

__all__ = ("get_accessible_network_addresses",)

LOGGER_NAME = "SoAI.features.api.tls_network"
OPERATION = "api_middleware.tls.get_network_addresses"
NETWORK_ADDRESS_RECOVERABLE_EXCEPTIONS: tuple[type[Exception], ...] = (
    *RECOVERABLE_EXCEPTIONS,
    psutil.Error,
    OSError,
)


def get_accessible_network_addresses(host: str, port: int, scheme: str) -> str | None:
    if not is_bind_all_interfaces_host(host):
        return None
    try:
        network_addresses = list_connect_addresses(host)
    except NETWORK_ADDRESS_RECOVERABLE_EXCEPTIONS as exception:
        log_handled_exception(
            get_logger(LOGGER_NAME),
            exception,
            message="Failed to compute external network addresses (non-critical).",
            operation=OPERATION,
            level="debug",
        )
        return None
    if not network_addresses:
        return "No external network addresses detected."
    address_list = ", ".join(
        build_host_port_url(scheme, address, port) for address in network_addresses
    )
    if len(network_addresses) == 1:
        return f"Network address available: {address_list}"
    return f"Network addresses available: {address_list}"
