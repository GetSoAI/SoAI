"""SoAI - Recoverable managed runtime directory publication [backend/core/bootstrap/runtime_directory_publication.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
import stat
import uuid
from typing import TYPE_CHECKING

from core.errors.exceptions import StateError
from core.files.windows_reparse_points import is_windows_reparse_point
from core.filesystem.windows_sharing_conflicts import (
    remove_path_with_sharing_retry,
    replace_with_sharing_retry,
)
from core.logging.trace import get_logger

if TYPE_CHECKING:
    from collections.abc import Callable

    type RuntimeDirectoryValidator = Callable[[str], None]

__all__ = (
    "publish_runtime_directory",
    "recover_runtime_directory_publication",
)

LOGGER_NAME = "SoAI.core.bootstrap.runtime_directory_publication"


def recover_runtime_directory_publication(
    install_directory: str,
    validate_directory: RuntimeDirectoryValidator,
) -> None:
    backups = _owned_directories(install_directory, purpose="backup")
    failed_directories = _owned_directories(install_directory, purpose="failed")
    install_exists = os.path.lexists(install_directory)
    if install_exists:
        _require_directory(install_directory, "Managed runtime installation")
        try:
            validate_directory(install_directory)
        except (OSError, StateError, ValueError) as validation_exception:
            if len(backups) == 1:
                _restore_retained_backup(
                    install_directory,
                    backups[0],
                )
            elif len(backups) > 1:
                raise StateError(
                    "Managed runtime recovery has ambiguous retained backups."
                ) from validation_exception
            _remove_retained_directories(
                install_directory,
                failed_directories,
                purpose="failed",
            )
            return
        _remove_retained_directories(install_directory, backups, purpose="backup")
        _remove_retained_directories(
            install_directory,
            failed_directories,
            purpose="failed",
        )
        return
    if len(backups) > 1:
        raise StateError("Managed runtime recovery has ambiguous retained backups.")
    if not backups:
        _remove_retained_directories(
            install_directory,
            failed_directories,
            purpose="failed",
        )
        return
    backup_directory = backups[0]
    try:
        replace_with_sharing_retry(backup_directory, install_directory)
    except (OSError, StateError) as exception:
        raise StateError("Managed runtime backup restoration failed.") from exception
    _remove_retained_directories(
        install_directory,
        failed_directories,
        purpose="failed",
    )


def publish_runtime_directory(
    staging_directory: str,
    install_directory: str,
    validate_directory: RuntimeDirectoryValidator,
) -> None:
    _require_directory(staging_directory, "Managed runtime staging directory")
    validate_directory(staging_directory)
    recover_runtime_directory_publication(install_directory, validate_directory)
    backup_directory = _new_owned_directory(install_directory, purpose="backup")
    failed_directory = _new_owned_directory(install_directory, purpose="failed")
    moved_existing = False
    promoted = False
    try:
        if os.path.lexists(install_directory):
            _require_directory(install_directory, "Managed runtime installation")
            replace_with_sharing_retry(install_directory, backup_directory)
            moved_existing = True
        replace_with_sharing_retry(staging_directory, install_directory)
        promoted = True
        validate_directory(install_directory)
    except (OSError, StateError, ValueError) as exception:
        if promoted and os.path.lexists(install_directory):
            try:
                replace_with_sharing_retry(install_directory, failed_directory)
            except (OSError, StateError) as quarantine_exception:
                raise StateError(
                    "Managed runtime promotion failed and could not be retained for recovery."
                ) from quarantine_exception
        if moved_existing:
            try:
                replace_with_sharing_retry(backup_directory, install_directory)
            except (OSError, StateError) as restoration_exception:
                raise StateError(
                    "Managed runtime promotion failed and its backup was retained."
                ) from restoration_exception
        if os.path.lexists(failed_directory):
            _remove_owned_directory(install_directory, failed_directory, purpose="failed")
        raise StateError("Managed runtime directory publication failed.") from exception
    if moved_existing:
        try:
            _remove_owned_directory(install_directory, backup_directory, purpose="backup")
        except StateError as exception:
            get_logger(LOGGER_NAME).warning(
                "Managed runtime backup cleanup is pending: %s", exception
            )


def _restore_retained_backup(
    install_directory: str,
    backup_directory: str,
) -> None:
    failed_directory = _new_owned_directory(install_directory, purpose="failed")
    try:
        replace_with_sharing_retry(install_directory, failed_directory)
        try:
            replace_with_sharing_retry(backup_directory, install_directory)
        except (OSError, StateError):
            replace_with_sharing_retry(failed_directory, install_directory)
            raise
    except (OSError, StateError) as exception:
        raise StateError(
            "Managed runtime recovery could not restore its retained backup."
        ) from exception
    _remove_owned_directory(install_directory, failed_directory, purpose="failed")


def _remove_retained_directories(
    install_directory: str,
    retained_directories: tuple[str, ...],
    *,
    purpose: str,
) -> None:
    for retained_directory in retained_directories:
        _remove_owned_directory(
            install_directory,
            retained_directory,
            purpose=purpose,
        )


def _owned_directories(install_directory: str, *, purpose: str) -> tuple[str, ...]:
    parent_directory = os.path.dirname(install_directory)
    install_name = os.path.basename(install_directory)
    prefix = f".{install_name}.soai-{purpose}."
    if not os.path.isdir(parent_directory):
        return ()
    owned: list[str] = []
    try:
        with os.scandir(parent_directory) as entries:
            for entry in entries:
                if not entry.name.startswith(prefix):
                    continue
                suffix = entry.name[len(prefix) :]
                if len(suffix) != 32 or any(
                    character not in "0123456789abcdef" for character in suffix
                ):
                    continue
                _require_directory(entry.path, "Managed runtime retained directory")
                owned.append(entry.path)
    except OSError as exception:
        raise StateError(
            "Managed runtime retained directories could not be inspected."
        ) from exception
    return tuple(sorted(owned))


def _new_owned_directory(install_directory: str, *, purpose: str) -> str:
    parent_directory = os.path.dirname(install_directory)
    install_name = os.path.basename(install_directory)
    return os.path.join(
        parent_directory,
        f".{install_name}.soai-{purpose}.{uuid.uuid4().hex}",
    )


def _remove_owned_directory(
    install_directory: str,
    owned_directory: str,
    *,
    purpose: str,
) -> None:
    expected_parent = os.path.dirname(os.path.abspath(install_directory))
    resolved_directory = os.path.abspath(owned_directory)
    expected_prefix = f".{os.path.basename(install_directory)}.soai-{purpose}."
    if os.path.dirname(resolved_directory) != expected_parent or not os.path.basename(
        resolved_directory
    ).startswith(expected_prefix):
        raise StateError("Managed runtime residue ownership validation failed.")
    _require_directory(resolved_directory, "Managed runtime retained directory")
    try:
        remove_path_with_sharing_retry(resolved_directory)
    except (OSError, StateError) as exception:
        raise StateError("Managed runtime retained directory could not be removed.") from exception


def _require_directory(path: str, label: str) -> None:
    try:
        status = os.lstat(path)
    except OSError as exception:
        raise StateError(f"{label} is unavailable.") from exception
    if (
        not stat.S_ISDIR(status.st_mode)
        or stat.S_ISLNK(status.st_mode)
        or is_windows_reparse_point(status)
    ):
        raise StateError(f"{label} has an unsafe filesystem type.")
