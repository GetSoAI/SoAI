"""SoAI - Core OS network types [backend/core/os/network_types.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from core.timing.epoch import epoch_ms

__all__ = (
    "NetworkConnection",
    "NetworkConnectionConfig",
    "NetworkConnectionProfile",
    "NetworkDevice",
    "NetworkStatusSnapshot",
)


@dataclass(frozen=True, slots=True)
class NetworkConnection:
    connection_id: str
    name: str
    connection_type: str
    device: str | None
    state: str | None
    active: bool
    profile_editable: bool


@dataclass(frozen=True, slots=True)
class NetworkDevice:
    device: str
    device_type: str | None
    state: str | None
    connection: str | None
    ipv4_addresses: tuple[str, ...] = ()
    ipv4_gateway: str | None = None
    ipv4_dns: tuple[str, ...] = ()
    ipv6_addresses: tuple[str, ...] = ()
    ipv6_gateway: str | None = None
    ipv6_dns: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class NetworkConnectionConfig:
    ipv4_method: Literal["auto", "manual"] | None = None
    ipv4_addresses: tuple[str, ...] | None = None
    ipv4_gateway: str | None = None
    ipv4_dns: tuple[str, ...] | None = None
    ipv6_method: Literal["auto", "manual"] | None = None
    ipv6_addresses: tuple[str, ...] | None = None
    ipv6_gateway: str | None = None
    ipv6_dns: tuple[str, ...] | None = None
    autoconnect: bool | None = None


@dataclass(frozen=True, slots=True)
class NetworkConnectionProfile:
    connection_id: str
    name: str
    connection_type: str
    autoconnect: bool
    ipv4_method: Literal["auto", "manual"]
    ipv4_addresses: tuple[str, ...] = ()
    ipv4_gateway: str = ""
    ipv4_dns: tuple[str, ...] = ()
    ipv6_method: Literal["auto", "manual"] = "auto"
    ipv6_addresses: tuple[str, ...] = ()
    ipv6_gateway: str = ""
    ipv6_dns: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class NetworkStatusSnapshot:
    devices: tuple[NetworkDevice, ...]
    connections: tuple[NetworkConnection, ...]
    timestamp_ms: int = field(default_factory=epoch_ms)
