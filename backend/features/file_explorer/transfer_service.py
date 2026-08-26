"""SoAI - File explorer copy/move operations [backend/features/file_explorer/transfer_service.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import os
import stat
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.events.types_file_explorer import (
    FileExplorerOperation,
    FileSystemChangedEvent,
)
from core.files.directory_size import calculate_directory_size_bytes
from core.files.path_policy import is_path_inside_directory, is_same_path
from core.files.protected_sqlite_runtime_paths import (
    ensure_directory_excludes_protected_sqlite_runtime_files,
    ensure_not_protected_sqlite_runtime_file,
)
from features.file_explorer.event_publishing import try_publish_filesystem_event
from features.file_explorer.path_resolution import canonicalize_virtual_path

if TYPE_CHECKING:
    from core.concurrency.path_tree_lock import AsyncPathTreeLock
    from core.events.protocols import EventBusProtocol
    from core.files.protocols_explorer import FileSystemRootScopeProtocol
    from core.hardware.protocols_storage import StorageManagerProtocol
    from features.file_explorer.internal_protocols import SecureFileOpsProtocol

__all__ = (
    "copy_entry",
    "move_entry",
)


async def move_entry(
    *,
    root_scope: FileSystemRootScopeProtocol,
    secure_ops: SecureFileOpsProtocol,
    mutation_locks: AsyncPathTreeLock,
    event_bus: EventBusProtocol,
    source_virtual_path: str,
    destination_virtual_path: str,
    overwrite: bool,
    database_path: str | None,
) -> None:
    source_virtual_path = canonicalize_virtual_path(root_scope, source_virtual_path)
    destination_virtual_path = canonicalize_virtual_path(root_scope, destination_virtual_path)
    source_real = root_scope.resolve(source_virtual_path)
    destination_real = root_scope.resolve(destination_virtual_path)
    if is_same_path(source_real, destination_real):
        raise ValidationError(
            "Source and destination paths are identical.",
            operation="file_explorer.move",
        )
    event: FileSystemChangedEvent | None = None
    async with mutation_locks.lock_many((source_real, destination_real)):
        st = await asyncio.to_thread(secure_ops.stat_path, source_real)
        is_dir = stat.S_ISDIR(st.st_mode)
        if is_dir:
            ensure_directory_excludes_protected_sqlite_runtime_files(
                source_real,
                database_path,
                operation="file_explorer.move",
            )
        else:
            ensure_not_protected_sqlite_runtime_file(
                source_real,
                database_path,
                operation="file_explorer.move",
            )
        ensure_not_protected_sqlite_runtime_file(
            destination_real,
            database_path,
            operation="file_explorer.move",
        )
        if os.path.lexists(destination_real):
            if not overwrite:
                raise ValidationError(
                    "Destination path already exists.",
                    operation="file_explorer.move",
                )
            if is_dir:
                raise ValidationError(
                    "Cannot overwrite an existing destination when moving a directory.",
                    operation="file_explorer.move",
                )
            if os.path.isdir(destination_real):
                raise ValidationError(
                    "Destination path already exists and is a directory.",
                    operation="file_explorer.move",
                )
            await asyncio.to_thread(secure_ops.remove_file, destination_real)
        if is_dir:
            if is_path_inside_directory(source_real, destination_real):
                raise ValidationError(
                    "Cannot move a directory into itself.",
                    operation="file_explorer.move",
                )
        await asyncio.to_thread(secure_ops.move_entry, source_real, destination_real)
        event = FileSystemChangedEvent(
            operation=FileExplorerOperation.MOVE,
            virtual_path=source_virtual_path,
            is_directory=is_dir,
            destination_virtual_path=destination_virtual_path,
            workspace_root_path=root_scope.root_path,
        )
    if event is not None:
        await try_publish_filesystem_event(event_bus, event)


async def copy_entry(
    *,
    root_scope: FileSystemRootScopeProtocol,
    secure_ops: SecureFileOpsProtocol,
    mutation_locks: AsyncPathTreeLock,
    event_bus: EventBusProtocol,
    storage_manager: StorageManagerProtocol,
    source_virtual_path: str,
    destination_virtual_path: str,
    overwrite: bool,
    database_path: str | None,
) -> None:
    source_virtual_path = canonicalize_virtual_path(root_scope, source_virtual_path)
    destination_virtual_path = canonicalize_virtual_path(root_scope, destination_virtual_path)
    source_real = root_scope.resolve(source_virtual_path)
    destination_real = root_scope.resolve(destination_virtual_path)
    if is_same_path(source_real, destination_real):
        raise ValidationError(
            "Source and destination paths are identical.",
            operation="file_explorer.copy",
        )
    event: FileSystemChangedEvent | None = None
    async with mutation_locks.lock_many((source_real, destination_real)):
        st = await asyncio.to_thread(secure_ops.stat_path, source_real)
        is_dir = stat.S_ISDIR(st.st_mode)
        ensure_not_protected_sqlite_runtime_file(
            destination_real,
            database_path,
            operation="file_explorer.copy",
        )
        if os.path.lexists(destination_real):
            if not overwrite:
                raise ValidationError(
                    "Destination path already exists.",
                    operation="file_explorer.copy",
                )
            if is_dir:
                raise ValidationError(
                    "Cannot overwrite an existing destination when copying a directory.",
                    operation="file_explorer.copy",
                )
            if os.path.isdir(destination_real):
                raise ValidationError(
                    "Destination path already exists and is a directory.",
                    operation="file_explorer.copy",
                )
            await asyncio.to_thread(secure_ops.remove_file, destination_real)
        if is_dir:
            if is_path_inside_directory(source_real, destination_real):
                raise ValidationError(
                    "Cannot copy a directory into itself.",
                    operation="file_explorer.copy",
                )
            required_bytes = await asyncio.to_thread(calculate_directory_size_bytes, source_real)
            with storage_manager.reserve_disk_space(
                path=os.path.dirname(destination_real),
                required_bytes=required_bytes,
                operation="file_explorer.copy_entry",
                details={
                    "source_path": source_real,
                    "destination_path": destination_real,
                    "is_directory": True,
                    "required_bytes": required_bytes,
                },
            ) as reservation:
                await asyncio.to_thread(
                    secure_ops.copy_directory,
                    source_real,
                    destination_real,
                    write_reservation=reservation,
                )
        else:
            required_bytes = int(st.st_size)
            with storage_manager.reserve_disk_space(
                path=os.path.dirname(destination_real),
                required_bytes=required_bytes,
                operation="file_explorer.copy_entry",
                details={
                    "source_path": source_real,
                    "destination_path": destination_real,
                    "is_directory": False,
                    "required_bytes": required_bytes,
                },
            ) as reservation:
                await asyncio.to_thread(
                    secure_ops.copy_file,
                    source_real,
                    destination_real,
                    write_reservation=reservation,
                )
        event = FileSystemChangedEvent(
            operation=FileExplorerOperation.COPY,
            virtual_path=source_virtual_path,
            is_directory=is_dir,
            destination_virtual_path=destination_virtual_path,
            workspace_root_path=root_scope.root_path,
        )
    if event is not None:
        await try_publish_filesystem_event(event_bus, event)
