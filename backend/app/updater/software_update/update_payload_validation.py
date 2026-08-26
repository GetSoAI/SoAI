"""SoAI - Signed staged update payload validation [backend/app/updater/software_update/update_payload_validation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os

from app.edition_composition import UpdaterComposition
from app.updater.release_manifest_types import ReleaseManifestV1, ReleaseUpdateArchive
from app.updater.software_update.frontend_payload_validation import (
    validate_staged_frontend,
)
from app.updater.software_update.install_transaction_state import (
    EXECUTABLE_UPDATE_FILES,
    TRANSACTION_PREFIX,
    required_update_paths,
)
from core.errors.exceptions import ValidationError
from core.files.staged_transfer import compute_file_sha256

__all__ = ("validate_and_prepare_staged_update",)


def _staged_file_paths(staged_root: str) -> tuple[str, ...]:
    relative_paths: list[str] = []
    for directory_path, directory_names, file_names in os.walk(
        staged_root,
        followlinks=False,
    ):
        for directory_name in directory_names:
            directory_entry = os.path.join(directory_path, directory_name)
            if os.path.islink(directory_entry):
                raise ValidationError("Update archive extracted a symbolic-link directory.")
        for file_name in file_names:
            file_path = os.path.join(directory_path, file_name)
            if os.path.islink(file_path) or not os.path.isfile(file_path):
                raise ValidationError("Update archive extracted a non-regular file.")
            relative_paths.append(os.path.relpath(file_path, staged_root).replace(os.sep, "/"))
    return tuple(sorted(relative_paths))


def _validate_signed_file_records(
    *,
    staged_root: str,
    archive_record: ReleaseUpdateArchive,
) -> None:
    expected_paths = tuple(record.path for record in archive_record.files)
    actual_paths = _staged_file_paths(staged_root)
    if actual_paths != expected_paths:
        missing_paths = sorted(set(expected_paths).difference(actual_paths))
        unexpected_paths = sorted(set(actual_paths).difference(expected_paths))
        raise ValidationError(
            "Staged update files do not match the signed release manifest.",
            details={
                "missing": missing_paths[:20],
                "unexpected": unexpected_paths[:20],
            },
        )
    for record in archive_record.files:
        file_path = os.path.join(staged_root, *record.path.split("/"))
        if os.path.getsize(file_path) != record.size_bytes:
            raise ValidationError(f"Staged update file size is invalid: {record.path}")
        digest = compute_file_sha256(file_path).sha256_hex
        if digest != record.sha256:
            raise ValidationError(f"Staged update file hash is invalid: {record.path}")


def validate_and_prepare_staged_update(
    *,
    staged_root: str,
    platform_id: str,
    archive_record: ReleaseUpdateArchive,
    manifest: ReleaseManifestV1,
    updater: UpdaterComposition,
) -> None:
    _validate_signed_file_records(
        staged_root=staged_root,
        archive_record=archive_record,
    )
    updater.validate_staged_payload(staged_root, manifest)
    for relative_path in required_update_paths(platform_id):
        staged_path = os.path.join(staged_root, *relative_path.split("/"))
        if not os.path.isfile(staged_path) or os.path.islink(staged_path):
            raise ValidationError(f"Update archive is missing required path: {relative_path}")
    for item_name in os.listdir(staged_root):
        if item_name.startswith(TRANSACTION_PREFIX):
            raise ValidationError(f"Update archive contains reserved top-level item: {item_name}")
    validate_staged_frontend(
        staged_root,
        frontend_relative_path="frontend",
        expected_edition="soai-core",
        fallback_relative_paths=(),
    )
    for relative_file in EXECUTABLE_UPDATE_FILES:
        file_path = os.path.join(staged_root, *relative_file.split("/"))
        if os.path.isfile(file_path):
            os.chmod(file_path, 0o700)
