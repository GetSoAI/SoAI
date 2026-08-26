"""SoAI - File explorer write, directory creation, and deletion mutations [backend/features/file_explorer/entry_mutation_service.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import os
import stat
from typing import TYPE_CHECKING

from core.concurrency.path_tree_lock import AsyncPathTreeLock
from core.errors.exceptions import NotFoundError, ValidationError
from core.events.types_file_explorer import (
    FileExplorerOperation,
    FileSystemChangedEvent,
)
from core.files.protected_sqlite_runtime_paths import (
    ensure_directory_excludes_protected_sqlite_runtime_files,
    ensure_not_protected_sqlite_runtime_file,
)
from core.hardware.reservation_claims import claim_reserved_write
from features.file_explorer.event_publishing import try_publish_filesystem_event
from features.file_explorer.path_resolution import canonicalize_virtual_path

if TYPE_CHECKING:
    from core.events.protocols import EventBusProtocol
    from core.files.protocols_explorer import FileSystemRootScopeProtocol
    from core.hardware.protocols_storage import StorageManagerProtocol
    from features.file_explorer.internal_protocols import SecureFileOpsProtocol

__all__ = (
    "create_directory",
    "delete_entry",
    "write_text_file",
)

DIRECTORY_CREATE_BYTES_PER_LEVEL = 64 * 1024


async def write_text_file(
    *,
    root_scope: FileSystemRootScopeProtocol,
    secure_ops: SecureFileOpsProtocol,
    storage_manager: StorageManagerProtocol,
    mutation_locks: AsyncPathTreeLock,
    event_bus: EventBusProtocol,
    virtual_path: str,
    content: str,
    temp_dir: str,
    database_path: str | None,
) -> None:
    virtual_path = canonicalize_virtual_path(root_scope, virtual_path)
    real_path = root_scope.resolve(virtual_path)
    event: FileSystemChangedEvent | None = None
    async with mutation_locks.lock(real_path):
        parent_dir = os.path.dirname(real_path)
        if not os.path.isdir(parent_dir):
            raise NotFoundError(
                "Parent directory does not exist.",
                operation="file_explorer.write_text_file",
            )
        if os.path.isdir(real_path):
            raise ValidationError(
                "Target path is a directory.",
                operation="file_explorer.write_text_file",
            )
        ensure_not_protected_sqlite_runtime_file(
            real_path,
            database_path,
            operation="file_explorer.write_text_file",
        )
        existed = os.path.exists(real_path)
        encoded_content = content.encode("utf-8")
        with storage_manager.reserve_disk_space(
            path=parent_dir,
            required_bytes=len(encoded_content),
            operation="file_explorer.write_text_file",
            details={
                "virtual_path": virtual_path,
                "required_bytes": len(encoded_content),
            },
        ) as reservation:
            with claim_reserved_write(reservation, size_bytes=len(encoded_content)):
                await asyncio.to_thread(
                    secure_ops.write_text_atomic,
                    real_path,
                    content,
                    temp_dir=temp_dir,
                    root_path=root_scope.root_path,
                )
        event = FileSystemChangedEvent(
            operation=FileExplorerOperation.UPDATE if existed else FileExplorerOperation.CREATE,
            virtual_path=virtual_path,
            is_directory=False,
            workspace_root_path=root_scope.root_path,
        )
    if event is not None:
        await try_publish_filesystem_event(event_bus, event)


async def create_directory(
    *,
    root_scope: FileSystemRootScopeProtocol,
    secure_ops: SecureFileOpsProtocol,
    storage_manager: StorageManagerProtocol,
    mutation_locks: AsyncPathTreeLock,
    event_bus: EventBusProtocol,
    virtual_path: str,
    database_path: str | None,
) -> None:
    virtual_path = canonicalize_virtual_path(root_scope, virtual_path)
    real_path = root_scope.resolve(virtual_path)
    event: FileSystemChangedEvent | None = None
    async with mutation_locks.lock(real_path):
        if os.path.isdir(real_path):
            return
        ensure_directory_excludes_protected_sqlite_runtime_files(
            real_path,
            database_path,
            operation="file_explorer.mkdir",
        )
        if os.path.exists(real_path):
            raise ValidationError(
                "Target path already exists and is not a directory.",
                operation="file_explorer.mkdir",
            )
        try:
            required_bytes = _directory_create_required_bytes(real_path)
            with storage_manager.reserve_disk_space(
                path=os.path.dirname(real_path),
                required_bytes=required_bytes,
                operation="file_explorer.mkdir",
                details={
                    "virtual_path": virtual_path,
                    "required_bytes": required_bytes,
                },
            ) as reservation:
                with claim_reserved_write(reservation, size_bytes=required_bytes):
                    await asyncio.to_thread(secure_ops.create_directory, real_path)
        except (FileExistsError, NotADirectoryError) as exception:
            raise ValidationError(
                "Cannot create directory because the parent path is not a directory.",
                operation="file_explorer.mkdir",
            ) from exception
        event = FileSystemChangedEvent(
            operation=FileExplorerOperation.MKDIR,
            virtual_path=virtual_path,
            is_directory=True,
            workspace_root_path=root_scope.root_path,
        )
    if event is not None:
        await try_publish_filesystem_event(event_bus, event)


async def delete_entry(
    *,
    root_scope: FileSystemRootScopeProtocol,
    secure_ops: SecureFileOpsProtocol,
    mutation_locks: AsyncPathTreeLock,
    event_bus: EventBusProtocol,
    virtual_path: str,
    database_path: str | None,
) -> None:
    virtual_path = canonicalize_virtual_path(root_scope, virtual_path)
    real_path = root_scope.resolve(virtual_path)
    event: FileSystemChangedEvent | None = None
    async with mutation_locks.lock(real_path):
        try:
            entry_stat = await asyncio.to_thread(secure_ops.stat_path, real_path)
        except NotFoundError as original_exception:
            raise NotFoundError(
                f"Path not found: '{virtual_path}'.",
                operation="file_explorer.delete_entry",
            ) from original_exception
        is_dir = stat.S_ISDIR(entry_stat.st_mode)
        if is_dir:
            ensure_directory_excludes_protected_sqlite_runtime_files(
                real_path,
                database_path,
                operation="file_explorer.delete_entry",
            )
            await asyncio.to_thread(secure_ops.remove_directory_recursive, real_path)
        else:
            ensure_not_protected_sqlite_runtime_file(
                real_path,
                database_path,
                operation="file_explorer.delete_entry",
            )
            await asyncio.to_thread(secure_ops.remove_file, real_path)
        event = FileSystemChangedEvent(
            operation=FileExplorerOperation.DELETE,
            virtual_path=virtual_path,
            is_directory=is_dir,
            workspace_root_path=root_scope.root_path,
        )
    if event is not None:
        await try_publish_filesystem_event(event_bus, event)


def _directory_create_required_bytes(real_path: str) -> int:
    missing_levels = 0
    cursor = real_path
    while cursor and not os.path.exists(cursor):
        missing_levels += 1
        parent = os.path.dirname(cursor)
        if parent == cursor:
            break
        cursor = parent
    return max(1, missing_levels) * DIRECTORY_CREATE_BYTES_PER_LEVEL
