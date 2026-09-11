"""SoAI - Public offline signed release verification [backend/app/updater/offline_release_verification.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import argparse
import hashlib
import os
import stat
import sys
from typing import TYPE_CHECKING

from app.updater.offline_release_archive import verify_complete_release_archive
from app.updater.release_artifact_files import (
    read_bounded_release_file,
    require_regular_release_file,
)
from app.updater.release_contract import (
    checksum_asset_name,
    macos_release_manifest_asset_name,
    release_manifest_asset_name,
    require_canonical_release_version,
    windows_release_manifest_asset_name,
)
from app.updater.release_manifest import parse_release_manifest_bytes
from app.updater.release_signature import (
    release_public_key_fingerprint,
    verify_release_manifest_signature,
)
from core.errors.exceptions import ValidationError
from core.filesystem.open_files import open_binary
from core.meta.software_update_platforms import (
    MACOS_UPDATE_PLATFORMS,
    WINDOWS_UPDATE_PLATFORMS,
)
from core.serialization.sha256_hexdigest import is_canonical_sha256_hexdigest

if TYPE_CHECKING:
    from app.updater.release_manifest_types import ReleaseManifestV1

__all__ = ("main", "verify_offline_release")

MAX_MANIFEST_BYTES = 64 * 1024 * 1024
MAX_SIGNATURE_BYTES = 1024
MAX_CHECKSUM_BYTES = 1024
MAX_UPLOAD_INVENTORY_BYTES = 64 * 1024


def _sha256_file(path: str) -> str:
    digest = hashlib.sha256()
    try:
        with open_binary(path, mode="rb") as file_handle:
            while chunk := file_handle.read(1024 * 1024):
                digest.update(chunk)
    except OSError as exception:
        raise ValidationError("Release artifact is unreadable.") from exception
    return digest.hexdigest()


def _require_artifact(path: str, *, name: str, size_bytes: int, sha256: str) -> None:
    file_stat = require_regular_release_file(path, label=f"Release artifact {name}")
    actual_sha256 = _sha256_file(path)
    if file_stat.st_size != size_bytes or actual_sha256 != sha256:
        raise ValidationError(f"Release artifact does not match the signed manifest: {name}")


def _require_checksum(
    artifacts_directory: str,
    *,
    artifact_name: str,
    expected_sha256: str,
) -> bytes:
    checksum_name = checksum_asset_name(artifact_name)
    checksum_path = os.path.join(artifacts_directory, checksum_name)
    try:
        checksum_text = read_bounded_release_file(
            checksum_path,
            maximum_bytes=MAX_CHECKSUM_BYTES,
            label=f"Release checksum {checksum_name}",
        ).decode("utf-8", errors="strict")
    except UnicodeError as exception:
        raise ValidationError(f"Release checksum is unreadable: {checksum_name}") from exception
    if checksum_text != f"{expected_sha256}  {artifact_name}\n":
        raise ValidationError(f"Release checksum is invalid: {checksum_name}")
    return checksum_text.encode("utf-8")


def _require_exact_release_set(
    artifacts_directory: str,
    *,
    expected_names: frozenset[str],
) -> None:
    try:
        directory_stat = os.stat(artifacts_directory, follow_symlinks=False)
    except OSError as exception:
        raise ValidationError(
            "Release artifacts directory is missing or unreadable."
        ) from exception
    if not stat.S_ISDIR(directory_stat.st_mode) or os.path.islink(artifacts_directory):
        raise ValidationError("Release artifacts directory must be a regular directory.")
    try:
        entries = tuple(os.scandir(artifacts_directory))
    except OSError as exception:
        raise ValidationError("Release artifacts directory is unreadable.") from exception
    actual_names = frozenset(entry.name for entry in entries)
    if actual_names != expected_names:
        raise ValidationError(
            "Release artifact inputs do not match the exact V1 release set.",
            details={
                "missing": sorted(expected_names.difference(actual_names)),
                "unexpected": sorted(actual_names.difference(expected_names)),
            },
        )
    for expected_name in expected_names:
        require_regular_release_file(
            os.path.join(artifacts_directory, expected_name),
            label=f"Release artifact {expected_name}",
        )


def _read_upload_inventory(path: str) -> list[str]:
    try:
        content = read_bounded_release_file(
            path,
            maximum_bytes=MAX_UPLOAD_INVENTORY_BYTES,
            label="Release upload inventory",
        )
        return content.decode("utf-8", errors="strict").splitlines()
    except UnicodeError as exception:
        raise ValidationError("Release upload inventory is unreadable.") from exception


def verify_offline_release(
    *,
    artifacts_directory: str,
    version: str,
    core_version: str,
    edition: str,
    public_key_path: str,
    expected_public_key_sha256: str,
) -> None:
    require_canonical_release_version(version)
    require_canonical_release_version(core_version)
    if edition not in {"soai-core", "soai-os"}:
        raise ValidationError("Release edition is invalid.")
    if core_version != version:
        raise ValidationError("Release Core version must match the release version.")
    if not is_canonical_sha256_hexdigest(expected_public_key_sha256):
        raise ValidationError("Expected release public key fingerprint is invalid.")
    output_prefix = "SoAI" if edition == "soai-core" else "SoAI-OS"
    inventory_name = f"{output_prefix}-{version}-upload-inventory.txt"
    require_regular_release_file(public_key_path, label="Release public key")
    fingerprint = release_public_key_fingerprint(public_key_path)
    if fingerprint != expected_public_key_sha256:
        raise ValidationError("Release public key fingerprint does not match the trusted value.")
    primary_manifest_spec = (
        release_manifest_asset_name(version, edition=edition),
        None,
    )
    manifest_specs: tuple[tuple[str, str | None], ...]
    if edition == "soai-core":
        manifest_specs = (
            primary_manifest_spec,
            (
                macos_release_manifest_asset_name(version),
                MACOS_UPDATE_PLATFORMS[0],
            ),
            (
                windows_release_manifest_asset_name(version),
                WINDOWS_UPDATE_PLATFORMS[0],
            ),
        )
    else:
        manifest_specs = (primary_manifest_spec,)
    manifests: list[ReleaseManifestV1] = []
    for manifest_name, expected_platform_id in manifest_specs:
        signature_name = f"{manifest_name}.sig"
        manifest_bytes = read_bounded_release_file(
            os.path.join(artifacts_directory, manifest_name),
            maximum_bytes=MAX_MANIFEST_BYTES,
            label="Release manifest",
        )
        signature_bytes = read_bounded_release_file(
            os.path.join(artifacts_directory, signature_name),
            maximum_bytes=MAX_SIGNATURE_BYTES,
            label="Release manifest signature",
        )
        verify_release_manifest_signature(
            manifest_bytes=manifest_bytes,
            signature_bytes=signature_bytes,
            public_key_path=public_key_path,
        )
        manifest = parse_release_manifest_bytes(
            manifest_bytes,
            expected_version=version,
            expected_edition=edition,
            expected_platform_id=expected_platform_id,
        )
        if manifest.core_version != core_version:
            raise ValidationError(
                "Release manifest Core version does not match the expected version."
            )
        if manifest.public_trust.release_signing_key_sha256 != fingerprint:
            raise ValidationError("Release manifest public trust does not match the signing key.")
        manifests.append(manifest)
    archive_names = tuple(
        archive.name for manifest in manifests for archive in manifest.update_archives
    )
    installer_names = tuple(
        installer.name for manifest in manifests for installer in manifest.installers
    )
    artifact_names = (*archive_names, *installer_names)
    if len(frozenset(artifact_names)) != len(artifact_names):
        raise ValidationError("Release manifests contain duplicate artifact names.")
    manifest_names = tuple(name for name, _ in manifest_specs)
    expected_names = frozenset(
        (
            *artifact_names,
            *(checksum_asset_name(name) for name in artifact_names),
            *manifest_names,
            *(f"{name}.sig" for name in manifest_names),
            inventory_name,
        )
    )
    _require_exact_release_set(artifacts_directory, expected_names=expected_names)
    for manifest in manifests:
        for archive in manifest.update_archives:
            archive_path = os.path.join(artifacts_directory, archive.name)
            _require_artifact(
                archive_path,
                name=archive.name,
                size_bytes=archive.size_bytes,
                sha256=archive.sha256,
            )
            _require_checksum(
                artifacts_directory,
                artifact_name=archive.name,
                expected_sha256=archive.sha256,
            )
            verify_complete_release_archive(
                archive_path,
                archive_record=archive,
                manifest=manifest,
            )
        for installer in manifest.installers:
            installer_path = os.path.join(artifacts_directory, installer.name)
            _require_artifact(
                installer_path,
                name=installer.name,
                size_bytes=installer.size_bytes,
                sha256=installer.sha256,
            )
            _require_checksum(
                artifacts_directory,
                artifact_name=installer.name,
                expected_sha256=installer.sha256,
            )
    inventory_path = os.path.join(artifacts_directory, inventory_name)
    inventory_names = _read_upload_inventory(inventory_path)
    if inventory_names != sorted(expected_names.difference({inventory_name})):
        raise ValidationError("Release upload inventory is incomplete or non-deterministic.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify a complete signed SoAI V1 release.")
    parser.add_argument("--artifacts-directory", required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--core-version", required=True)
    parser.add_argument("--edition", required=True, choices=("soai-core", "soai-os"))
    parser.add_argument("--public-key", required=True)
    parser.add_argument("--expected-public-key-sha256", required=True)
    arguments = parser.parse_args()
    try:
        verify_offline_release(
            artifacts_directory=arguments.artifacts_directory,
            version=arguments.version,
            core_version=arguments.core_version,
            edition=arguments.edition,
            public_key_path=arguments.public_key,
            expected_public_key_sha256=arguments.expected_public_key_sha256,
        )
    except ValidationError as exception:
        sys.stderr.write(f"Release verification failed: {exception}\n")
        raise SystemExit(1) from exception
    sys.stdout.write(
        "Release signature, checksums, artifacts, and archive inventories are valid.\n"
    )


if __name__ == "__main__":
    main()
