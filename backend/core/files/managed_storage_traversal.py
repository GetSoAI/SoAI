"""SoAI - Managed storage traversal guards [backend/core/files/managed_storage_traversal.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
import stat
import sys

from core.files.managed_storage_errors import (
    FileDeletionSecurityError,
    FileStorageSecurityError,
)
from core.files.path_policy import ensure_path_within_base_lexical
from core.files.secure_open_flags import secure_read_only_open_flags
from core.files.windows_reparse_points import is_windows_reparse_point

__all__ = (
    "close_file_descriptor_stack",
    "ensure_managed_directory",
    "normalize_storage_relative_path",
    "open_directory_fd",
    "open_storage_directory_stack",
    "supports_storage_directory_descriptors",
)


def _create_directory_segment(
    parent_descriptor: int,
    segment: str,
    *,
    mode: int,
) -> None:
    try:
        os.mkdir(segment, mode=mode, dir_fd=parent_descriptor)
    except FileExistsError:
        return
    except OSError as exception:
        raise FileStorageSecurityError("Managed directory creation failed.") from exception


def ensure_managed_directory(
    storage_root: str,
    directory_path: str,
    *,
    mode: int = 0o755,
) -> str:
    root = os.path.normpath(os.path.abspath(storage_root))
    target = os.path.normpath(os.path.abspath(directory_path))
    ensure_path_within_base_lexical(
        root,
        target,
        description="Managed directory",
        error_cls=FileStorageSecurityError,
    )
    if not supports_storage_directory_descriptors():
        raise FileStorageSecurityError(
            "Secure managed directory creation is unsupported on this platform."
        )
    target_parts = [part for part in target.split(os.sep) if part]
    flags = secure_read_only_open_flags(directory=True)
    descriptor_stack = [open_directory_fd(None, os.sep, flags=flags)]
    try:
        current_descriptor = descriptor_stack[-1]
        for segment in target_parts:
            try:
                next_descriptor = open_directory_fd(
                    current_descriptor,
                    segment,
                    flags=flags,
                )
            except FileDeletionSecurityError as exception:
                if not isinstance(exception.__cause__, FileNotFoundError):
                    raise FileStorageSecurityError(
                        "Managed directory traversal failed closed."
                    ) from exception
                _create_directory_segment(
                    current_descriptor,
                    segment,
                    mode=mode,
                )
                try:
                    next_descriptor = open_directory_fd(
                        current_descriptor,
                        segment,
                        flags=flags,
                    )
                except FileDeletionSecurityError as open_exception:
                    raise FileStorageSecurityError(
                        "Created managed directory could not be verified."
                    ) from open_exception
            descriptor_stack.append(next_descriptor)
            current_descriptor = next_descriptor
    finally:
        close_file_descriptor_stack(descriptor_stack)
    return target


def normalize_storage_relative_path(storage_root: str, file_path: str) -> list[str]:
    if not file_path:
        raise FileDeletionSecurityError("Managed storage path is required.")
    abs_path = os.path.abspath(file_path)
    try:
        validated_path = ensure_path_within_base_lexical(
            storage_root,
            abs_path,
            description="File path",
            error_cls=FileDeletionSecurityError,
        )
    except FileDeletionSecurityError as exception:
        if isinstance(exception.__cause__, ValueError):
            raise FileDeletionSecurityError(
                f"File '{file_path}' is not located on the same volume as storage root '{storage_root}'.",
            ) from exception
        raise FileDeletionSecurityError(
            f"File '{file_path}' escapes managed storage '{storage_root}'.",
        ) from exception
    relative_path = os.path.relpath(validated_path, storage_root)
    parts = [part for part in relative_path.split(os.sep) if part and part != "."]
    if not parts or any(part == ".." for part in parts):
        raise FileDeletionSecurityError(
            f"File '{file_path}' resolves outside managed storage.",
        )
    return parts


def open_directory_fd(dir_fd: int | None, segment: str, *, flags: int) -> int:
    try:
        stat_before = os.stat(segment, dir_fd=dir_fd, follow_symlinks=False)
    except FileNotFoundError as exception:
        raise FileDeletionSecurityError(f"Storage segment '{segment}' is missing.") from exception
    if stat.S_ISLNK(stat_before.st_mode):
        raise FileDeletionSecurityError(
            f"Storage segment '{segment}' is a symbolic link.",
        )
    if is_windows_reparse_point(stat_before):
        raise FileDeletionSecurityError(
            f"Storage segment '{segment}' is a reparse point.",
        )
    if not stat.S_ISDIR(stat_before.st_mode):
        raise FileDeletionSecurityError(f"Storage segment '{segment}' is not a directory.")
    try:
        descriptor = os.open(segment, flags, dir_fd=dir_fd)
    except OSError as exception:
        raise FileDeletionSecurityError(
            f"Failed to open storage segment '{segment}'.",
        ) from exception
    try:
        stat_after = os.fstat(descriptor)
    except OSError as exception:
        close_file_descriptor_stack([descriptor], primary_exception=exception)
        raise FileDeletionSecurityError(
            f"Failed to inspect opened storage segment '{segment}'.",
        ) from exception
    if is_windows_reparse_point(stat_after):
        error = FileDeletionSecurityError(
            f"Storage segment '{segment}' is a reparse point.",
        )
        close_file_descriptor_stack([descriptor], primary_exception=error)
        raise error
    if stat_before.st_dev == stat_after.st_dev and stat_before.st_ino == stat_after.st_ino:
        return descriptor
    error = FileDeletionSecurityError(
        f"Storage segment '{segment}' was replaced during traversal.",
    )
    close_file_descriptor_stack([descriptor], primary_exception=error)
    raise error


def supports_storage_directory_descriptors() -> bool:
    try:
        secure_read_only_open_flags(directory=True)
    except FileStorageSecurityError:
        return False
    return (
        os.open in os.supports_dir_fd
        and os.stat in os.supports_dir_fd
        and os.stat in os.supports_follow_symlinks
    )


def close_file_descriptor_stack(
    file_descriptor_stack: list[int],
    *,
    primary_exception: BaseException | None = None,
) -> None:
    first_close_exception: OSError | None = None
    while file_descriptor_stack:
        file_descriptor = file_descriptor_stack.pop()
        try:
            os.close(file_descriptor)
        except OSError as close_exception:
            if first_close_exception is None:
                first_close_exception = close_exception
    if first_close_exception is None:
        return
    active_exception = primary_exception or sys.exception()
    if active_exception is not None:
        active_exception.add_note(
            f"Failed to close managed storage descriptor: {first_close_exception}",
        )
        return
    raise FileDeletionSecurityError(
        "Failed to close managed storage descriptor.",
    ) from first_close_exception


def open_storage_directory_stack(
    storage_root: str,
    directory_parts: list[str],
    *,
    missing_segment_returns_none: bool,
) -> list[int] | None:
    base_flags = secure_read_only_open_flags(directory=True)
    file_descriptor_stack: list[int] = []
    completed = False
    try:
        try:
            current_descriptor = open_directory_fd(None, storage_root, flags=base_flags)
        except FileDeletionSecurityError as exception:
            if missing_segment_returns_none and isinstance(
                exception.__cause__,
                FileNotFoundError,
            ):
                completed = True
                return None
            raise
        file_descriptor_stack.append(current_descriptor)
        for segment in directory_parts:
            try:
                next_descriptor = open_directory_fd(current_descriptor, segment, flags=base_flags)
            except FileDeletionSecurityError as exception:
                if missing_segment_returns_none and isinstance(
                    exception.__cause__,
                    FileNotFoundError,
                ):
                    close_file_descriptor_stack(file_descriptor_stack)
                    completed = True
                    return None
                raise
            file_descriptor_stack.append(next_descriptor)
            current_descriptor = next_descriptor
        completed = True
        return file_descriptor_stack
    finally:
        if not completed:
            close_file_descriptor_stack(file_descriptor_stack)
