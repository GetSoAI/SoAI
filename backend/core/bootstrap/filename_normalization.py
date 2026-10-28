"""SoAI - Durable verified installation filename normalization [backend/core/bootstrap/filename_normalization.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
import stat
from io import TextIOBase

from core.bootstrap.filename_layout import (
    PackagedFilename,
    load_packaged_filenames,
    verified_filename_bytes,
)
from core.errors.exceptions import ConflictError, StateError
from core.filesystem.atomic_write_primitives import (
    allocate_atomic_temporary_file,
    cleanup_temp_file_on_failure,
    fsync_directory,
)
from core.filesystem.atomic_writes import atomic_write_text
from core.filesystem.exclusive_rename import rename_file_without_replacement
from core.filesystem.open_files import read_regular_file_no_symlink
from core.filesystem.windows_access_control import copy_windows_discretionary_acl
from core.filesystem.windows_sharing_conflicts import remove_path_with_sharing_retry

__all__ = (
    "validate_filename_destinations",
    "normalize_installed_filenames",
    "normalized_filenames_are_usable",
    "has_pending_filename_cleanup",
)


def has_pending_filename_cleanup(root: str) -> bool:
    return any(
        os.path.lexists(os.path.join(root, record.original))
        for record in load_packaged_filenames(root)
    )


def validate_filename_destinations(
    incoming_root: str, destination_root: str, *, previous_root: str | None = None
) -> None:
    previous = {
        record.canonical: record
        for record in load_packaged_filenames(previous_root or destination_root)
    }
    for record in load_packaged_filenames(incoming_root):
        verified_filename_bytes(incoming_root, record.original, record.sha256)
        destination = os.path.join(destination_root, record.canonical)
        if not os.path.lexists(destination):
            continue
        try:
            verified_filename_bytes(destination_root, record.canonical, record.sha256)
        except StateError as exception:
            old_record = previous.get(record.canonical)
            if old_record is None:
                raise ConflictError(
                    f"Filename normalization destination contains foreign content: {record.canonical}"
                ) from exception
            verified_filename_bytes(destination_root, record.canonical, old_record.sha256)
        _validate_ownership(incoming_root, destination_root, record)


def _validate_ownership(source_root: str, destination_root: str, record: PackagedFilename) -> None:
    source = os.path.join(source_root, record.original)
    destination = os.path.join(destination_root, record.canonical)
    if not os.path.lexists(destination):
        return
    destination_stat = os.lstat(destination)
    if not stat.S_ISREG(destination_stat.st_mode) or destination_stat.st_nlink != 1:
        raise ConflictError(
            f"Filename destination is not an exclusively owned file: {record.canonical}"
        )
    if os.name != "nt" and os.path.lexists(source):
        source_stat = os.lstat(source)
        if (source_stat.st_uid, source_stat.st_gid) != (
            destination_stat.st_uid,
            destination_stat.st_gid,
        ):
            raise ConflictError(f"Filename destination ownership conflicts: {record.canonical}")


def _publish_canonical(
    root: str, record: PackagedFilename, *, previous: PackagedFilename | None = None
) -> None:
    source = os.path.join(root, record.original)
    destination = os.path.join(root, record.canonical)
    content = verified_filename_bytes(root, record.original, record.sha256)
    source_stat = os.lstat(source)
    descriptor, temporary = allocate_atomic_temporary_file(destination, file_mode=record.mode)
    try:
        with os.fdopen(descriptor, "wb") as target:
            target.write(content)
            target.flush()
            if os.name != "nt":
                os.fchown(target.fileno(), source_stat.st_uid, source_stat.st_gid)
                os.fchmod(target.fileno(), record.mode)
            os.fsync(target.fileno())
        if os.name == "nt":
            copy_windows_discretionary_acl(source, temporary)
        if os.path.lexists(destination):
            _validate_ownership(root, root, record)
            try:
                verified_filename_bytes(root, record.canonical, record.sha256)
            except StateError as exception:
                if previous is None:
                    raise ConflictError(
                        f"Filename changed before publication: {record.canonical}"
                    ) from exception
                verified_filename_bytes(root, record.canonical, previous.sha256)
            os.replace(temporary, destination)
        else:
            rename_file_without_replacement(temporary, destination)
        fsync_directory(root, strict=True)
    finally:
        cleanup_temp_file_on_failure(temporary)


def _windows_inventory_entries(
    root: str, records: tuple[PackagedFilename, ...]
) -> tuple[str, bytes, set[str]] | None:
    manifest = os.path.join(root, "installer-support", "installed-files.txt")
    if os.path.islink(os.path.dirname(manifest)):
        raise StateError("Windows installation ownership directory cannot be a symbolic link.")
    if not os.path.lexists(manifest):
        return None
    content = read_regular_file_no_symlink(manifest, max_bytes=16 * 1024 * 1024)
    entries = content.decode("utf-8-sig").splitlines()
    if len(entries) != len(set(entries)):
        raise StateError("Windows installation ownership inventory contains duplicate paths.")
    owned = set(entries)
    for record in records:
        if record.original not in owned and record.canonical not in owned:
            raise ConflictError(
                f"Windows installation does not own mapped filename: {record.original}"
            )
    return manifest, content, owned


def _reconcile_windows_inventory(root: str, records: tuple[PackagedFilename, ...]) -> None:
    inventory = _windows_inventory_entries(root, records)
    if inventory is None:
        return
    manifest, content, updated = inventory
    for record in records:
        updated.add(record.canonical)
        if os.path.lexists(os.path.join(root, record.original)):
            updated.add(record.original)
        else:
            updated.discard(record.original)
    rendered = "".join(f"{entry}\n" for entry in sorted(updated))
    if rendered.encode("utf-8") != content:

        def write_inventory(target: TextIOBase) -> None:
            target.write(rendered)

        atomic_write_text(
            manifest,
            write_inventory,
            ensure_parent=False,
            fsync=True,
            fsync_parent_directory=True,
            preserve_windows_acl=True,
        )
        fsync_directory(os.path.dirname(manifest), strict=True)


def normalize_installed_filenames(root: str, *, previous_root: str | None = None) -> None:
    records = load_packaged_filenames(root)
    if not records:
        return
    previous = (
        {record.canonical: record for record in load_packaged_filenames(previous_root)}
        if previous_root
        else {}
    )
    _windows_inventory_entries(root, records)
    for record in records:
        original_exists = os.path.lexists(os.path.join(root, record.original))
        if original_exists:
            verified_filename_bytes(root, record.original, record.sha256)
        destination = os.path.join(root, record.canonical)
        if os.path.lexists(destination):
            _validate_ownership(root, root, record)
            try:
                verified_filename_bytes(root, record.canonical, record.sha256)
            except StateError as exception:
                old_record = previous.get(record.canonical)
                if not original_exists or old_record is None:
                    raise ConflictError(
                        f"Filename destination contains foreign content: {record.canonical}"
                    ) from exception
                verified_filename_bytes(root, record.canonical, old_record.sha256)
        elif not original_exists:
            raise StateError(f"Both release-owned filenames are missing: {record.canonical}")
    for record in records:
        destination = os.path.join(root, record.canonical)
        if os.path.lexists(os.path.join(root, record.original)):
            if not os.path.lexists(destination) or (
                verified_filename_bytes(root, record.original, record.sha256)
                != read_regular_file_no_symlink(destination, max_bytes=2097152)
            ):
                _publish_canonical(root, record, previous=previous.get(record.canonical))
        verified_filename_bytes(root, record.canonical, record.sha256)
        if os.name != "nt" and stat.S_IMODE(os.stat(destination).st_mode) != record.mode:
            os.chmod(destination, record.mode)
            with open(destination, "rb") as normalized:
                os.fsync(normalized.fileno())
    _reconcile_windows_inventory(root, records)
    for record in records:
        if os.path.lexists(os.path.join(root, record.original)):
            verified_filename_bytes(root, record.original, record.sha256)
            verified_filename_bytes(root, record.canonical, record.sha256)
            remove_path_with_sharing_retry(os.path.join(root, record.original))
            fsync_directory(root, strict=True)
    _reconcile_windows_inventory(root, records)


def normalized_filenames_are_usable(root: str) -> bool:
    records = load_packaged_filenames(root)
    if not records:
        return False
    inventory = _windows_inventory_entries(root, records)
    owned = inventory[2] if inventory is not None else None
    for record in records:
        if not os.path.lexists(os.path.join(root, record.canonical)):
            return False
        verified_filename_bytes(root, record.canonical, record.sha256)
        _validate_ownership(root, root, record)
        if (
            os.name != "nt"
            and stat.S_IMODE(os.stat(os.path.join(root, record.canonical)).st_mode) != record.mode
        ):
            return False
        if owned is not None and record.canonical not in owned:
            raise StateError(f"Normalized filename ownership is incomplete: {record.canonical}")
        if os.path.lexists(os.path.join(root, record.original)):
            verified_filename_bytes(root, record.original, record.sha256)
            if owned is not None and record.original not in owned:
                raise StateError(
                    f"Pending original filename ownership is incomplete: {record.original}"
                )
    return True
