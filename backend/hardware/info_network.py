"""SoAI - Network interface information gathering [backend/hardware/info_network.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import socket
from typing import TYPE_CHECKING

import psutil

from core.errors.exception_logging import log_handled_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.hardware.constants import NETWORK_INTERFACE_STAT_KEYS
from core.logging.trace import get_logger
from hardware.operations import create_device_id

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("get_network_info",)

LOGGER_NAME = "SoAI.hardware.info_network"
OPERATION = "hardware_info.network.net_io_counters"


def get_network_info() -> JSONDict:
    logger = get_logger(LOGGER_NAME)
    interfaces: list[JSONDict] = []
    stats_by_interface: dict[str, JSONDict] = {}
    interface_status_by_name: dict[str, tuple[bool, int]] = {}
    try:
        raw_stats = psutil.net_io_counters(pernic=True)
    except RECOVERABLE_EXCEPTIONS as exception:
        log_handled_exception(
            logger,
            exception,
            message="Failed to query network I/O counters (non-critical).",
            operation=OPERATION,
            level="trace",
        )
        raw_stats = {}
    try:
        raw_interface_status = psutil.net_if_stats()
        interface_status_by_name = {
            name: (bool(status.isup), max(0, int(status.speed)))
            for name, status in raw_interface_status.items()
        }
    except RECOVERABLE_EXCEPTIONS as exception:
        log_handled_exception(
            logger,
            exception,
            message="Failed to query network interface status (non-critical).",
            operation=OPERATION,
            level="trace",
        )
        interface_status_by_name = {}
    for if_name, if_addrs in psutil.net_if_addrs().items():
        addresses: list[JSONDict] = []
        iface_info: JSONDict = {"name": if_name, "addresses": addresses}
        interface_status = interface_status_by_name.get(if_name)
        if interface_status is not None:
            is_up, link_speed_mbps = interface_status
            iface_info["is_up"] = is_up
            iface_info["link_speed_mbps"] = link_speed_mbps
        for addr in if_addrs:
            if addr.family == socket.AF_INET:
                addresses.append({"type": "ipv4", "address": addr.address, "netmask": addr.netmask})
            elif addr.family == socket.AF_INET6:
                addresses.append({"type": "ipv6", "address": addr.address, "netmask": addr.netmask})
            elif addr.family == psutil.AF_LINK:
                iface_info["mac_address"] = addr.address
        mac_candidate = None
        mac_address = iface_info.get("mac_address")
        if isinstance(mac_address, str) and mac_address:
            candidate = mac_address.replace("-", ":").lower()
            if any(char not in "0:" for char in candidate):
                mac_candidate = candidate
        address_tokens = sorted(
            [
                f"{item.get('type')}:{item.get('address')}"
                for item in addresses
                if item.get("type") and item.get("address")
            ],
        )
        hostname = socket.gethostname()
        address_part = "|".join(address_tokens) if address_tokens else "no_addr"
        if mac_candidate:
            primary_device_id = f"nic-{mac_candidate}"
        else:
            primary_device_id = f"nic-{hostname}-{if_name}-{address_part}"
        iface_info["device_id"] = create_device_id("nic", primary_device_id)
        interfaces.append(iface_info)
    for if_name, counters in raw_stats.items():
        counter_values = counters._asdict()
        stats_by_interface[if_name] = {
            field: counter_values.get(field, 0) for field in NETWORK_INTERFACE_STAT_KEYS
        }
    by_device_id: dict[str, JSONDict] = {}
    for iface in interfaces:
        device_id = iface.get("device_id")
        if not isinstance(device_id, str) or not device_id:
            continue
        interface_name = iface.get("name")
        by_device_id[device_id] = {
            "name": interface_name,
            "mac_address": iface.get("mac_address"),
            "addresses": iface.get("addresses"),
            "is_up": iface.get("is_up"),
            "link_speed_mbps": iface.get("link_speed_mbps"),
            "stats": (
                stats_by_interface.get(interface_name, {})
                if isinstance(interface_name, str)
                else {}
            ),
        }
    return {
        "interfaces": interfaces,
        "hostname": socket.gethostname(),
        "stats": stats_by_interface,
        "by_device_id": by_device_id,
    }
