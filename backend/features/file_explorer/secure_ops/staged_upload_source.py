"""SoAI - Pinned staged upload source ownership [backend/features/file_explorer/secure_ops/staged_upload_source.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
import stat
from dataclasses import dataclass

from core.errors.exceptions import SecurityError, StateError, ValidationError
from core.files.managed_storage_traversal import close_file_descriptor_stack
from core.files.secure_open_flags import secure_read_only_open_flags
from core.filesystem.descriptor_io import open_descriptor
from features.file_explorer.secure_ops.link_checks import is_no_symlink_open_error

__all__ = (
    "OpenedStagedSource",
    "close_staged_source",
    "open_staged_source",
    "remove_staged_source",
    "same_staged_file_identity",
)


@dataclass(frozen=True, slots=True)
class OpenedStagedSource:
    file_descriptor: int
    parent_descriptor: int
    filename: str
    stat_result: os.stat_result


def open_staged_source(source_path: str, *, expected_size: int) -> OpenedStagedSource:
    source_parent = os.path.dirname(source_path)
    source_name = os.path.basename(source_path)
    parent_descriptor = open_descriptor(source_parent, secure_read_only_open_flags(directory=True))
    try:
        file_descriptor = open_descriptor(
            source_name,
            secure_read_only_open_flags(directory=False),
            dir_fd=parent_descriptor,
        )
    except OSError as exception:
        close_file_descriptor_stack([parent_descriptor], primary_exception=exception)
        if is_no_symlink_open_error(exception):
            raise SecurityError("Staged upload source cannot be a symbolic link.") from exception
        if isinstance(exception, FileNotFoundError):
            raise StateError("Staged upload source is no longer available.") from exception
        raise
    accepted = False
    try:
        source_stat = os.fstat(file_descriptor)
        if not stat.S_ISREG(source_stat.st_mode):
            raise ValidationError("Staged upload source must be a regular file.")
        if source_stat.st_size != expected_size:
            raise StateError("Staged upload source size changed before commit.")
        parent_stat = os.fstat(parent_descriptor)
        if parent_stat.st_uid != os.geteuid() or stat.S_IMODE(parent_stat.st_mode) & 0o022:
            raise SecurityError("Staged upload requires a protected private namespace.")
        accepted = True
    finally:
        if not accepted:
            _close_source_descriptors(file_descriptor, parent_descriptor)
    return OpenedStagedSource(file_descriptor, parent_descriptor, source_name, source_stat)


def close_staged_source(source: OpenedStagedSource) -> None:
    _close_source_descriptors(source.file_descriptor, source.parent_descriptor)


def _close_source_descriptors(file_descriptor: int, parent_descriptor: int) -> None:
    close_file_descriptor_stack([parent_descriptor, file_descriptor])


def remove_staged_source(source: OpenedStagedSource) -> None:
    current_stat = os.stat(
        source.filename,
        dir_fd=source.parent_descriptor,
        follow_symlinks=False,
    )
    if not same_staged_file_identity(current_stat, source.stat_result):
        raise StateError("Staged upload source changed during commit.")
    os.unlink(source.filename, dir_fd=source.parent_descriptor)


def same_staged_file_identity(first: os.stat_result, second: os.stat_result) -> bool:
    return (
        first.st_dev == second.st_dev
        and first.st_ino == second.st_ino
        and first.st_size == second.st_size
    )
