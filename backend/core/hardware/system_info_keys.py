"""SoAI - Canonical hardware/system-info component keys [backend/core/hardware/system_info_keys.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

__all__ = (
    "SYSTEM_INFO_COMPONENT_KEYS",
    "SYSTEM_INFO_COMPONENT_KEYS_EXCLUDING_CPU",
    "SYSTEM_INFO_ORDERED_KEYS_WITH_META",
)

SYSTEM_INFO_COMPONENT_KEYS: tuple[str, ...] = (
    "uptime",
    "os",
    "cpus",
    "cpu",
    "memory",
    "swap",
    "gpu",
    "motherboard",
    "disk",
    "disk_speed",
    "network",
    "network_speed",
)

SYSTEM_INFO_COMPONENT_KEYS_EXCLUDING_CPU: tuple[str, ...] = (
    "uptime",
    "os",
    "cpus",
    "memory",
    "swap",
    "gpu",
    "motherboard",
    "disk",
    "disk_speed",
    "network",
    "network_speed",
)

SYSTEM_INFO_ORDERED_KEYS_WITH_META: tuple[str, ...] = (
    "uptime",
    "os",
    "summary",
    "capabilities",
    "cpus",
    "cpu",
    "memory",
    "swap",
    "gpu",
    "motherboard",
    "disk",
    "disk_speed",
    "network",
    "network_speed",
)
