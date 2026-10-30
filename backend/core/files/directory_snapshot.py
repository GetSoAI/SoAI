"""SoAI - Secure bounded directory snapshots [backend/core/files/directory_snapshot.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
import stat
from collections.abc import Callable, Iterator
from threading import Event

from core.concurrency.cancellation import check_cancellation_deadline
from core.concurrency.deadlines import MonotonicDeadline
from core.errors.exceptions import (
    ConflictError,
    NotFoundError,
    SecurityError,
    StateError,
    ValidationError,
)
from core.files.file_identity import FileIdentity
from core.files.managed_path_access import (
    open_managed_directory_descriptor,
    stat_managed_path,
    supports_managed_directory_descriptors,
)
from core.files.managed_storage_errors import FileStorageSecurityError
from core.files.windows_managed_path_handles import open_windows_managed_path_handles
from core.files.windows_reparse_points import is_windows_reparse_point

__all__ = ("read_directory_entries", "verify_directory_snapshot")


def read_directory_entries(
    root_path: str,
    directory_path: str,
    *,
    expected_identity: FileIdentity,
    admit_entry: Callable[[str, FileIdentity], None],
    cancellation_event: Event,
    deadline: MonotonicDeadline | None = None,
    stable_object_only: bool = False,
    concurrent_leaf_read: bool = False,
    operation: str = "file_explorer.download_archive.plan",
) -> tuple[tuple[str, FileIdentity], ...]:
    check_cancellation_deadline(cancellation_event, deadline, operation=operation)
    entries: list[tuple[str, FileIdentity]] = []
    try:
        for name, identity in _iterate_directory(
            root_path,
            directory_path,
            expected_identity=expected_identity,
            stable_object_only=stable_object_only,
            concurrent_leaf_read=concurrent_leaf_read,
            operation=operation,
            cancellation_event=cancellation_event,
            deadline=deadline,
        ):
            check_cancellation_deadline(cancellation_event, deadline, operation=operation)
            admit_entry(name, identity)
            entries.append((name, identity))
        check_cancellation_deadline(cancellation_event, deadline, operation=operation)
        return tuple(sorted(entries))
    except FileStorageSecurityError as exception:
        if isinstance(exception.__cause__, FileNotFoundError):
            raise NotFoundError(
                "File explorer download directory disappeared during archive creation.",
                operation=operation,
            ) from exception
        raise SecurityError(
            "File explorer download directory failed secure traversal.",
            operation=operation,
        ) from exception
    except (FileNotFoundError, NotADirectoryError) as exception:
        raise NotFoundError(
            "File explorer download directory disappeared during archive creation.",
            operation=operation,
        ) from exception
    except OSError as exception:
        raise StateError(
            "File explorer download directory could not be read.",
            operation=operation,
            cause=exception,
        ) from exception


def verify_directory_snapshot(
    root_path: str,
    directory_path: str,
    *,
    expected_identity: FileIdentity,
    expected_child_names: tuple[str, ...],
    cancellation_event: Event,
    deadline: MonotonicDeadline | None = None,
    operation: str = "file_explorer.download_archive.verify",
) -> None:
    names: list[str] = []
    try:
        for name, _identity in _iterate_directory(
            root_path,
            directory_path,
            expected_identity=expected_identity,
            stable_object_only=False,
            concurrent_leaf_read=False,
            operation=operation,
            cancellation_event=cancellation_event,
            deadline=deadline,
        ):
            check_cancellation_deadline(cancellation_event, deadline, operation=operation)
            if len(names) >= len(expected_child_names):
                raise ConflictError(
                    "File explorer download directory changed during archive creation.",
                    operation=operation,
                )
            names.append(name)
    except FileStorageSecurityError as exception:
        if isinstance(exception.__cause__, FileNotFoundError):
            raise ConflictError(
                "File explorer download directory changed during archive creation.",
                operation=operation,
            ) from exception
        raise SecurityError(
            "File explorer download directory failed secure traversal.", operation=operation
        ) from exception
    except OSError as exception:
        raise StateError(
            "File explorer download directory could not be verified.",
            operation=operation,
            cause=exception,
        ) from exception
    if tuple(sorted(names)) != expected_child_names:
        raise ConflictError(
            "File explorer download directory changed during archive creation.", operation=operation
        )


def _iterate_directory(
    root_path: str,
    directory_path: str,
    *,
    expected_identity: FileIdentity,
    stable_object_only: bool,
    concurrent_leaf_read: bool,
    operation: str,
    cancellation_event: Event,
    deadline: MonotonicDeadline | None,
) -> Iterator[tuple[str, FileIdentity]]:
    if os.name == "nt":
        with open_windows_managed_path_handles(
            root_path, directory_path, require_directory=True
        ) as opened_path:
            _require_directory_identity(
                expected_identity,
                FileIdentity.from_stat(opened_path.stat_result),
                stable_object_only=stable_object_only,
                operation=operation,
            )
            with os.scandir(opened_path.path) as iterator:
                for entry in iterator:
                    check_cancellation_deadline(cancellation_event, deadline, operation=operation)
                    identity = _entry_identity(os.stat(entry.path, follow_symlinks=False))
                    if identity.is_regular_file:
                        identity = _entry_identity(
                            stat_managed_path(
                                root_path,
                                entry.path,
                                file_descriptor_snapshot=True,
                                concurrent_leaf_read=concurrent_leaf_read,
                            )
                        )
                    yield entry.name, identity
            _require_directory_identity(
                expected_identity,
                FileIdentity.from_stat(os.stat(opened_path.path, follow_symlinks=False)),
                stable_object_only=stable_object_only,
                operation=operation,
            )
    elif supports_managed_directory_descriptors():
        with open_managed_directory_descriptor(root_path, directory_path) as descriptor:
            _require_directory_identity(
                expected_identity,
                FileIdentity.from_stat(os.fstat(descriptor)),
                stable_object_only=stable_object_only,
                operation=operation,
            )
            with os.scandir(descriptor) as iterator:
                for entry in iterator:
                    check_cancellation_deadline(cancellation_event, deadline, operation=operation)
                    yield entry.name, _entry_identity(entry.stat(follow_symlinks=False))
            _require_directory_identity(
                expected_identity,
                FileIdentity.from_stat(os.fstat(descriptor)),
                stable_object_only=stable_object_only,
                operation=operation,
            )
    else:
        raise FileStorageSecurityError(
            "Secure managed directory access is unavailable on this platform."
        )


def _entry_identity(entry_status: os.stat_result) -> FileIdentity:
    if stat.S_ISLNK(entry_status.st_mode) or is_windows_reparse_point(entry_status):
        raise SecurityError(
            "Symbolic links and filesystem junctions cannot be included in download archives.",
            operation="file_explorer.download_archive.plan",
        )
    identity = FileIdentity.from_stat(entry_status)
    if not identity.is_directory and not identity.is_regular_file:
        raise ValidationError(
            "Download archives support only regular files and directories.",
            details={"type": "unsupported_entry"},
            operation="file_explorer.download_archive.plan",
        )
    return identity


def _require_directory_identity(
    expected: FileIdentity, actual: FileIdentity, *, stable_object_only: bool, operation: str
) -> None:
    matches = (
        expected.matches_file_object(actual)
        if stable_object_only
        else expected.matches_descriptor_snapshot(actual)
    )
    if not matches or not actual.is_directory:
        raise ConflictError(
            "File explorer download directory changed during archive creation.", operation=operation
        )
