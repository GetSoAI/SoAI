"""SoAI - V1 release artifact and platform contract [backend/app/updater/release_contract.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import re

from app.updater.release_manifest_types import ReleaseInstaller, ReleaseUpdateArchive
from core.errors.exceptions import ValidationError

__all__ = (
    "COMPLETE_ARCHIVE_TYPE",
    "INSTALLER_TYPE",
    "LINUX_UPDATE_PLATFORMS",
    "OS_UPDATE_PLATFORMS",
    "SUPPORTED_UPDATE_PLATFORMS",
    "WINDOWS_UPDATE_PLATFORMS",
    "checksum_asset_name",
    "linux_update_archive_name",
    "os_linux_update_archive_name",
    "release_manifest_asset_name",
    "release_manifest_signature_asset_name",
    "require_canonical_release_version",
    "supported_update_platforms_for_edition",
    "validate_release_artifact_contract",
    "windows_installer_name",
)

COMPLETE_ARCHIVE_TYPE = "complete_archive"
INSTALLER_TYPE = "installer"
LINUX_UPDATE_PLATFORMS = (
    "linux-x64",
    "linux-arm64",
)
WINDOWS_UPDATE_PLATFORMS = ("windows-x64",)
SUPPORTED_UPDATE_PLATFORMS = frozenset((*LINUX_UPDATE_PLATFORMS, *WINDOWS_UPDATE_PLATFORMS))
OS_UPDATE_PLATFORMS = ("linux-x64", "linux-arm64")
CANONICAL_RELEASE_VERSION_PATTERN = r"[0-9]+\.[0-9]+\.[0-9]+(?:[-+][0-9A-Za-z.-]+)?\Z"


def require_canonical_release_version(version: str) -> str:
    if (
        not isinstance(version, str)
        or re.fullmatch(CANONICAL_RELEASE_VERSION_PATTERN, version) is None
    ):
        raise ValidationError("Release version is not canonical.")
    return version


def supported_update_platforms_for_edition(edition: str) -> tuple[str, ...]:
    if edition == "soai-core":
        return LINUX_UPDATE_PLATFORMS
    if edition == "soai-os":
        return OS_UPDATE_PLATFORMS
    raise ValidationError("Release edition is invalid.")


def linux_update_archive_name(version: str) -> str:
    return f"SoAI-{version}-linux-complete.zip"


def windows_installer_name(version: str) -> str:
    return f"SoAI-{version}-windows-x64-setup.exe"


def os_linux_update_archive_name(version: str) -> str:
    return f"SoAI-OS-{version}-linux-complete.zip"


def release_manifest_asset_name(version: str, *, edition: str) -> str:
    prefix = "SoAI" if edition == "soai-core" else "SoAI-OS"
    return f"{prefix}-{version}-release-manifest-v1.json"


def release_manifest_signature_asset_name(version: str, *, edition: str) -> str:
    return f"{release_manifest_asset_name(version, edition=edition)}.sig"


def checksum_asset_name(artifact_name: str) -> str:
    return f"{artifact_name}.sha256"


def validate_release_artifact_contract(
    *,
    version: str,
    edition: str,
    core_version: str,
    archives: tuple[ReleaseUpdateArchive, ...],
    installers: tuple[ReleaseInstaller, ...],
) -> None:
    require_canonical_release_version(version)
    if edition == "soai-os":
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
    expected_archives = ((linux_update_archive_name(version), LINUX_UPDATE_PLATFORMS),)
    actual_archives = tuple((archive.name, archive.platforms) for archive in archives)
    if actual_archives != expected_archives:
        raise ValidationError("Release update archives do not match the V1 artifact contract.")
    if len(installers) != 1 or installers[0].name != windows_installer_name(version):
        raise ValidationError("Release installer does not match the V1 artifact contract.")
    if installers[0].platforms != WINDOWS_UPDATE_PLATFORMS:
        raise ValidationError("Release installer platforms do not match the V1 artifact contract.")
