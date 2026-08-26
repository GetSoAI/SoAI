"""SoAI - Atomic managed install payload transaction [backend/core/bootstrap/install_payload_transaction.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
import shutil
from typing import TYPE_CHECKING

from core.bootstrap.install_payload import (
    managed_root_entries,
    validate_existing_install_edition,
    write_install_manifest,
)
from core.meta.paths import join_data_abs

__all__ = ("copy_managed_payload",)

if TYPE_CHECKING:
    from core.hardware.protocols_storage import (
        DiskSpaceReservationLeaseProtocol,
        StorageManagerProtocol,
    )

PAYLOAD_OPERATION_EXCEPTIONS: tuple[type[BaseException], ...] = (
    OSError,
    shutil.Error,
    ValueError,
)


def copy_managed_payload(
    source: str,
    target: str,
    *,
    reservation_provider: StorageManagerProtocol,
    edition: str,
    product_version: str,
    core_version: str,
) -> None:
    source_root = os.path.abspath(source)
    target_root = os.path.abspath(target)
    validate_existing_install_edition(target_root, edition)
    root_entries = managed_root_entries(edition)
    if os.path.normcase(source_root) == os.path.normcase(target_root):
        write_install_manifest(
            target_root,
            source_root,
            reservation_provider=reservation_provider,
            edition=edition,
            product_version=product_version,
            core_version=core_version,
        )
        return
    staging = os.path.join(target_root, f".soai_install_staging.{os.getpid()}")
    backup = os.path.join(target_root, f".soai_install_previous.{os.getpid()}")
    _safe_remove(target_root, staging)
    _safe_remove(target_root, backup)
    required_bytes = _managed_payload_copy_size(source_root, root_entries)
    reservation = _reserve_payload_copy(
        target_root,
        required_bytes=required_bytes,
        source_root=source_root,
        reservation_provider=reservation_provider,
    )
    try:
        with reservation.claim_write_bytes(required_bytes) as claim:
            os.makedirs(staging, exist_ok=False)
            _copy_staging_payload(source_root, staging, root_entries)
            claim.commit()
        os.makedirs(backup, exist_ok=False)
        try:
            _backup_staged_entries(target_root, backup, staging, root_entries)
            _move_staged_entries(target_root, staging, root_entries)
        except PAYLOAD_OPERATION_EXCEPTIONS:
            _restore_managed_entries(target_root, backup, root_entries)
            raise
        if os.path.isdir(backup):
            _safe_remove(target_root, backup)
    except PAYLOAD_OPERATION_EXCEPTIONS:
        _safe_remove(target_root, staging)
        raise
    finally:
        reservation.release()
    _safe_remove(target_root, staging)
    write_install_manifest(
        target_root,
        source_root,
        reservation_provider=reservation_provider,
        edition=edition,
        product_version=product_version,
        core_version=core_version,
    )


def _reserve_payload_copy(
    target_root: str,
    *,
    required_bytes: int,
    source_root: str,
    reservation_provider: StorageManagerProtocol,
) -> DiskSpaceReservationLeaseProtocol:
    return reservation_provider.reserve_disk_space(
        path=target_root,
        required_bytes=required_bytes,
        operation="core.bootstrap.install_payload.copy_managed_payload",
        details={
            "source_root": source_root,
            "target_root": target_root,
            "required_bytes": required_bytes,
        },
    )


def _managed_payload_copy_size(
    source_root: str,
    root_entries: tuple[str, ...],
) -> int:
    total_size = 0
    for entry in root_entries:
        total_size += _copy_size(os.path.join(source_root, entry))
    total_size += _copy_size(join_data_abs(source_root, "vendor"))
    return total_size


def _copy_size(source_entry: str) -> int:
    if not os.path.exists(source_entry):
        return 0
    if os.path.islink(source_entry) or os.path.isfile(source_entry):
        return os.path.getsize(source_entry)
    total_size = 0
    for directory_path, directory_names, file_names in os.walk(
        source_entry,
        followlinks=False,
    ):
        directory_names[:] = [
            directory_name
            for directory_name in directory_names
            if not os.path.islink(os.path.join(directory_path, directory_name))
        ]
        for file_name in file_names:
            total_size += os.path.getsize(os.path.join(directory_path, file_name))
    return total_size


def _copy_staging_payload(
    source: str,
    staging: str,
    root_entries: tuple[str, ...],
) -> None:
    for entry in root_entries:
        _copy_existing_entry(os.path.join(source, entry), staging)
    _copy_existing_entry(join_data_abs(source, "vendor"), join_data_abs(staging))


def _copy_existing_entry(source_entry: str, target_parent: str) -> None:
    if not os.path.exists(source_entry):
        return
    os.makedirs(target_parent, exist_ok=True)
    target_entry = os.path.join(target_parent, os.path.basename(source_entry))
    if os.path.isdir(source_entry) and not os.path.islink(source_entry):
        shutil.copytree(source_entry, target_entry, symlinks=True, copy_function=shutil.copy2)
        return
    shutil.copy2(source_entry, target_entry, follow_symlinks=False)


def _backup_staged_entries(
    target: str,
    backup: str,
    staging: str,
    root_entries: tuple[str, ...],
) -> None:
    for entry in root_entries:
        if not os.path.exists(os.path.join(staging, entry)):
            continue
        source_entry = os.path.join(target, entry)
        if os.path.exists(source_entry):
            backup_entry = os.path.join(backup, entry)
            os.makedirs(os.path.dirname(backup_entry), exist_ok=True)
            shutil.move(source_entry, backup_entry)
    vendor_source = join_data_abs(target, "vendor")
    if os.path.exists(join_data_abs(staging, "vendor")) and os.path.exists(vendor_source):
        vendor_backup_parent = join_data_abs(backup)
        os.makedirs(vendor_backup_parent, exist_ok=True)
        shutil.move(vendor_source, os.path.join(vendor_backup_parent, "vendor"))


def _move_staged_entries(
    target: str,
    staging: str,
    root_entries: tuple[str, ...],
) -> None:
    for entry in root_entries:
        source_entry = os.path.join(staging, entry)
        if os.path.exists(source_entry):
            shutil.move(source_entry, os.path.join(target, entry))
    vendor_source = join_data_abs(staging, "vendor")
    if os.path.exists(vendor_source):
        vendor_target_parent = join_data_abs(target)
        os.makedirs(vendor_target_parent, exist_ok=True)
        shutil.move(vendor_source, os.path.join(vendor_target_parent, "vendor"))


def _restore_managed_entries(
    target: str,
    backup: str,
    root_entries: tuple[str, ...],
) -> None:
    for entry in root_entries:
        target_entry = os.path.join(target, entry)
        if os.path.exists(target_entry):
            _safe_remove(target, target_entry)
        backup_entry = os.path.join(backup, entry)
        if os.path.exists(backup_entry):
            shutil.move(backup_entry, target_entry)
    target_vendor = join_data_abs(target, "vendor")
    if os.path.exists(target_vendor):
        _safe_remove(target, target_vendor)
    backup_vendor = join_data_abs(backup, "vendor")
    if os.path.exists(backup_vendor):
        target_vendor_parent = join_data_abs(target)
        os.makedirs(target_vendor_parent, exist_ok=True)
        shutil.move(backup_vendor, os.path.join(target_vendor_parent, "vendor"))


def _safe_remove(target: str, path: str) -> None:
    target_root = os.path.normcase(os.path.abspath(target))
    candidate = os.path.normcase(os.path.abspath(path))
    if candidate == target_root:
        raise ValueError(f"Refusing to remove install target root: {path}")
    if os.path.commonpath([target_root, candidate]) != target_root:
        raise ValueError(f"Refusing to remove path outside install target: {path}")
    if not os.path.exists(candidate):
        return
    if os.path.isdir(candidate) and not os.path.islink(candidate):
        shutil.rmtree(candidate)
        return
    os.unlink(candidate)
