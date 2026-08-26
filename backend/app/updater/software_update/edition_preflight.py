"""SoAI - Edition-aware staged update preflight [backend/app/updater/software_update/edition_preflight.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
from dataclasses import dataclass

from app.updater.release_manifest_types import ReleaseManifestV1
from core.errors.exceptions import ValidationError
from core.filesystem.open_files import open_binary
from core.serialization.json_parsing import parse_json_dict

__all__ = (
    "InternalReleaseInfoV1",
    "require_internal_release_info",
    "validate_core_staged_update",
)

PRIVATE_LICENSE_MARKER = b"LicenseRef-" + b"SoAI-OS-"
RELEASE_INFO_FIELDS = frozenset(
    ("artifact_type", "core_version", "edition", "product", "schema_version", "version")
)


@dataclass(frozen=True, slots=True)
class InternalReleaseInfoV1:
    edition: str
    version: str
    core_version: str
    artifact_type: str


def require_internal_release_info(
    staged_root: str, manifest: ReleaseManifestV1
) -> InternalReleaseInfoV1:
    release_info_path = os.path.join(staged_root, "release-info-v1.json")
    try:
        with open_binary(release_info_path, mode="rb") as release_info_file:
            payload = parse_json_dict(
                release_info_file.read(),
                field="update payload release-info-v1.json",
                reject_duplicate_keys=True,
            )
    except (OSError, ValidationError) as exception:
        raise ValidationError("Update payload release-info-v1.json is invalid.") from exception
    if frozenset(payload) != RELEASE_INFO_FIELDS:
        raise ValidationError("Update payload release information does not match V1.")
    if payload.get("schema_version") != 1 or payload.get("product") != "SoAI":
        raise ValidationError("Update payload release product or schema is invalid.")
    edition = payload.get("edition")
    version = payload.get("version")
    core_version = payload.get("core_version")
    artifact_type = payload.get("artifact_type")
    if not isinstance(edition, str) or not edition:
        raise ValidationError("Update payload release information contains invalid edition.")
    if not isinstance(version, str) or not version:
        raise ValidationError("Update payload release information contains invalid version.")
    if not isinstance(core_version, str) or not core_version:
        raise ValidationError("Update payload release information contains invalid base version.")
    if not isinstance(artifact_type, str) or not artifact_type:
        raise ValidationError("Update payload release information contains invalid values.")
    release_info = InternalReleaseInfoV1(
        edition=edition,
        version=version,
        core_version=core_version,
        artifact_type=artifact_type,
    )
    if (
        release_info.edition != manifest.edition
        or release_info.version != manifest.version
        or release_info.core_version != manifest.core_version
        or release_info.artifact_type != "complete"
    ):
        raise ValidationError("External and internal release metadata do not agree.")
    return release_info


def validate_core_staged_update(staged_root: str, manifest: ReleaseManifestV1) -> None:
    release_info = require_internal_release_info(staged_root, manifest)
    if release_info.edition != "soai-core" or release_info.core_version != release_info.version:
        raise ValidationError("Core update metadata is incompatible.")
    if os.path.lexists(os.path.join(staged_root, "soai_os")):
        raise ValidationError("Core update payload contains private product material.")
    for directory_path, _, file_names in os.walk(staged_root, followlinks=False):
        for file_name in file_names:
            file_path = os.path.join(directory_path, file_name)
            try:
                with open_binary(file_path, mode="rb") as source_file:
                    retained = b""
                    while content := source_file.read(1024 * 1024):
                        inspected = retained + content
                        if PRIVATE_LICENSE_MARKER in inspected:
                            raise ValidationError(
                                "Core update payload contains unapproved first-party SPDX material."
                            )
                        retained = inspected[-(len(PRIVATE_LICENSE_MARKER) - 1) :]
            except OSError as exception:
                raise ValidationError(
                    "Core update payload contains an unreadable file."
                ) from exception
