"""SoAI - Trusted proxy resolution helpers [backend/core/runtime/trusted_proxy.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import ipaddress

from starlette.applications import Starlette
from starlette.datastructures import State

from core.runtime.state_access import read_state_flag, read_state_has_key

__all__ = ("is_trusted_proxy_client_host", "read_trusted_proxy_networks")


def read_trusted_proxy_networks(
    state: State,
) -> tuple[ipaddress.IPv4Network | ipaddress.IPv6Network, ...] | None:
    if not read_state_has_key(state, "trusted_proxy_networks"):
        return None
    networks: tuple[ipaddress.IPv4Network | ipaddress.IPv6Network, ...] = state[
        "trusted_proxy_networks"
    ]
    if not isinstance(networks, tuple):
        return ()
    return networks


def is_trusted_proxy_client_host(app: Starlette | None, client_host: str | None) -> bool:
    if app is None or not client_host:
        return False
    state = app.state
    proxy_headers_enabled = read_state_flag(state, "proxy_headers_enabled")
    if not proxy_headers_enabled:
        return False
    if not read_state_has_key(state, "trusted_proxy_networks"):
        return False
    networks = read_trusted_proxy_networks(state)
    if not networks:
        return False
    try:
        address = ipaddress.ip_address(client_host)
    except ValueError:
        return False
    return any(address in network for network in networks)
