"""SoAI - Deterministic ZIP plugin package cloning [backend/plugins/clone_plugin_file.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import io
import os
import shutil
import zipfile
from typing import TYPE_CHECKING

from core.archives.zip_plan import ValidatedZipMember
from core.concurrency.cancellation_cleanup import (
    current_task_has_pending_cancellation,
    uncancel_and_wait,
)
from core.errors.exceptions import StateError, ValidationError
from core.filesystem.atomic_binary_writes import atomic_write_binary
from core.hardware.reservation_claims import claim_reserved_write
from plugins.clone.clone_package_plan import (
    ENTRYPOINT_PATH,
    inspect_clone_package_source,
    open_clone_package_plan,
    require_unchanged_clone_package_source,
)
from plugins.fs_permissions import ensure_single_path_permissions

if TYPE_CHECKING:
    from core.hardware.protocols_storage import (
        DiskSpaceReservationLeaseProtocol,
        StorageManagerProtocol,
    )

__all__ = (
    "clone_plugin_file",
    "estimate_clone_package_bytes",
)


def _clone_member_info(member: ValidatedZipMember) -> zipfile.ZipInfo:
    source = member.zip_info
    cloned = zipfile.ZipInfo(member.archive_path, date_time=source.date_time)
    cloned.comment = source.comment
    cloned.extra = source.extra
    cloned.create_system = source.create_system
    cloned.create_version = source.create_version
    cloned.extract_version = source.extract_version
    cloned.external_attr = source.external_attr
    cloned.internal_attr = source.internal_attr
    cloned.flag_bits = source.flag_bits & ~0x1
    cloned.compress_type = zipfile.ZIP_DEFLATED
    return cloned


def _write_clone_archive(
    target_handle: io.BufferedIOBase,
    source_zip: zipfile.ZipFile,
    members: tuple[ValidatedZipMember, ...],
    modified_entrypoint: bytes,
) -> None:
    with zipfile.ZipFile(
        target_handle,
        mode="w",
        compression=zipfile.ZIP_DEFLATED,
        allowZip64=True,
        compresslevel=9,
    ) as target_zip:
        target_zip.comment = source_zip.comment
        for member in sorted(members, key=lambda item: item.archive_path):
            cloned_info = _clone_member_info(member)
            if member.is_directory:
                target_zip.writestr(cloned_info, b"")
                continue
            if member.archive_path == ENTRYPOINT_PATH:
                target_zip.writestr(cloned_info, modified_entrypoint)
                continue
            with source_zip.open(member.zip_info, "r") as source_handle:
                with target_zip.open(cloned_info, "w", force_zip64=True) as target_member:
                    shutil.copyfileobj(source_handle, target_member, 1024 * 1024)


def _clone_package_snapshot(
    source_plugin_file: str,
    target_plugin_file: str,
    target_plugin_name: str,
    storage_manager: StorageManagerProtocol,
    aggregate_reservation: DiskSpaceReservationLeaseProtocol | None = None,
    expected_required_bytes: int | None = None,
    expected_source_digest: bytes | None = None,
) -> str:
    try:
        with open_clone_package_plan(
            source_plugin_file,
            target_plugin_name,
        ) as source:
            source_handle, package_plan = source
            if (
                expected_required_bytes is not None
                and package_plan.required_bytes != expected_required_bytes
            ):
                raise StateError("Clone plugin package changed after capacity planning.")
            if (
                expected_source_digest is not None
                and package_plan.source_digest != expected_source_digest
            ):
                raise StateError("Clone plugin package changed after capacity planning.")
            with zipfile.ZipFile(source_handle, "r") as source_zip:
                owned_reservation = aggregate_reservation is None
                reservation = aggregate_reservation or storage_manager.reserve_disk_space(
                    path=os.path.dirname(target_plugin_file),
                    required_bytes=package_plan.required_bytes,
                    operation="plugin_clone.clone_plugin_file",
                    details={"required_bytes": package_plan.required_bytes},
                )
                try:
                    with claim_reserved_write(
                        reservation,
                        size_bytes=package_plan.required_bytes,
                    ):

                        def writer(target_handle: io.BufferedIOBase) -> None:
                            _write_clone_archive(
                                target_handle,
                                source_zip,
                                package_plan.members,
                                package_plan.modified_entrypoint,
                            )
                            require_unchanged_clone_package_source(
                                source_handle,
                                package_plan.source_digest,
                            )

                        atomic_write_binary(
                            target_plugin_file,
                            writer,
                            file_mode=0o644,
                            fsync_parent_directory=True,
                            exclusive=True,
                        )
                finally:
                    if owned_reservation:
                        reservation.release()
    except (zipfile.BadZipFile, zipfile.LargeZipFile) as exception:
        raise ValidationError("Source plugin package must be a valid ZIP archive.") from exception
    return package_plan.display_name


def estimate_clone_package_bytes(
    source_plugin_file: str,
    target_plugin_name: str,
) -> int:
    return inspect_clone_package_source(
        source_plugin_file,
        target_plugin_name,
    ).required_bytes


async def clone_plugin_file(
    *,
    storage_manager: StorageManagerProtocol,
    source_plugin_file: str,
    target_plugin_file: str,
    target_plugin_name: str,
    aggregate_reservation: DiskSpaceReservationLeaseProtocol | None = None,
    expected_required_bytes: int | None = None,
    expected_source_digest: bytes | None = None,
) -> str:
    display_name = await uncancel_and_wait(
        asyncio.to_thread(
            _clone_package_snapshot,
            source_plugin_file,
            target_plugin_file,
            target_plugin_name,
            storage_manager,
            aggregate_reservation,
            expected_required_bytes,
            expected_source_digest,
        )
    )
    if current_task_has_pending_cancellation():
        raise asyncio.CancelledError
    await uncancel_and_wait(ensure_single_path_permissions(target_plugin_file))
    if current_task_has_pending_cancellation():
        raise asyncio.CancelledError
    return display_name
