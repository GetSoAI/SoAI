"""SoAI - Core OS types [backend/core/os/types.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

__all__ = ("OSCapabilities",)


@dataclass(frozen=True, slots=True)
class OSCapabilities:
    systemctl_available: bool
    systemd_active: bool
    soai_service_installed: bool
    soai_service_enabled: bool
    soai_service_conflict: bool
    network_manager: bool
    apt_available: bool
    dkms_available: bool
    secure_boot_enabled: bool
    is_root: bool
    sudo_available: bool
    debian_version: str | None
