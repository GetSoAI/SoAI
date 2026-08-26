"""SoAI - Clone package source audit and capacity plan [backend/plugins/clone/clone_package_plan.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import hashlib
import io
import os
import zipfile
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass

from core.archives.zip_plan import ValidatedZipMember
from core.errors.exceptions import StateError
from core.filesystem.open_files import open_regular_binary_no_symlink
from plugins.clone_naming import derive_clone_manifest
from plugins.package_audit import inspect_open_plugin_package

__all__ = (
    "ClonePackagePlan",
    "ClonePackageSourceSnapshot",
    "build_clone_package_plan",
    "inspect_clone_package_source",
    "open_clone_package_plan",
    "require_unchanged_clone_package_source",
)

ENTRYPOINT_PATH = "__init__.py"
ZIP_END_RECORD_BYTES = 22
ZIP_LOCAL_HEADER_BYTES = 30
ZIP_CENTRAL_HEADER_BYTES = 46
ZIP64_CONSERVATIVE_MEMBER_BYTES = 64
ZIP64_END_RECORD_BYTES = 76


@dataclass(frozen=True, slots=True)
class ClonePackagePlan:
    members: tuple[ValidatedZipMember, ...]
    modified_entrypoint: bytes
    display_name: str
    required_bytes: int
    source_digest: bytes


@dataclass(frozen=True, slots=True)
class ClonePackageSourceSnapshot:
    required_bytes: int
    source_digest: bytes


def _deflate_bound(size_bytes: int) -> int:
    return size_bytes + (size_bytes >> 12) + (size_bytes >> 14) + (size_bytes >> 25) + 13


def _clone_reservation_bytes(
    members: tuple[ValidatedZipMember, ...],
    entrypoint_size: int,
    archive_comment_size: int,
) -> int:
    required_bytes = ZIP_END_RECORD_BYTES + ZIP64_END_RECORD_BYTES + archive_comment_size
    for member in members:
        source_size = (
            entrypoint_size if member.archive_path == ENTRYPOINT_PATH else member.file_size
        )
        filename_size = len(member.archive_path.encode("utf-8"))
        extra_size = len(member.zip_info.extra)
        comment_size = len(member.zip_info.comment)
        required_bytes += _deflate_bound(source_size)
        required_bytes += ZIP_LOCAL_HEADER_BYTES + filename_size + extra_size
        required_bytes += ZIP_CENTRAL_HEADER_BYTES + filename_size + extra_size + comment_size
        required_bytes += ZIP64_CONSERVATIVE_MEMBER_BYTES
    return required_bytes


def require_unchanged_clone_package_source(
    source_handle: io.BufferedIOBase,
    expected_digest: bytes,
) -> None:
    source_handle.seek(0)
    current_digest = hashlib.file_digest(source_handle, "sha256").digest()
    if current_digest != expected_digest:
        raise StateError("Clone plugin package changed during clone materialization.")


def build_clone_package_plan(
    source_handle: io.BufferedIOBase,
    source_plugin_file: str,
    target_plugin_name: str,
) -> ClonePackagePlan:
    source_handle.seek(0)
    source_digest = hashlib.file_digest(source_handle, "sha256").digest()
    source_handle.seek(0)
    source_plugin_name = os.path.basename(source_plugin_file).removesuffix(".soaiplugin")
    audit = inspect_open_plugin_package(
        source_plugin_name,
        source_plugin_file,
        source_handle,
    )

    modified_source, display_name = derive_clone_manifest(
        target_plugin_name,
        audit.entrypoint.source_text,
    )
    modified_entrypoint = modified_source.encode("utf-8")
    source_handle.seek(0)
    with zipfile.ZipFile(source_handle, "r") as source_zip:
        archive_comment_size = len(source_zip.comment)
    require_unchanged_clone_package_source(source_handle, source_digest)
    return ClonePackagePlan(
        members=audit.zip_plan.members,
        modified_entrypoint=modified_entrypoint,
        display_name=display_name,
        required_bytes=_clone_reservation_bytes(
            audit.zip_plan.members,
            len(modified_entrypoint),
            archive_comment_size,
        ),
        source_digest=source_digest,
    )


@contextmanager
def open_clone_package_plan(
    source_plugin_file: str,
    target_plugin_name: str,
) -> Generator[tuple[io.BufferedIOBase, ClonePackagePlan]]:
    with open_regular_binary_no_symlink(
        source_plugin_file,
        not_found_message="Source plugin package was not found.",
        symlink_message="Source plugin package must not be a symbolic link.",
        open_message="Source plugin package could not be opened.",
        inspect_message="Source plugin package could not be inspected.",
        regular_file_message="Source plugin package must be a regular file.",
    ) as source_handle:
        yield (
            source_handle,
            build_clone_package_plan(
                source_handle,
                source_plugin_file,
                target_plugin_name,
            ),
        )


def inspect_clone_package_source(
    source_plugin_file: str,
    target_plugin_name: str,
) -> ClonePackageSourceSnapshot:
    with open_clone_package_plan(
        source_plugin_file,
        target_plugin_name,
    ) as source:
        _source_handle, package_plan = source
        return ClonePackageSourceSnapshot(
            required_bytes=package_plan.required_bytes,
            source_digest=package_plan.source_digest,
        )
