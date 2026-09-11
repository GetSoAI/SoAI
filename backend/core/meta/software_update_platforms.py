"""SoAI - Software update platform capabilities [backend/core/meta/software_update_platforms.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exceptions import ValidationError

__all__ = (
    "COMPLETE_ARCHIVE_TYPE",
    "INSTALLER_TYPE",
    "LINUX_UPDATE_PLATFORMS",
    "MACOS_UPDATE_PLATFORMS",
    "OS_UPDATE_PLATFORMS",
    "SUPPORTED_UPDATE_PLATFORMS",
    "WINDOWS_UPDATE_PLATFORMS",
    "delivery_type_for_platform",
    "supported_update_platforms_for_edition",
)

COMPLETE_ARCHIVE_TYPE = "complete_archive"
INSTALLER_TYPE = "installer"
LINUX_UPDATE_PLATFORMS = (
    "linux-x64",
    "linux-arm64",
)
MACOS_UPDATE_PLATFORMS = (
    "darwin-x64",
    "darwin-arm64",
)
WINDOWS_UPDATE_PLATFORMS = ("windows-x64",)
SUPPORTED_UPDATE_PLATFORMS = (
    *LINUX_UPDATE_PLATFORMS,
    *MACOS_UPDATE_PLATFORMS,
    *WINDOWS_UPDATE_PLATFORMS,
)
OS_UPDATE_PLATFORMS = ("linux-x64", "linux-arm64")


def supported_update_platforms_for_edition(edition: str) -> tuple[str, ...]:
    if edition == "soai-core":
        return SUPPORTED_UPDATE_PLATFORMS
    if edition == "soai-os":
        return OS_UPDATE_PLATFORMS
    raise ValidationError("Release edition is invalid.")


def delivery_type_for_platform(platform_id: str | None) -> str | None:
    if platform_id in (*LINUX_UPDATE_PLATFORMS, *MACOS_UPDATE_PLATFORMS):
        return COMPLETE_ARCHIVE_TYPE
    if platform_id in WINDOWS_UPDATE_PLATFORMS:
        return INSTALLER_TYPE
    return None
