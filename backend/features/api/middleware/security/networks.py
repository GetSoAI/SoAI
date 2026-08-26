"""SoAI - API security network parsing [backend/features/api/middleware/security/networks.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import ipaddress
from collections.abc import Collection
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError

if TYPE_CHECKING:
    from core.types.json import JSONValue

__all__ = (
    "client_ip_allowed",
    "is_ip_network_tuple",
    "parse_network_entries",
)


def client_ip_allowed(
    client_ip: str | None,
    whitelist: tuple[ipaddress.IPv4Network | ipaddress.IPv6Network, ...],
    blacklist: tuple[ipaddress.IPv4Network | ipaddress.IPv6Network, ...],
) -> bool:
    whitelist_match = _client_ip_in_networks(client_ip, whitelist)
    blacklist_match = _client_ip_in_networks(client_ip, blacklist)
    if whitelist:
        if whitelist_match:
            return True
        return False
    if blacklist_match:
        return False
    return True


def parse_network_entries(
    entries: Collection[JSONValue],
    *,
    error_label: str,
) -> tuple[ipaddress.IPv4Network | ipaddress.IPv6Network, ...]:
    networks: list[ipaddress.IPv4Network | ipaddress.IPv6Network] = []
    for entry in entries or ():
        text = str(entry or "").strip()
        if not text:
            continue
        try:
            network = ipaddress.ip_network(text, strict=False)
        except ValueError as exception:
            try:
                address = ipaddress.ip_address(text)
            except ValueError:
                raise ValidationError(f"Invalid {error_label} '{text}'.") from exception
            network = ipaddress.ip_network(
                f"{address}/32" if isinstance(address, ipaddress.IPv4Address) else f"{address}/128",
            )
        networks.append(network)
    return tuple(networks)


def is_ip_network_tuple(
    value: tuple[ipaddress.IPv4Network | ipaddress.IPv6Network | str, ...] | list[str] | None,
) -> bool:
    if not isinstance(value, tuple):
        return False
    return all(
        isinstance(network, ipaddress.IPv4Network | ipaddress.IPv6Network) for network in value
    )


def _client_ip_in_networks(
    client_ip: str | None,
    networks: tuple[ipaddress.IPv4Network | ipaddress.IPv6Network, ...],
) -> bool:
    if not client_ip or not networks:
        return False
    try:
        address = ipaddress.ip_address(client_ip)
    except ValueError:
        return False
    return any(address in network for network in networks)
