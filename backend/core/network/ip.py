"""SoAI - IP classification helpers for network policy [backend/core/network/ip.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import ipaddress

__all__ = (
    "is_disallowed_ip",
    "is_local_network_ip",
)

_LOCAL_NETWORK_RANGES: tuple[str, ...] = (
    "10.0.0.0/8",
    "172.16.0.0/12",
    "192.168.0.0/16",
    "127.0.0.0/8",
    "169.254.0.0/16",
    "::1/128",
    "fc00::/7",
    "fe80::/10",
)


def is_local_network_ip(
    ip_obj: ipaddress.IPv4Address | ipaddress.IPv6Address,
) -> bool:
    return any(
        ip_obj in ipaddress.ip_network(network_range) for network_range in _LOCAL_NETWORK_RANGES
    )


def is_disallowed_ip(
    ip_addr: ipaddress.IPv4Address | ipaddress.IPv6Address,
) -> bool:
    return bool(
        ip_addr.is_loopback
        or ip_addr.is_private
        or ip_addr.is_link_local
        or ip_addr.is_multicast
        or ip_addr.is_reserved
        or ip_addr.is_unspecified,
    )
