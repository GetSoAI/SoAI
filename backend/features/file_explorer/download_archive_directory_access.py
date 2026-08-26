"""SoAI - Secure download archive directory snapshots [backend/features/file_explorer/download_archive_directory_access.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
import stat

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
    supports_managed_directory_descriptors,
)
from core.files.managed_storage_errors import FileStorageSecurityError
from core.files.windows_managed_path_handles import open_windows_managed_path_handles
from core.files.windows_reparse_points import is_windows_reparse_point

__all__ = (
    "read_download_directory_entries",
    "verify_download_directory",
)


def read_download_directory_entries(
    root_path: str,
    directory_path: str,
    *,
    expected_identity: FileIdentity,
) -> tuple[tuple[str, FileIdentity], ...]:
    try:
        if os.name == "nt":
            return _read_windows_directory_entries(
                root_path,
                directory_path,
                expected_identity=expected_identity,
                operation="file_explorer.download_archive.plan",
            )
        if supports_managed_directory_descriptors():
            with open_managed_directory_descriptor(root_path, directory_path) as descriptor:
                opened_identity = FileIdentity.from_stat(os.fstat(descriptor))
                _require_directory_identity(
                    expected_identity,
                    opened_identity,
                    operation="file_explorer.download_archive.plan",
                )
                return tuple(_read_descriptor_entries(descriptor))
        raise FileStorageSecurityError(
            "Secure managed directory access is unavailable on this platform.",
        )
    except FileStorageSecurityError as exception:
        if isinstance(exception.__cause__, FileNotFoundError):
            raise NotFoundError(
                "File explorer download directory disappeared during archive creation.",
                operation="file_explorer.download_archive.plan",
            ) from exception
        raise SecurityError(
            "File explorer download directory failed secure traversal.",
            operation="file_explorer.download_archive.plan",
        ) from exception
    except (FileNotFoundError, NotADirectoryError) as exception:
        raise NotFoundError(
            "File explorer download directory disappeared during archive creation.",
            operation="file_explorer.download_archive.plan",
        ) from exception
    except OSError as exception:
        raise StateError(
            "File explorer download directory could not be read.",
            operation="file_explorer.download_archive.plan",
            cause=exception,
        ) from exception


def verify_download_directory(
    root_path: str,
    directory_path: str,
    *,
    expected_identity: FileIdentity,
    expected_child_names: tuple[str, ...],
) -> None:
    try:
        if os.name == "nt":
            entries = _read_windows_directory_entries(
                root_path,
                directory_path,
                expected_identity=expected_identity,
                operation="file_explorer.download_archive.verify",
            )
            child_names = tuple(name for name, _identity in entries)
            identity = expected_identity
        elif supports_managed_directory_descriptors():
            with open_managed_directory_descriptor(root_path, directory_path) as descriptor:
                identity = FileIdentity.from_stat(os.fstat(descriptor))
                child_names = tuple(sorted(os.listdir(descriptor)))
        else:
            raise FileStorageSecurityError(
                "Secure managed directory access is unavailable on this platform.",
            )
    except FileStorageSecurityError as exception:
        if isinstance(exception.__cause__, FileNotFoundError):
            raise ConflictError(
                "File explorer download directory changed during archive creation.",
                operation="file_explorer.download_archive.verify",
            ) from exception
        raise SecurityError(
            "File explorer download directory failed secure traversal.",
            operation="file_explorer.download_archive.verify",
        ) from exception
    except OSError as exception:
        raise StateError(
            "File explorer download directory could not be verified.",
            operation="file_explorer.download_archive.verify",
            cause=exception,
        ) from exception
    _require_directory_identity(
        expected_identity,
        identity,
        operation="file_explorer.download_archive.verify",
    )
    if child_names != expected_child_names:
        raise ConflictError(
            "File explorer download directory changed during archive creation.",
            operation="file_explorer.download_archive.verify",
        )


def _read_descriptor_entries(descriptor: int) -> list[tuple[str, FileIdentity]]:
    entries: list[tuple[str, FileIdentity]] = []
    for name in sorted(os.listdir(descriptor)):
        entry_status = os.stat(name, dir_fd=descriptor, follow_symlinks=False)
        if stat.S_ISLNK(entry_status.st_mode) or is_windows_reparse_point(entry_status):
            _raise_link_error()
        identity = FileIdentity.from_stat(entry_status)
        _require_supported_identity(identity)
        entries.append((name, identity))
    return entries


def _read_path_entries(
    directory_entries: list[os.DirEntry[str]],
) -> list[tuple[str, FileIdentity]]:
    entries: list[tuple[str, FileIdentity]] = []
    for directory_entry in directory_entries:
        entry_status = directory_entry.stat(follow_symlinks=False)
        if stat.S_ISLNK(entry_status.st_mode) or is_windows_reparse_point(entry_status):
            _raise_link_error()
        identity = FileIdentity.from_stat(entry_status)
        _require_supported_identity(identity)
        entries.append((directory_entry.name, identity))
    return entries


def _read_windows_directory_entries(
    root_path: str,
    directory_path: str,
    *,
    expected_identity: FileIdentity,
    operation: str,
) -> tuple[tuple[str, FileIdentity], ...]:
    with open_windows_managed_path_handles(
        root_path,
        directory_path,
        require_directory=True,
    ) as opened_path:
        opened_identity = FileIdentity.from_stat(opened_path.stat_result)
        _require_directory_identity(
            expected_identity,
            opened_identity,
            operation=operation,
        )
        with os.scandir(opened_path.path) as iterator:
            directory_entries = sorted(iterator, key=lambda entry: entry.name)
        return tuple(_read_path_entries(directory_entries))


def _require_directory_identity(
    expected: FileIdentity,
    actual: FileIdentity,
    *,
    operation: str,
) -> None:
    if expected == actual and actual.is_directory:
        return
    raise ConflictError(
        "File explorer download directory changed during archive creation.",
        operation=operation,
    )


def _require_supported_identity(identity: FileIdentity) -> None:
    if identity.is_directory or identity.is_regular_file:
        return
    raise ValidationError(
        "Download archives support only regular files and directories.",
        operation="file_explorer.download_archive.plan",
    )


def _raise_link_error() -> None:
    raise SecurityError(
        "Symbolic links and filesystem junctions cannot be included in download archives.",
        operation="file_explorer.download_archive.plan",
    )
