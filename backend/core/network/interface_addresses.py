"""SoAI - Reachable interface address listing for device pairing [backend/core/network/interface_addresses.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import ipaddress
import socket
from typing import TYPE_CHECKING, Literal

import psutil

from core.network.hosts import is_bind_all_interfaces_host, normalize_host
from core.runtime.network_policy import is_loopback_host

__all__ = (
    "classify_bind_scope",
    "list_connect_addresses",
)

if TYPE_CHECKING:
    type BindScope = Literal["loopback", "all_interfaces", "specific"]
    type IpAddress = ipaddress.IPv4Address | ipaddress.IPv6Address

_PRIMARY_ROUTE_PROBE_PORT = 9
_PRIMARY_ROUTE_PROBE_HOST_V4 = "192.0.2.1"
_PRIMARY_ROUTE_PROBE_HOST_V6 = "2001:db8::1"


def classify_bind_scope(bind_host: str) -> BindScope:
    if is_loopback_host(bind_host):
        return "loopback"
    if is_bind_all_interfaces_host(bind_host):
        return "all_interfaces"
    return "specific"


def list_connect_addresses(bind_host: str, *, limit: int = 8) -> tuple[str, ...]:
    bind_scope = classify_bind_scope(bind_host)
    normalized_host = normalize_host(bind_host)
    if bind_scope == "loopback" or normalized_host is None:
        return ()
    if bind_scope == "specific":
        return (normalized_host,)
    address_family = _socket_family(ipaddress.ip_address(normalized_host))
    addresses = sorted(_list_interface_addresses(address_family))
    primary_address = _resolve_primary_route_address(address_family)
    if primary_address is not None and primary_address in addresses:
        addresses.remove(primary_address)
        addresses.insert(0, primary_address)
    return tuple(str(address) for address in addresses[:limit])


def _socket_family(address: IpAddress) -> socket.AddressFamily:
    if address.version == 6:
        return socket.AF_INET6
    return socket.AF_INET


def _is_connectable_address(address: IpAddress) -> bool:
    return not (
        address.is_loopback
        or address.is_link_local
        or address.is_unspecified
        or address.is_multicast
    )


def _parse_interface_address(raw_address: str) -> IpAddress | None:
    normalized_address = normalize_host(raw_address)
    if normalized_address is None:
        return None
    try:
        return ipaddress.ip_address(normalized_address)
    except ValueError:
        return None


def _list_interface_addresses(address_family: socket.AddressFamily) -> list[IpAddress]:
    interface_stats = psutil.net_if_stats()
    addresses: list[IpAddress] = []
    for interface_name, interface_addresses in psutil.net_if_addrs().items():
        stats = interface_stats.get(interface_name)
        if stats is None or not stats.isup:
            continue
        for interface_address in interface_addresses:
            if interface_address.family != address_family:
                continue
            address = _parse_interface_address(interface_address.address)
            if address is None or not _is_connectable_address(address):
                continue
            if address not in addresses:
                addresses.append(address)
    return addresses


def _resolve_primary_route_address(address_family: socket.AddressFamily) -> IpAddress | None:
    probe_host = (
        _PRIMARY_ROUTE_PROBE_HOST_V6
        if address_family == socket.AF_INET6
        else _PRIMARY_ROUTE_PROBE_HOST_V4
    )
    try:
        with socket.socket(address_family, socket.SOCK_DGRAM) as probe_socket:
            probe_socket.connect((probe_host, _PRIMARY_ROUTE_PROBE_PORT))
            local_address = probe_socket.getsockname()[0]
    except OSError:
        return None
    if not isinstance(local_address, str):
        return None
    return _parse_interface_address(local_address)
