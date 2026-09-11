"""SoAI - Native host filesystem root discovery and directory location [backend/core/files/host_filesystem_roots.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
import sys
from dataclasses import dataclass

from core.errors.exception_logging import log_handled_exception
from core.errors.exceptions import ValidationError
from core.files.workspace_path import resolve_existing_workspace_directory
from core.logging.trace import get_logger

__all__ = (
    "HostDirectoryLocation",
    "default_host_filesystem_root",
    "enumerate_host_filesystem_roots",
    "locate_existing_host_directory",
    "resolve_host_filesystem_root",
)

LOGGER_NAME = "SoAI.core.files.host_filesystem_roots"
OPERATION_HOST_FILESYSTEM_ROOT_DISCOVERY = "core.files.host_filesystem_roots.discovery"


@dataclass(frozen=True, slots=True)
class HostDirectoryLocation:
    root_path: str
    absolute_path: str


def listdrives() -> list[str]:
    if sys.platform == "win32":
        return os.listdrives()
    return [os.sep]


def _filesystem_anchor(path: str) -> str:
    absolute_path = os.path.abspath(path)
    drive, tail = os.path.splitdrive(absolute_path)
    if not os.path.isabs(absolute_path):
        raise ValidationError("Host filesystem path must be absolute.")
    if drive:
        return os.path.normpath(f"{drive}{os.sep}")
    if not tail.startswith(os.sep):
        raise ValidationError("Host filesystem path must have a filesystem root.")
    return os.path.normpath(os.sep)


def _comparison_key(path: str) -> str:
    return os.path.normcase(os.path.normpath(path))


def default_host_filesystem_root() -> str:
    return resolve_host_filesystem_root(_filesystem_anchor(os.curdir))


def resolve_host_filesystem_root(root_path: str) -> str:
    resolved_path = resolve_existing_workspace_directory(root_path)
    canonical_root = _filesystem_anchor(resolved_path)
    if _comparison_key(resolved_path) != _comparison_key(canonical_root):
        raise ValidationError("root_path must identify a filesystem root.")
    return canonical_root


def enumerate_host_filesystem_roots() -> tuple[str, ...]:
    default_root = default_host_filesystem_root()
    discovered = listdrives()
    roots_by_key = {_comparison_key(default_root): default_root}
    unavailable_roots: list[str] = []
    first_unavailable_exception: ValidationError | None = None
    for discovered_root in discovered:
        try:
            resolved_root = resolve_host_filesystem_root(discovered_root)
        except ValidationError as exception:
            unavailable_roots.append(discovered_root)
            if first_unavailable_exception is None:
                first_unavailable_exception = exception
            continue
        resolved_key = _comparison_key(resolved_root)
        if resolved_key not in roots_by_key:
            roots_by_key[resolved_key] = resolved_root
    if first_unavailable_exception is not None:
        log_handled_exception(
            get_logger(LOGGER_NAME),
            first_unavailable_exception,
            message="Skipped unavailable host filesystem roots during discovery",
            operation=OPERATION_HOST_FILESYSTEM_ROOT_DISCOVERY,
            details={"unavailable_roots": unavailable_roots},
            level="info",
        )
    default_key = _comparison_key(default_root)
    remaining = sorted(
        (root for key, root in roots_by_key.items() if key != default_key),
        key=_comparison_key,
    )
    return (default_root, *remaining)


def locate_existing_host_directory(directory_path: str) -> HostDirectoryLocation:
    absolute_path = resolve_existing_workspace_directory(directory_path)
    root_path = resolve_host_filesystem_root(_filesystem_anchor(absolute_path))
    relative_path = os.path.relpath(absolute_path, root_path)
    if relative_path == os.pardir or relative_path.startswith(f"{os.pardir}{os.sep}"):
        raise ValidationError("Host directory must remain within its filesystem root.")
    return HostDirectoryLocation(root_path=root_path, absolute_path=absolute_path)
