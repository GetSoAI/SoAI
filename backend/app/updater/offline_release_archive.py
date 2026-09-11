"""SoAI - Offline complete release archive verification [backend/app/updater/offline_release_archive.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
import shutil
import stat
import tempfile
import zipfile

from app.updater.release_artifact_files import require_regular_release_file
from app.updater.release_manifest_types import ReleaseManifestV1, ReleaseUpdateArchive
from app.updater.software_update.edition_preflight import (
    require_internal_release_info,
    validate_core_staged_update,
)
from app.updater.software_update.frontend_payload_validation import (
    validate_staged_frontend,
)
from app.updater.software_update.install_transaction_state import (
    MANAGED_CONFIG_DEFAULT_RELATIVE_COMPONENTS,
    MANAGED_VENDOR_RELATIVE_COMPONENTS,
    required_update_paths,
)
from core.archives.resource_limits import default_archive_resource_limits
from core.archives.zip_directory_budget import validate_zip_directory_budget
from core.archives.zip_plan import ZipPlanPolicy, build_validated_zip_plan
from core.archives.zip_plan_extraction import extract_validated_zip_plan
from core.errors.exceptions import ValidationError
from core.files.staged_transfer import compute_file_sha256
from core.filesystem.open_files import open_binary

__all__ = ("verify_complete_release_archive",)

FORBIDDEN_RELEASE_ROOTS = frozenset(
    {
        ".git",
        "backends",
        "backend_check",
        "cache",
        "config",
        "logs",
        "models",
        "node_modules",
        "release_tools",
        "soai_main_venv",
        "soai_plugins_venv",
        "soai_test_venv",
        "temp",
    }
)


def _require_release_payload_path(relative_path: str) -> None:
    root_name = relative_path.split("/", maxsplit=1)[0]
    if root_name in FORBIDDEN_RELEASE_ROOTS or root_name.endswith("_venv"):
        raise ValidationError(f"Complete release archive contains forbidden data: {relative_path}")
    managed_vendor_path_prefix = f"{'/'.join(MANAGED_VENDOR_RELATIVE_COMPONENTS)}/"
    managed_config_default_path = "/".join(MANAGED_CONFIG_DEFAULT_RELATIVE_COMPONENTS)
    if root_name == "data" and not (
        relative_path.startswith(managed_vendor_path_prefix)
        or relative_path == managed_config_default_path
    ):
        raise ValidationError(f"Complete release archive contains runtime data: {relative_path}")


def _validate_archive_plan(
    archive_record: ReleaseUpdateArchive,
    plan_paths: tuple[str, ...],
    plan_sizes: tuple[int, ...],
) -> None:
    expected_paths = tuple(record.path for record in archive_record.files)
    if tuple(sorted(plan_paths)) != expected_paths:
        raise ValidationError(
            f"Release archive inventory is invalid: {archive_record.name}",
            details={
                "missing": sorted(set(expected_paths).difference(plan_paths))[:20],
                "unexpected": sorted(set(plan_paths).difference(expected_paths))[:20],
            },
        )
    expected_sizes = {record.path: record.size_bytes for record in archive_record.files}
    for relative_path, file_size in zip(plan_paths, plan_sizes, strict=True):
        if expected_sizes[relative_path] != file_size:
            raise ValidationError(f"Release archive member size is invalid: {relative_path}")
        _require_release_payload_path(relative_path)


def _validate_staged_files(
    staged_root: str,
    archive_record: ReleaseUpdateArchive,
) -> None:
    for record in archive_record.files:
        file_path = os.path.join(staged_root, *record.path.split("/"))
        file_stat = require_regular_release_file(
            file_path, label=f"Release archive file {record.path}"
        )
        if file_stat.st_size != record.size_bytes:
            raise ValidationError(f"Release archive member size is invalid: {record.path}")
        if compute_file_sha256(file_path).sha256_hex != record.sha256:
            raise ValidationError(f"Release archive member hash is invalid: {record.path}")


def _validate_required_payload(
    staged_root: str,
    archive_record: ReleaseUpdateArchive,
) -> None:
    for platform_id in archive_record.platforms:
        for relative_path in required_update_paths(platform_id):
            file_path = os.path.join(staged_root, *relative_path.split("/"))
            require_regular_release_file(
                file_path, label=f"Required {platform_id} file {relative_path}"
            )


def _validate_edition_payload(
    staged_root: str,
    manifest: ReleaseManifestV1,
) -> None:
    require_internal_release_info(staged_root, manifest)
    validate_staged_frontend(
        staged_root,
        frontend_relative_path="frontend",
        expected_edition="soai-core",
        fallback_relative_paths=(),
    )
    if manifest.edition == "soai-core":
        validate_core_staged_update(staged_root, manifest)
        return
    private_root = os.path.join(staged_root, "soai_os")
    try:
        private_stat = os.stat(private_root, follow_symlinks=False)
    except OSError as exception:
        raise ValidationError(
            "SoAI OS release archive is missing its private product root."
        ) from exception
    if not stat.S_ISDIR(private_stat.st_mode) or os.path.islink(private_root):
        raise ValidationError("SoAI OS private product root must be a regular directory.")
    validate_staged_frontend(
        staged_root,
        frontend_relative_path="soai_os/frontend",
        expected_edition="soai-os",
        fallback_relative_paths=("frontend",),
    )


def verify_complete_release_archive(
    archive_path: str,
    *,
    archive_record: ReleaseUpdateArchive,
    manifest: ReleaseManifestV1,
) -> None:
    archive_stat = require_regular_release_file(archive_path, label="Complete release archive")
    if archive_stat.st_size <= 0:
        raise ValidationError("Complete release archive is empty.")
    resource_limits = default_archive_resource_limits()
    staging_path = tempfile.mkdtemp(prefix="soai-offline-release-")
    try:
        with open_binary(archive_path, mode="rb") as archive_handle:
            validate_zip_directory_budget(archive_handle, resource_limits)
            with zipfile.ZipFile(archive_handle, mode="r") as archive:
                plan = build_validated_zip_plan(
                    archive,
                    policy=ZipPlanPolicy.strict_portable_paths(
                        resource_limits=resource_limits,
                    ),
                )
                plan_paths: list[str] = []
                plan_sizes: list[int] = []
                for member in plan.members:
                    if member.is_directory:
                        raise ValidationError(
                            "Complete release archives must not contain directory entries."
                        )
                    archive_prefix = "SoAI/"
                    if not member.archive_path.startswith(archive_prefix):
                        raise ValidationError("Complete release archive root must be SoAI.")
                    relative_path = member.archive_path.removeprefix(archive_prefix)
                    if not relative_path:
                        raise ValidationError(
                            "Complete release archive contains a root file entry."
                        )
                    plan_paths.append(relative_path)
                    plan_sizes.append(member.file_size)
                _validate_archive_plan(
                    archive_record,
                    tuple(plan_paths),
                    tuple(plan_sizes),
                )
                extract_validated_zip_plan(archive, plan, staging_path)
        staged_root = os.path.join(staging_path, "SoAI")
        _validate_staged_files(staged_root, archive_record)
        _validate_required_payload(staged_root, archive_record)
        _validate_edition_payload(staged_root, manifest)
    except zipfile.BadZipFile as exception:
        raise ValidationError(
            f"Complete release archive is invalid: {archive_record.name}"
        ) from exception
    finally:
        shutil.rmtree(staging_path, ignore_errors=False)
