"""SoAI - V1 release artifact contract [backend/app/updater/release_contract.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import re

from app.updater.release_manifest_types import ReleaseInstaller, ReleaseUpdateArchive
from core.errors.exceptions import ValidationError
from core.meta.software_update_platforms import (
    LINUX_UPDATE_PLATFORMS,
    MACOS_UPDATE_PLATFORMS,
    OS_UPDATE_PLATFORMS,
    WINDOWS_UPDATE_PLATFORMS,
)

__all__ = (
    "checksum_asset_name",
    "linux_update_archive_name",
    "macos_release_manifest_asset_name",
    "macos_release_manifest_signature_asset_name",
    "macos_update_archive_name",
    "os_linux_update_archive_name",
    "release_manifest_asset_name",
    "release_manifest_signature_asset_name",
    "require_canonical_release_version",
    "validate_release_artifact_contract",
    "windows_complete_archive_name",
    "windows_installer_name",
    "windows_release_manifest_asset_name",
    "windows_release_manifest_signature_asset_name",
)

CANONICAL_RELEASE_VERSION_PATTERN = r"[0-9]+\.[0-9]+\.[0-9]+(?:[-+][0-9A-Za-z.-]+)?\Z"


def require_canonical_release_version(version: str) -> str:
    if (
        not isinstance(version, str)
        or re.fullmatch(CANONICAL_RELEASE_VERSION_PATTERN, version) is None
    ):
        raise ValidationError("Release version is not canonical.")
    return version


def linux_update_archive_name(version: str) -> str:
    return f"SoAI-{version}-linux-complete.zip"


def macos_update_archive_name(version: str) -> str:
    return f"SoAI-{version}-macos-complete.zip"


def windows_installer_name(version: str) -> str:
    return f"SoAI-{version}-windows-x64-setup.exe"


def windows_complete_archive_name(version: str) -> str:
    return f"SoAI-{version}-windows-x64-complete.zip"


def windows_release_manifest_asset_name(version: str) -> str:
    return f"SoAI-{version}-windows-release-manifest-v1.json"


def windows_release_manifest_signature_asset_name(version: str) -> str:
    return f"{windows_release_manifest_asset_name(version)}.sig"


def os_linux_update_archive_name(version: str) -> str:
    return f"SoAI-OS-{version}-linux-complete.zip"


def release_manifest_asset_name(
    version: str,
    *,
    edition: str,
    platform_id: str | None = None,
) -> str:
    if edition == "soai-core" and platform_id in MACOS_UPDATE_PLATFORMS:
        return macos_release_manifest_asset_name(version)
    prefix = "SoAI" if edition == "soai-core" else "SoAI-OS"
    return f"{prefix}-{version}-release-manifest-v1.json"


def release_manifest_signature_asset_name(
    version: str,
    *,
    edition: str,
    platform_id: str | None = None,
) -> str:
    return f"{release_manifest_asset_name(version, edition=edition, platform_id=platform_id)}.sig"


def macos_release_manifest_asset_name(version: str) -> str:
    return f"SoAI-{version}-macos-release-manifest-v1.json"


def macos_release_manifest_signature_asset_name(version: str) -> str:
    return f"{macos_release_manifest_asset_name(version)}.sig"


def checksum_asset_name(artifact_name: str) -> str:
    return f"{artifact_name}.sha256"


def validate_release_artifact_contract(
    *,
    version: str,
    edition: str,
    core_version: str,
    archives: tuple[ReleaseUpdateArchive, ...],
    installers: tuple[ReleaseInstaller, ...],
    expected_platform_id: str | None = None,
) -> None:
    require_canonical_release_version(version)
    if edition == "soai-os":
        if expected_platform_id is not None:
            raise ValidationError("SoAI OS does not use a platform-specific V1 manifest.")
        if core_version != version:
            raise ValidationError("SoAI OS release version must match the SoAI Core version.")
        expected_archive = os_linux_update_archive_name(version)
        if tuple((archive.name, archive.platforms) for archive in archives) != (
            (expected_archive, OS_UPDATE_PLATFORMS),
        ):
            raise ValidationError("SoAI OS update archive does not match the V1 artifact contract.")
        if installers:
            raise ValidationError("SoAI OS releases cannot contain Windows installers.")
        return
    if edition != "soai-core" or core_version != version:
        raise ValidationError("SoAI Core release identity is invalid.")
    claimed_platforms: set[str] = set()
    for archive in archives:
        overlap = claimed_platforms.intersection(archive.platforms)
        if overlap:
            raise ValidationError("Release artifacts contain duplicate platform mappings.")
        claimed_platforms.update(archive.platforms)
    for installer in installers:
        overlap = claimed_platforms.intersection(installer.platforms)
        if overlap:
            raise ValidationError("Release artifacts contain duplicate platform mappings.")
        claimed_platforms.update(installer.platforms)
    expected_archives: tuple[tuple[str, tuple[str, ...]], ...]
    expected_installers: tuple[tuple[str, tuple[str, ...]], ...]
    if expected_platform_id in MACOS_UPDATE_PLATFORMS:
        expected_archives = ((macos_update_archive_name(version), MACOS_UPDATE_PLATFORMS),)
        expected_installers = ()
    elif expected_platform_id in WINDOWS_UPDATE_PLATFORMS:
        expected_archives = ((windows_complete_archive_name(version), WINDOWS_UPDATE_PLATFORMS),)
        expected_installers = ()
    elif expected_platform_id is None or expected_platform_id in LINUX_UPDATE_PLATFORMS:
        expected_archives = ((linux_update_archive_name(version), LINUX_UPDATE_PLATFORMS),)
        expected_installers = ((windows_installer_name(version), WINDOWS_UPDATE_PLATFORMS),)
    else:
        raise ValidationError("Release manifest platform is invalid.")
    actual_archives = tuple((archive.name, archive.platforms) for archive in archives)
    if actual_archives != expected_archives:
        raise ValidationError("Release update archives do not match the V1 artifact contract.")
    actual_installers = tuple((installer.name, installer.platforms) for installer in installers)
    if actual_installers != expected_installers:
        raise ValidationError("Release installers do not match the V1 artifact contract.")
