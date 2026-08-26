"""SoAI - Host normalization and bind helpers [backend/core/network/hosts.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import ipaddress

__all__ = (
    "anonymize_ip",
    "bind_all_interfaces_host_v4",
    "is_bind_all_interfaces_host",
    "normalize_host",
)


def _strip_scope_id(host: str) -> str:
    if "%" in host:
        return host.split("%", 1)[0]
    return host


def normalize_host(host: str | None) -> str | None:
    if not host:
        return None
    candidate = host.strip().lower()
    if candidate.startswith("[") and candidate.endswith("]"):
        candidate = candidate[1:-1]
    candidate = _strip_scope_id(candidate)
    return candidate or None


def bind_all_interfaces_host_v4() -> str:
    return str(ipaddress.IPv4Address(0))


def is_bind_all_interfaces_host(host: str | None) -> bool:
    normalized_host = normalize_host(host)
    if not normalized_host:
        return False
    try:
        ip_obj = ipaddress.ip_address(normalized_host)
    except ValueError:
        return False
    return ip_obj.is_unspecified


def anonymize_ip(ip_str: str) -> str:
    try:
        ip_address = ipaddress.ip_address(ip_str)
        if isinstance(ip_address, ipaddress.IPv4Address):
            return str(ipaddress.ip_network(f"{ip_address}/24", strict=False).network_address)
        return str(ipaddress.ip_network(f"{ip_address}/64", strict=False).network_address)
    except ValueError:
        return ip_str
