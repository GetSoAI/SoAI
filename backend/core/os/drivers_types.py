"""SoAI - Core OS driver types [backend/core/os/drivers_types.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

__all__ = (
    "DKMSModule",
    "DKMSStatusSnapshot",
    "DriverPackageEntry",
    "DriverRuntimeToolEntry",
    "DriverStatusEntry",
    "DriverStatusSnapshot",
    "DriverVariantStatusEntry",
    "SecureBootStatus",
)


@dataclass(frozen=True, slots=True)
class DKMSModule:
    name: str
    version: str
    kernel_version: str
    status: str
    arch: str


@dataclass(frozen=True, slots=True)
class DKMSStatusSnapshot:
    modules: tuple[DKMSModule, ...]


@dataclass(frozen=True, slots=True)
class SecureBootStatus:
    enabled: bool
    setup_mode: bool
    mok_keys_present: bool
    mok_enrolled: bool


@dataclass(frozen=True, slots=True)
class DriverStatusSnapshot:
    drivers: tuple[DriverStatusEntry, ...]
    dkms_modules: tuple[DKMSModule, ...]
    secure_boot_status: SecureBootStatus


@dataclass(frozen=True, slots=True)
class DriverPackageEntry:
    package_name: str
    installed_version: str | None
    candidate_version: str | None
    preferred_suite: str | None
    installed: bool


@dataclass(frozen=True, slots=True)
class DriverRuntimeToolEntry:
    tool_name: str
    executable: str
    available: bool
    version: str | None
    unsupported_reason: str | None


@dataclass(frozen=True, slots=True)
class DriverVariantStatusEntry:
    variant_id: str
    label: str


@dataclass(frozen=True, slots=True)
class DriverStatusEntry:
    driver_id: str
    vendor: str
    display_name: str
    detected: bool
    installed: bool
    kernel_active: bool
    runtime_ready: bool
    ready: bool
    installable: bool
    uninstallable: bool
    variant_id: str | None
    available_variants: tuple[DriverVariantStatusEntry, ...]
    kernel_modules: tuple[str, ...]
    packages: tuple[DriverPackageEntry, ...]
    runtime_tools: tuple[DriverRuntimeToolEntry, ...]
    warnings: tuple[str, ...]
    reboot_required: bool
