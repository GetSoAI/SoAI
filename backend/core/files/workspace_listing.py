"""SoAI - Strict workspace directory listing helpers [backend/core/files/workspace_listing.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
import stat
from dataclasses import dataclass

from core.files.managed_storage_errors import FileStorageSecurityError
from core.files.windows_managed_path_handles import open_windows_managed_path_handles
from core.files.workspace_descriptor import (
    close_workspace_descriptor_stack,
    is_disallowed_workspace_link,
    normalize_workspace_virtual_path_parts,
    open_workspace_directory_fd,
    open_workspace_parent_descriptor_stack,
)

__all__ = ("WorkspaceDirectoryEntry", "list_workspace_directory")


@dataclass(frozen=True, slots=True)
class WorkspaceDirectoryEntry:
    name: str
    entry_type: str
    size_bytes: int | None
    modified_at_ms: int


def list_workspace_directory(
    workspace_root: str,
    conversation_virtual_path: str,
    *,
    error_cls: type[Exception] = ValueError,
) -> list[WorkspaceDirectoryEntry]:
    if os.name == "nt":
        parts = normalize_workspace_virtual_path_parts(
            workspace_root,
            conversation_virtual_path,
            error_cls=error_cls,
        )
        target = os.path.join(os.path.abspath(workspace_root), *parts)
        try:
            with open_windows_managed_path_handles(
                workspace_root,
                target,
                require_directory=True,
            ) as opened_path:
                return _read_directory_path_entries(opened_path.path)
        except FileStorageSecurityError as exception:
            if isinstance(exception.__cause__, FileNotFoundError):
                raise error_cls("SoAI path target is missing.") from exception
            raise error_cls("SoAI path directory could not be listed securely.") from exception
    parts = normalize_workspace_virtual_path_parts(
        workspace_root,
        conversation_virtual_path,
        error_cls=error_cls,
    )
    stack = open_workspace_parent_descriptor_stack(workspace_root, parts, error_cls=error_cls)
    try:
        directory_descriptor = open_workspace_directory_fd(
            stack[-1],
            parts[-1],
            error_cls=error_cls,
        )
        try:
            return _read_directory_entries(directory_descriptor)
        finally:
            os.close(directory_descriptor)
    finally:
        close_workspace_descriptor_stack(stack)


def _read_directory_entries(directory_descriptor: int) -> list[WorkspaceDirectoryEntry]:
    entries: list[WorkspaceDirectoryEntry] = []
    for name in sorted(os.listdir(directory_descriptor)):
        stat_result = os.stat(name, dir_fd=directory_descriptor, follow_symlinks=False)
        if is_disallowed_workspace_link(stat_result):
            continue
        if stat.S_ISDIR(stat_result.st_mode):
            entry_type = "folder"
            size_bytes = None
        elif stat.S_ISREG(stat_result.st_mode):
            entry_type = "file"
            size_bytes = int(stat_result.st_size)
        else:
            continue
        entries.append(
            WorkspaceDirectoryEntry(
                name=name,
                entry_type=entry_type,
                size_bytes=size_bytes,
                modified_at_ms=int(stat_result.st_mtime * 1000),
            ),
        )
    return entries


def _read_directory_path_entries(directory_path: str) -> list[WorkspaceDirectoryEntry]:
    entries: list[WorkspaceDirectoryEntry] = []
    for entry in sorted(os.scandir(directory_path), key=lambda candidate: candidate.name):
        stat_result = entry.stat(follow_symlinks=False)
        if is_disallowed_workspace_link(stat_result):
            continue
        if stat.S_ISDIR(stat_result.st_mode):
            entry_type = "folder"
            size_bytes = None
        elif stat.S_ISREG(stat_result.st_mode):
            entry_type = "file"
            size_bytes = int(stat_result.st_size)
        else:
            continue
        entries.append(
            WorkspaceDirectoryEntry(
                name=entry.name,
                entry_type=entry_type,
                size_bytes=size_bytes,
                modified_at_ms=int(stat_result.st_mtime * 1000),
            ),
        )
    return entries
