"""SoAI - Signed release manifest V1 validation [backend/app/updater/release_manifest.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
import unicodedata
from typing import TYPE_CHECKING

from app.updater.release_contract import (
    COMPLETE_ARCHIVE_TYPE,
    INSTALLER_TYPE,
    SUPPORTED_UPDATE_PLATFORMS,
    validate_release_artifact_contract,
)
from app.updater.release_identity import (
    parse_legal_fingerprints,
    parse_public_trust,
    parse_release_identity,
)
from app.updater.release_manifest_bindings import validate_release_manifest_bindings
from app.updater.release_manifest_types import (
    ReleaseFileRecord,
    ReleaseInstaller,
    ReleaseManifestV1,
    ReleaseUpdateArchive,
)
from core.errors.exceptions import ValidationError
from core.runtime.platform import normalize_platform_id
from core.serialization.json_parsing import parse_json_dict
from core.serialization.sha256_hexdigest import is_canonical_sha256_hexdigest
from core.types.json_value import require_json_dict_list
from core.validation.strings import coerce_required_non_empty_str

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = ("parse_release_manifest_bytes", "select_update_archive")

RELEASE_MANIFEST_SCHEMA_VERSION = 1
RELEASE_PRODUCT = "SoAI"
RELEASE_SIGNATURE_ALGORITHM = "ed25519"


def _require_positive_exact_int(value: JSONValue, *, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValidationError(f"{field} must be a positive integer.")
    return value


def _require_nonnegative_exact_int(value: JSONValue, *, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValidationError(f"{field} must be a non-negative integer.")
    return value


def _require_sha256(value: JSONValue, *, field: str) -> str:
    if not isinstance(value, str) or not is_canonical_sha256_hexdigest(value):
        raise ValidationError(f"{field} must be a canonical SHA-256 digest.")
    return value


def _require_platforms(value: JSONValue, *, field: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not value:
        raise ValidationError(f"{field} must be a non-empty array.")
    platforms: list[str] = []
    for raw_platform in value:
        if not isinstance(raw_platform, str):
            raise ValidationError(f"{field} entries must be strings.")
        platform_id = normalize_platform_id(raw_platform)
        if platform_id is None or platform_id != raw_platform:
            raise ValidationError(f"{field} contains an invalid platform ID.")
        if platform_id not in SUPPORTED_UPDATE_PLATFORMS:
            raise ValidationError(f"{field} contains an unsupported platform ID.")
        if platform_id in platforms:
            raise ValidationError(f"{field} contains a duplicate platform ID.")
        platforms.append(platform_id)
    return tuple(platforms)


def _require_release_path(value: JSONValue, *, field: str) -> str:
    path = coerce_required_non_empty_str(value, label=field)
    normalized = path.replace("\\", "/")
    if (
        normalized != path
        or unicodedata.normalize("NFC", path) != path
        or path.startswith("/")
        or path.endswith("/")
        or ":" in path
    ):
        raise ValidationError(f"{field} must be a canonical relative path.")
    parts = path.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        raise ValidationError(f"{field} must be a canonical relative path.")
    if os.path.isabs(path) or "\x00" in path:
        raise ValidationError(f"{field} must be a canonical relative path.")
    return path


def _parse_file_records(value: JSONValue, *, archive_name: str) -> tuple[ReleaseFileRecord, ...]:
    entries = require_json_dict_list(value, label=f"{archive_name}.files")
    if not entries:
        raise ValidationError(f"{archive_name}.files must not be empty.")
    records: list[ReleaseFileRecord] = []
    paths: set[str] = set()
    casefold_paths: set[str] = set()
    for entry in entries:
        _require_exact_fields(
            entry,
            frozenset({"path", "size_bytes", "sha256"}),
            label=f"{archive_name}.files entry",
        )
        path = _require_release_path(entry.get("path"), field=f"{archive_name}.files.path")
        canonical_casefold_path = unicodedata.normalize("NFC", path).casefold()
        if path in paths or canonical_casefold_path in casefold_paths:
            raise ValidationError(f"Release manifest contains duplicate file path: {path}")
        paths.add(path)
        casefold_paths.add(canonical_casefold_path)
        records.append(
            ReleaseFileRecord(
                path=path,
                size_bytes=_require_nonnegative_exact_int(
                    entry.get("size_bytes"),
                    field=f"{archive_name}.{path}.size_bytes",
                ),
                sha256=_require_sha256(
                    entry.get("sha256"),
                    field=f"{archive_name}.{path}.sha256",
                ),
            ),
        )
    if tuple(sorted(paths)) != tuple(record.path for record in records):
        raise ValidationError(f"{archive_name}.files must be sorted by path.")
    return tuple(records)


def _parse_update_archive(entry: JSONDict) -> ReleaseUpdateArchive:
    _require_exact_fields(
        entry,
        frozenset(
            {
                "type",
                "name",
                "platforms",
                "size_bytes",
                "sha256",
                "archive_root",
                "files",
            }
        ),
        label="Update archive",
    )
    if entry.get("type") != COMPLETE_ARCHIVE_TYPE:
        raise ValidationError("Update archive type must be complete_archive.")
    name = coerce_required_non_empty_str(entry.get("name"), label="update archive name")
    if not name.endswith("-complete.zip") or "/" in name or "\\" in name:
        raise ValidationError("Update archive name is invalid.")
    archive_root = coerce_required_non_empty_str(
        entry.get("archive_root"),
        label=f"{name}.archive_root",
    )
    if archive_root != RELEASE_PRODUCT:
        raise ValidationError(f"{name}.archive_root must be {RELEASE_PRODUCT}.")
    return ReleaseUpdateArchive(
        name=name,
        platforms=_require_platforms(entry.get("platforms"), field=f"{name}.platforms"),
        size_bytes=_require_positive_exact_int(entry.get("size_bytes"), field=f"{name}.size_bytes"),
        sha256=_require_sha256(entry.get("sha256"), field=f"{name}.sha256"),
        archive_root=archive_root,
        files=_parse_file_records(entry.get("files"), archive_name=name),
    )


def _parse_installer(entry: JSONDict) -> ReleaseInstaller:
    _require_exact_fields(
        entry,
        frozenset({"type", "name", "platforms", "size_bytes", "sha256"}),
        label="Installer",
    )
    if entry.get("type") != INSTALLER_TYPE:
        raise ValidationError("Installer type must be installer.")
    name = coerce_required_non_empty_str(entry.get("name"), label="installer name")
    if not name.endswith("-setup.exe") or "/" in name or "\\" in name:
        raise ValidationError("Installer name is invalid.")
    return ReleaseInstaller(
        name=name,
        platforms=_require_platforms(entry.get("platforms"), field=f"{name}.platforms"),
        size_bytes=_require_positive_exact_int(entry.get("size_bytes"), field=f"{name}.size_bytes"),
        sha256=_require_sha256(entry.get("sha256"), field=f"{name}.sha256"),
    )


def _require_exact_fields(
    payload: JSONDict, expected_fields: frozenset[str], *, label: str
) -> None:
    actual_fields = frozenset(payload)
    if actual_fields != expected_fields:
        raise ValidationError(f"{label} fields do not match the V1 contract.")


def parse_release_manifest_bytes(
    manifest_bytes: bytes,
    *,
    expected_version: str,
    expected_edition: str,
) -> ReleaseManifestV1:
    payload = parse_json_dict(
        manifest_bytes,
        field="SoAI release manifest",
        reject_duplicate_keys=True,
    )
    _require_exact_fields(
        payload,
        frozenset(
            {
                "schema_version",
                "product",
                "edition",
                "version",
                "core_version",
                "release_identity",
                "legal_fingerprints",
                "public_trust",
                "signature_algorithm",
                "update_archives",
                "installers",
            },
        ),
        label="Release manifest",
    )
    if payload.get("schema_version") != RELEASE_MANIFEST_SCHEMA_VERSION:
        raise ValidationError("Release manifest schema_version must be 1.")
    if payload.get("product") != RELEASE_PRODUCT:
        raise ValidationError("Release manifest product must be SoAI.")
    edition = coerce_required_non_empty_str(payload.get("edition"), label="release edition")
    if edition not in {"soai-core", "soai-os"} or edition != expected_edition:
        raise ValidationError("Release manifest edition does not match the installed edition.")
    version = coerce_required_non_empty_str(payload.get("version"), label="release version")
    if version != expected_version:
        raise ValidationError("Release manifest version does not match the GitHub release tag.")
    core_version = coerce_required_non_empty_str(
        payload.get("core_version"),
        label="release Core version",
    )
    if core_version != version:
        raise ValidationError("SoAI release version and core_version must match.")
    if payload.get("signature_algorithm") != RELEASE_SIGNATURE_ALGORITHM:
        raise ValidationError("Release manifest signature_algorithm must be ed25519.")
    archives = tuple(
        _parse_update_archive(entry)
        for entry in require_json_dict_list(payload.get("update_archives"), label="update_archives")
    )
    installers = tuple(
        _parse_installer(entry)
        for entry in require_json_dict_list(payload.get("installers"), label="installers")
    )
    if not archives:
        raise ValidationError("Release manifest must contain update archives.")
    artifact_names = [archive.name for archive in archives]
    artifact_names.extend(installer.name for installer in installers)
    if len(set(artifact_names)) != len(artifact_names):
        raise ValidationError("Release manifest contains duplicate artifact names.")
    validate_release_artifact_contract(
        version=version,
        edition=edition,
        core_version=core_version,
        archives=archives,
        installers=installers,
    )
    manifest = ReleaseManifestV1(
        edition=edition,
        version=version,
        core_version=core_version,
        release_identity=parse_release_identity(payload.get("release_identity"), version),
        legal_fingerprints=parse_legal_fingerprints(payload.get("legal_fingerprints")),
        public_trust=parse_public_trust(payload.get("public_trust")),
        update_archives=archives,
        installers=installers,
    )
    validate_release_manifest_bindings(manifest)
    return manifest


def select_update_archive(
    manifest: ReleaseManifestV1,
    *,
    platform_id: str,
) -> ReleaseUpdateArchive:
    normalized_platform_id = normalize_platform_id(platform_id)
    if normalized_platform_id is None or normalized_platform_id != platform_id:
        raise ValidationError("Current platform ID is invalid.")
    matches = [archive for archive in manifest.update_archives if platform_id in archive.platforms]
    if not matches:
        raise ValidationError(f"Release has no supported update archive for {platform_id}.")
    if len(matches) != 1:
        raise ValidationError(f"Release has multiple update archives for {platform_id}.")
    return matches[0]
