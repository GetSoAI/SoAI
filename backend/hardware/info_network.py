"""SoAI - Network interface information gathering [backend/hardware/info_network.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import socket
from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING, Literal

import psutil

from core.errors.exception_logging import log_handled_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.hardware.constants import NETWORK_INTERFACE_STAT_KEYS
from core.logging.trace import get_logger
from core.runtime.platform import get_runtime_platform
from hardware.operations import create_device_id
from hardware.windows_network_adapters import query_windows_visible_adapter_names

if TYPE_CHECKING:
    from core.system.protocols import CommandExecutorProtocol
    from core.types.json import JSONDict

    type WindowsNetworkInventoryStatus = Literal["available", "unavailable"]
    type InterfaceAddressDetails = tuple[list[JSONDict], str | None]

__all__ = ("get_network_info",)

LOGGER_NAME = "SoAI.hardware.info_network"
OPERATION = "hardware_info.network.net_io_counters"


def get_network_info(executor: CommandExecutorProtocol) -> JSONDict:
    if not get_runtime_platform().is_windows:
        return _collect_psutil_network_info()
    visible_adapter_names = query_windows_visible_adapter_names(executor)
    if visible_adapter_names is None:
        return _build_network_payload([], {}, windows_inventory_status="unavailable")
    return _collect_windows_visible_network_info(visible_adapter_names)


def _collect_psutil_network_info() -> JSONDict:
    interface_status_by_name = _read_interface_status()
    interfaces = [
        _build_interface(if_name, address_details, interface_status_by_name.get(if_name))
        for if_name, address_details in _read_interface_addresses().items()
    ]
    return _build_network_payload(
        interfaces, _read_interface_counters(), windows_inventory_status=None
    )


def _collect_windows_visible_network_info(visible_adapter_names: Sequence[str]) -> JSONDict:
    canonical_name_by_alias = {name.casefold(): name for name in visible_adapter_names}
    addresses_by_name = _key_by_canonical_name(_read_interface_addresses(), canonical_name_by_alias)
    status_by_name = _key_by_canonical_name(_read_interface_status(), canonical_name_by_alias)
    counters_by_name = _key_by_canonical_name(_read_interface_counters(), canonical_name_by_alias)
    interfaces = [
        _build_interface(name, addresses_by_name.get(name, ([], None)), status_by_name.get(name))
        for name in visible_adapter_names
    ]
    return _build_network_payload(
        interfaces, counters_by_name, windows_inventory_status="available"
    )


def _key_by_canonical_name[ValueT](
    values_by_psutil_name: Mapping[str, ValueT],
    canonical_name_by_alias: Mapping[str, str],
) -> dict[str, ValueT]:
    values_by_canonical_name: dict[str, ValueT] = {}
    for psutil_name, value in values_by_psutil_name.items():
        canonical_name = canonical_name_by_alias.get(psutil_name.casefold())
        if canonical_name is not None:
            values_by_canonical_name[canonical_name] = value
    return values_by_canonical_name


def _read_interface_status() -> dict[str, tuple[bool, int]]:
    try:
        raw_interface_status = psutil.net_if_stats()
        return {
            name: (bool(status.isup), max(0, int(status.speed)))
            for name, status in raw_interface_status.items()
        }
    except RECOVERABLE_EXCEPTIONS as exception:
        log_handled_exception(
            get_logger(LOGGER_NAME),
            exception,
            message="Failed to query network interface status (non-critical).",
            operation=OPERATION,
            level="trace",
        )
        return {}


def _read_interface_counters() -> dict[str, JSONDict]:
    try:
        raw_stats = psutil.net_io_counters(pernic=True)
    except RECOVERABLE_EXCEPTIONS as exception:
        log_handled_exception(
            get_logger(LOGGER_NAME),
            exception,
            message="Failed to query network I/O counters (non-critical).",
            operation=OPERATION,
            level="trace",
        )
        return {}
    stats_by_interface: dict[str, JSONDict] = {}
    for if_name, counters in raw_stats.items():
        counter_values = counters._asdict()
        stats_by_interface[if_name] = {
            field: counter_values.get(field, 0) for field in NETWORK_INTERFACE_STAT_KEYS
        }
    return stats_by_interface


def _read_interface_addresses() -> dict[str, InterfaceAddressDetails]:
    address_details_by_name: dict[str, InterfaceAddressDetails] = {}
    for if_name, if_addrs in psutil.net_if_addrs().items():
        addresses: list[JSONDict] = []
        mac_address: str | None = None
        for addr in if_addrs:
            if addr.family == socket.AF_INET:
                addresses.append({"type": "ipv4", "address": addr.address, "netmask": addr.netmask})
            elif addr.family == socket.AF_INET6:
                addresses.append({"type": "ipv6", "address": addr.address, "netmask": addr.netmask})
            elif addr.family == psutil.AF_LINK:
                mac_address = addr.address
        address_details_by_name[if_name] = (addresses, mac_address)
    return address_details_by_name


def _build_interface(
    if_name: str,
    address_details: InterfaceAddressDetails,
    interface_status: tuple[bool, int] | None,
) -> JSONDict:
    addresses, mac_address = address_details
    iface_info: JSONDict = {"name": if_name, "addresses": addresses}
    if interface_status is not None:
        is_up, link_speed_mbps = interface_status
        iface_info["is_up"] = is_up
        iface_info["link_speed_mbps"] = link_speed_mbps
    if mac_address is not None:
        iface_info["mac_address"] = mac_address
    mac_candidate = None
    if mac_address:
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
    return iface_info


def _build_network_payload(
    interfaces: list[JSONDict],
    stats_by_interface: dict[str, JSONDict],
    *,
    windows_inventory_status: WindowsNetworkInventoryStatus | None,
) -> JSONDict:
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
    payload: JSONDict = {
        "interfaces": interfaces,
        "hostname": socket.gethostname(),
        "stats": stats_by_interface,
        "by_device_id": by_device_id,
    }
    if windows_inventory_status is not None:
        payload["windows_inventory_status"] = windows_inventory_status
    return payload
