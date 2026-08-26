"""SoAI - Secure clone model-tree copying [backend/plugins/clone_filesystem.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
import stat
from typing import TYPE_CHECKING

from core.config.byte_sizes import MIB_BYTES
from core.errors.exceptions import StateError, ValidationError
from core.files.content_hashing import hash_descriptor_content
from core.files.secure_open_flags import secure_read_only_open_flags
from core.hardware.reserved_writes import write_reserved_bytes
from plugins.clone.clone_source_manifest import (
    CloneSourceEntry,
    build_clone_source_snapshot,
    scan_clone_source,
)

if TYPE_CHECKING:
    from core.hardware.protocols_storage import (
        DiskSpaceReservationLeaseProtocol,
        StorageManagerProtocol,
    )

__all__ = ("copy_model_tree",)

COPY_CHUNK_BYTES = MIB_BYTES


def _create_directory_component(parent_handle: int, directory_name: str) -> None:
    try:
        os.mkdir(directory_name, mode=0o750, dir_fd=parent_handle)
    except FileExistsError as exception:
        existing = os.stat(directory_name, dir_fd=parent_handle, follow_symlinks=False)
        if not stat.S_ISDIR(existing.st_mode):
            raise StateError(
                f"Clone model destination component is not a directory: {directory_name}"
            ) from exception


def _require_unchanged(handle: int, source: CloneSourceEntry) -> None:
    current = os.fstat(handle)
    expected_type_matches = (
        stat.S_ISDIR(current.st_mode)
        if source.entry_type == "directory"
        else stat.S_ISREG(current.st_mode)
    )
    identity_matches = current.st_dev == source.device and current.st_ino == source.inode
    size_matches = source.entry_type != "file" or current.st_size == source.size_bytes
    timestamp_matches = current.st_mtime_ns == source.modified_ns
    if (
        not expected_type_matches
        or not identity_matches
        or not size_matches
        or not timestamp_matches
    ):
        raise StateError(f"Clone model source changed during copy: {source.relative_path}")


def _open_parent_directory(
    root_handle: int,
    relative_path: str,
    *,
    create: bool,
) -> tuple[int, str]:
    parts = relative_path.split(os.sep)
    parent_handle = os.dup(root_handle)
    parent_opened = False
    try:
        for directory_name in parts[:-1]:
            if create:
                _create_directory_component(parent_handle, directory_name)
            following_handle = os.open(
                directory_name,
                secure_read_only_open_flags(directory=True),
                dir_fd=parent_handle,
            )
            os.close(parent_handle)
            parent_handle = following_handle
        parent_opened = True
        return (parent_handle, parts[-1])
    finally:
        if not parent_opened:
            os.close(parent_handle)


def _copy_source_file(
    source_root_handle: int,
    destination_root_handle: int,
    source: CloneSourceEntry,
    reservation: DiskSpaceReservationLeaseProtocol,
) -> None:
    source_parent, source_name = _open_parent_directory(
        source_root_handle,
        source.relative_path,
        create=False,
    )
    try:
        destination_parent, destination_name = _open_parent_directory(
            destination_root_handle,
            source.relative_path,
            create=True,
        )
        try:
            source_handle = os.open(
                source_name,
                secure_read_only_open_flags(directory=False),
                dir_fd=source_parent,
            )
            try:
                _require_unchanged(source_handle, source)
                destination_handle = os.open(
                    destination_name,
                    os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                    0o600,
                    dir_fd=destination_parent,
                )
                copied_bytes = 0
                with os.fdopen(destination_handle, "wb", closefd=True) as destination_stream:
                    while True:
                        chunk = os.read(source_handle, COPY_CHUNK_BYTES)
                        if not chunk:
                            break
                        copied_bytes += len(chunk)
                        write_reserved_bytes(destination_stream, chunk, reservation=reservation)
                    destination_stream.flush()
                    os.fsync(destination_stream.fileno())
                _require_unchanged(source_handle, source)
                source_content = hash_descriptor_content(source_handle)
                expected_digest = source.content_digest.hex() if source.content_digest else None
                if (
                    source_content.size_bytes != source.size_bytes
                    or source_content.sha256_hex != expected_digest
                ):
                    raise StateError(
                        f"Clone model source changed during copy: {source.relative_path}"
                    )
                if copied_bytes != source.size_bytes:
                    raise StateError(f"Clone model copy was incomplete: {source.relative_path}")
            finally:
                os.close(source_handle)
            destination_handle = os.open(
                destination_name,
                secure_read_only_open_flags(directory=False),
                dir_fd=destination_parent,
            )
            try:
                destination_content = hash_descriptor_content(destination_handle)
            finally:
                os.close(destination_handle)
            if destination_content != source_content:
                raise StateError(f"Clone model copy verification failed: {source.relative_path}")
            os.chmod(
                destination_name,
                0o640,
                dir_fd=destination_parent,
                follow_symlinks=False,
            )
        finally:
            os.close(destination_parent)
    finally:
        os.close(source_parent)


def _copy_source_directory(
    source_root_handle: int,
    destination_root_handle: int,
    source: CloneSourceEntry,
) -> None:
    source_parent, source_name = _open_parent_directory(
        source_root_handle,
        source.relative_path,
        create=False,
    )
    try:
        source_handle = os.open(
            source_name,
            secure_read_only_open_flags(directory=True),
            dir_fd=source_parent,
        )
        try:
            _require_unchanged(source_handle, source)
        finally:
            os.close(source_handle)
    finally:
        os.close(source_parent)
    destination_parent, destination_name = _open_parent_directory(
        destination_root_handle,
        source.relative_path,
        create=False,
    )
    try:
        os.mkdir(destination_name, mode=0o750, dir_fd=destination_parent)
    finally:
        os.close(destination_parent)


def copy_model_tree(
    source: str,
    destination: str,
    storage_manager: StorageManagerProtocol,
    aggregate_reservation: DiskSpaceReservationLeaseProtocol | None = None,
    expected_required_bytes: int | None = None,
    expected_source_digest: bytes | None = None,
) -> None:
    if os.name == "nt":
        raise StateError("Secure clone copying requires directory-relative no-follow support.")
    source_handle = os.open(
        source,
        secure_read_only_open_flags(directory=True),
    )
    try:
        source_stat = os.fstat(source_handle)
        if not stat.S_ISDIR(source_stat.st_mode):
            raise ValidationError("Clone model source must be a regular directory.")
        manifest = scan_clone_source(source_handle)
        source_snapshot = build_clone_source_snapshot(manifest)
        required_bytes = source_snapshot.required_bytes
        if expected_required_bytes is not None and required_bytes != expected_required_bytes:
            raise StateError("Clone model source changed after capacity planning.")
        if (
            expected_source_digest is not None
            and source_snapshot.source_digest != expected_source_digest
        ):
            raise StateError("Clone model source changed after capacity planning.")
        os.mkdir(destination, mode=0o750)
        destination_handle = os.open(
            destination,
            secure_read_only_open_flags(directory=True),
        )
        try:
            owned_reservation = aggregate_reservation is None
            reservation = aggregate_reservation or storage_manager.reserve_disk_space(
                path=os.path.dirname(destination),
                required_bytes=required_bytes,
                operation="plugin_clone.copy_models",
                details={"required_bytes": required_bytes},
            )
            try:
                for entry in manifest:
                    if entry.entry_type == "directory":
                        _copy_source_directory(
                            source_handle,
                            destination_handle,
                            entry,
                        )
                        continue
                    _copy_source_file(
                        source_handle,
                        destination_handle,
                        entry,
                        reservation,
                    )
            finally:
                if owned_reservation:
                    reservation.release()
            if scan_clone_source(source_handle) != manifest:
                raise StateError("Clone model source changed during copy.")
            os.fsync(destination_handle)
        finally:
            os.close(destination_handle)
    finally:
        os.close(source_handle)
