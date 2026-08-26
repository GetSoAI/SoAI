"""SoAI - Strict workspace-rooted descriptor helpers [backend/core/files/workspace_descriptor.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
import stat
from dataclasses import dataclass
from typing import NoReturn

from core.files.managed_storage_errors import FileStorageSecurityError
from core.files.windows_managed_path_handles import open_windows_managed_path_handles
from core.files.windows_reparse_points import is_windows_reparse_point

__all__ = (
    "WorkspaceEntryDescriptor",
    "WorkspaceFileDescriptor",
    "canonical_workspace_virtual_path",
    "close_workspace_descriptor_stack",
    "is_disallowed_workspace_link",
    "normalize_workspace_virtual_path_parts",
    "open_workspace_directory_fd",
    "open_workspace_file_descriptor",
    "open_workspace_parent_descriptor_stack",
    "stat_workspace_entry",
)


@dataclass(frozen=True, slots=True)
class WorkspaceEntryDescriptor:
    entry_type: str
    name: str
    size_bytes: int | None
    modified_at_ms: int


@dataclass(frozen=True, slots=True)
class WorkspaceFileDescriptor:
    descriptor: int
    size_bytes: int
    modified_at_ms: int


def _raise(error_cls: type[Exception], message: str) -> NoReturn:
    raise error_cls(message)


def _directory_open_flags() -> int:
    if os.name != "posix":
        return os.O_RDONLY
    return os.O_RDONLY | os.O_CLOEXEC | os.O_DIRECTORY | os.O_NOFOLLOW


def _file_open_flags() -> int:
    if os.name != "posix":
        return os.O_RDONLY
    return os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW


def is_disallowed_workspace_link(stat_result: os.stat_result) -> bool:
    return stat.S_ISLNK(stat_result.st_mode) or is_windows_reparse_point(stat_result)


def normalize_workspace_virtual_path_parts(
    workspace_root: str,
    conversation_virtual_path: str,
    *,
    error_cls: type[Exception],
) -> list[str]:
    value = conversation_virtual_path.strip()
    if not value:
        _raise(error_cls, "SoAI path source reference cannot be empty.")
    if "\x00" in value:
        _raise(error_cls, "SoAI path source reference cannot contain NUL bytes.")
    normalized = value.replace("\\", "/")
    normalized = normalized.removeprefix("/")
    parts = [part for part in normalized.split("/") if part and part != "."]
    if not parts or any(part == ".." for part in parts):
        _raise(error_cls, "SoAI path source reference cannot target the workspace root.")
    root_abs = os.path.realpath(os.path.abspath(workspace_root))
    if not os.path.isdir(root_abs):
        _raise(error_cls, "SoAI path workspace root is not available.")
    return parts


def canonical_workspace_virtual_path(
    workspace_root: str,
    conversation_virtual_path: str,
    *,
    error_cls: type[Exception],
) -> str:
    parts = normalize_workspace_virtual_path_parts(
        workspace_root,
        conversation_virtual_path,
        error_cls=error_cls,
    )
    return f"/{'/'.join(parts)}"


def open_workspace_directory_fd(
    dir_fd: int | None,
    segment: str,
    *,
    error_cls: type[Exception],
) -> int:
    try:
        stat_before = os.stat(segment, dir_fd=dir_fd, follow_symlinks=False)
    except FileNotFoundError as exception:
        raise error_cls("SoAI path target is missing.") from exception
    except OSError as exception:
        raise error_cls("SoAI path parent segment could not be inspected.") from exception
    if is_disallowed_workspace_link(stat_before):
        _raise(error_cls, "SoAI path traversal through symbolic links is not allowed.")
    if not stat.S_ISDIR(stat_before.st_mode):
        _raise(error_cls, "SoAI path parent segment is not a directory.")
    try:
        descriptor = os.open(segment, _directory_open_flags(), dir_fd=dir_fd)
    except OSError as exception:
        raise error_cls("SoAI path parent segment could not be opened.") from exception
    try:
        stat_after = os.fstat(descriptor)
    except OSError as exception:
        close_workspace_descriptor_stack([descriptor])
        raise error_cls("SoAI path parent segment could not be inspected.") from exception
    if stat_before.st_dev == stat_after.st_dev and stat_before.st_ino == stat_after.st_ino:
        return descriptor
    close_workspace_descriptor_stack([descriptor])
    _raise(error_cls, "SoAI path parent segment changed during traversal.")


def open_workspace_parent_descriptor_stack(
    workspace_root: str,
    parts: list[str],
    *,
    error_cls: type[Exception],
) -> list[int]:
    stack: list[int] = []
    completed = False
    try:
        stack.append(open_workspace_directory_fd(None, workspace_root, error_cls=error_cls))
        current_descriptor = stack[-1]
        for segment in parts[:-1]:
            current_descriptor = open_workspace_directory_fd(
                current_descriptor,
                segment,
                error_cls=error_cls,
            )
            stack.append(current_descriptor)
        completed = True
        return stack
    finally:
        if not completed:
            close_workspace_descriptor_stack(stack)


def close_workspace_descriptor_stack(stack: list[int]) -> None:
    for descriptor in reversed(stack):
        try:
            os.close(descriptor)
        except OSError:
            continue


def _descriptor_from_stat(stat_result: os.stat_result, name: str) -> WorkspaceEntryDescriptor:
    if stat.S_ISDIR(stat_result.st_mode):
        return WorkspaceEntryDescriptor(
            entry_type="folder",
            name=name,
            size_bytes=None,
            modified_at_ms=int(stat_result.st_mtime * 1000),
        )
    if not stat.S_ISREG(stat_result.st_mode):
        raise ValueError("SoAI path target must be a regular file or directory.")
    return WorkspaceEntryDescriptor(
        entry_type="file",
        name=name,
        size_bytes=int(stat_result.st_size),
        modified_at_ms=int(stat_result.st_mtime * 1000),
    )


def stat_workspace_entry(
    workspace_root: str,
    conversation_virtual_path: str,
    *,
    error_cls: type[Exception] = ValueError,
) -> WorkspaceEntryDescriptor:
    if os.name == "nt":
        parts = normalize_workspace_virtual_path_parts(
            workspace_root,
            conversation_virtual_path,
            error_cls=error_cls,
        )
        try:
            target = os.path.join(os.path.abspath(workspace_root), *parts)
            with open_windows_managed_path_handles(
                workspace_root,
                target,
                require_directory=None,
            ) as opened_path:
                return _descriptor_from_stat(opened_path.stat_result, parts[-1])
        except FileStorageSecurityError as exception:
            if isinstance(exception.__cause__, FileNotFoundError):
                raise error_cls("SoAI path target is missing.") from exception
            raise error_cls("SoAI path target could not be inspected securely.") from exception
        except ValueError as exception:
            raise error_cls(str(exception)) from exception
    parts = normalize_workspace_virtual_path_parts(
        workspace_root,
        conversation_virtual_path,
        error_cls=error_cls,
    )
    stack = open_workspace_parent_descriptor_stack(workspace_root, parts, error_cls=error_cls)
    try:
        leaf = parts[-1]
        try:
            stat_result = os.stat(leaf, dir_fd=stack[-1], follow_symlinks=False)
        except FileNotFoundError as exception:
            raise error_cls("SoAI path target is missing.") from exception
        except OSError as exception:
            raise error_cls("SoAI path target could not be inspected.") from exception
        if is_disallowed_workspace_link(stat_result):
            _raise(error_cls, "SoAI path target cannot be a symbolic link.")
        try:
            return _descriptor_from_stat(stat_result, leaf)
        except ValueError as exception:
            raise error_cls(str(exception)) from exception
    finally:
        close_workspace_descriptor_stack(stack)


def open_workspace_file_descriptor(
    workspace_root: str,
    conversation_virtual_path: str,
    *,
    error_cls: type[Exception] = ValueError,
) -> WorkspaceFileDescriptor:
    if os.name == "nt":
        parts = normalize_workspace_virtual_path_parts(
            workspace_root,
            conversation_virtual_path,
            error_cls=error_cls,
        )
        try:
            target = os.path.join(os.path.abspath(workspace_root), *parts)
            with open_windows_managed_path_handles(
                workspace_root,
                target,
                require_directory=False,
                read_leaf=True,
            ) as opened_path:
                descriptor = opened_path.detach_leaf_file_descriptor()
                return WorkspaceFileDescriptor(
                    descriptor=descriptor,
                    size_bytes=int(opened_path.stat_result.st_size),
                    modified_at_ms=int(opened_path.stat_result.st_mtime * 1000),
                )
        except FileStorageSecurityError as exception:
            if isinstance(exception.__cause__, FileNotFoundError):
                raise error_cls("SoAI path target is missing.") from exception
            raise error_cls("SoAI path target could not be opened securely.") from exception
    parts = normalize_workspace_virtual_path_parts(
        workspace_root,
        conversation_virtual_path,
        error_cls=error_cls,
    )
    stack = open_workspace_parent_descriptor_stack(workspace_root, parts, error_cls=error_cls)
    try:
        leaf = parts[-1]
        try:
            stat_before = os.stat(leaf, dir_fd=stack[-1], follow_symlinks=False)
        except FileNotFoundError as exception:
            raise error_cls("SoAI path target is missing.") from exception
        except OSError as exception:
            raise error_cls("SoAI path target could not be inspected.") from exception
        if is_disallowed_workspace_link(stat_before) or not stat.S_ISREG(stat_before.st_mode):
            _raise(error_cls, "SoAI path target must be a regular file.")
        descriptor = -1
        try:
            descriptor = os.open(leaf, _file_open_flags(), dir_fd=stack[-1])
        except OSError as exception:
            raise error_cls("SoAI path target could not be opened.") from exception
        completed = False
        try:
            try:
                stat_after = os.fstat(descriptor)
            except OSError as exception:
                raise error_cls(
                    "SoAI path target could not be inspected after open.",
                ) from exception
            if stat_before.st_dev != stat_after.st_dev or stat_before.st_ino != stat_after.st_ino:
                _raise(error_cls, "SoAI path target changed during open.")
            if not stat.S_ISREG(stat_after.st_mode):
                _raise(error_cls, "SoAI path target must be a regular file.")
            if is_windows_reparse_point(stat_after):
                _raise(error_cls, "SoAI path target cannot be a reparse point.")
            file_descriptor = WorkspaceFileDescriptor(
                descriptor=descriptor,
                size_bytes=int(stat_after.st_size),
                modified_at_ms=int(stat_after.st_mtime * 1000),
            )
            completed = True
            return file_descriptor
        finally:
            if not completed and descriptor >= 0:
                close_workspace_descriptor_stack([descriptor])
    finally:
        close_workspace_descriptor_stack(stack)
