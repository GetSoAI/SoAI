"""SoAI - TLS network address discovery [backend/features/api/middleware/tls_network.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import ipaddress
import socket
from typing import TYPE_CHECKING

from core.errors.exception_logging import log_handled_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger
from core.network.hosts import is_bind_all_interfaces_host
from core.types.json import JSONValue
from core.types.json_value import coerce_json_dict

if TYPE_CHECKING:
    from core.hardware.protocols import HardwareManagerProtocol

__all__ = ("get_accessible_network_addresses",)

LOGGER_NAME = "SoAI.features.api.tls_network"
OPERATION = "api_middleware.tls.get_network_addresses"


def _collect_network_addresses(network_info: JSONValue, port: int) -> tuple[list[str], bool]:
    network_dict = coerce_json_dict(network_info)
    interfaces_raw = network_dict.get("interfaces") if network_dict else None
    interfaces: list[JSONValue] = list(interfaces_raw) if isinstance(interfaces_raw, list) else []
    addresses: list[str] = []
    has_interface_entries = False
    for interface in interfaces:
        interface_dict = coerce_json_dict(interface)
        if interface_dict is None:
            continue
        has_interface_entries = True
        addresses_raw = interface_dict.get("addresses")
        if not isinstance(addresses_raw, list):
            continue
        for address_entry in addresses_raw:
            address_dict = coerce_json_dict(address_entry)
            if address_dict is None:
                continue
            raw_address = address_dict.get("address")
            if not isinstance(raw_address, str) or not raw_address:
                continue
            try:
                parsed_address = ipaddress.ip_address(raw_address)
            except ValueError:
                continue
            if parsed_address.is_loopback or parsed_address.is_link_local:
                continue
            if parsed_address.version == 6:
                addresses.append(f"[{raw_address}]:{port}")
            else:
                addresses.append(f"{raw_address}:{port}")
    return (sorted(set(addresses)), has_interface_entries)


def get_accessible_network_addresses(
    host: str,
    port: int,
    scheme: str,
    hw_manager: HardwareManagerProtocol,
) -> str | None:
    logger = get_logger(LOGGER_NAME)
    if not is_bind_all_interfaces_host(host):
        return None
    try:
        network_addresses, has_interfaces = _collect_network_addresses(
            hw_manager.get_network_info(),
            port,
        )
        if not has_interfaces:
            hostname = socket.gethostname()
            return f"Network access available via hostname: {hostname}"
        if not network_addresses:
            return "No external network addresses detected."
        address_list = ", ".join(f"{scheme}://{address}" for address in network_addresses)
        if len(network_addresses) == 1:
            return f"Network address available: {address_list}"
        return f"Network addresses available: {address_list}"
    except RECOVERABLE_EXCEPTIONS as exception:
        log_handled_exception(
            logger,
            exception,
            message="Failed to compute external network addresses (non-critical).",
            operation=OPERATION,
            level="debug",
        )
        return None
