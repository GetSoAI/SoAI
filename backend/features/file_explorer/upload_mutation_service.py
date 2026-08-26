"""SoAI - File explorer upload-specific mutations [backend/features/file_explorer/upload_mutation_service.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import stat
from typing import TYPE_CHECKING

from core.concurrency.path_tree_lock import AsyncPathTreeLock
from core.concurrency.protocols import CancellationTokenProtocol
from core.errors.exceptions import ValidationError
from core.events.types_file_explorer import (
    FileExplorerOperation,
    FileSystemChangedEvent,
)
from core.files.protected_sqlite_runtime_paths import ensure_not_protected_sqlite_runtime_file
from features.file_explorer.event_publishing import try_publish_filesystem_event
from features.file_explorer.path_resolution import (
    canonicalize_virtual_path,
    resolve_upload_destination,
)
from features.file_explorer.secure_ops.staged_upload_commit import commit_staged_upload

if TYPE_CHECKING:
    from core.events.protocols import EventBusProtocol
    from core.files.protocols_explorer import FileSystemRootScopeProtocol
    from core.hardware.protocols_storage import StorageManagerProtocol
    from features.file_explorer.internal_protocols import SecureFileOpsProtocol

__all__ = (
    "move_staged_upload",
    "notify_upload_complete",
)


async def move_staged_upload(
    *,
    root_scope: FileSystemRootScopeProtocol,
    secure_ops: SecureFileOpsProtocol,
    mutation_locks: AsyncPathTreeLock,
    storage_manager: StorageManagerProtocol,
    temp_path: str,
    expected_size: int,
    virtual_destination: str,
    token: CancellationTokenProtocol,
    create_missing_parents: bool,
    database_path: str | None,
    allow_symlinks: bool,
) -> str:
    virtual_destination = canonicalize_virtual_path(root_scope, virtual_destination)
    real_destination = root_scope.resolve(virtual_destination)
    async with mutation_locks.lock(real_destination):
        ensure_not_protected_sqlite_runtime_file(
            real_destination,
            database_path,
            operation="file_explorer.upload",
        )
        resolved_destination = await asyncio.to_thread(
            resolve_upload_destination,
            root_scope,
            secure_ops,
            virtual_destination,
            create_missing_parents=create_missing_parents,
        )
        ensure_not_protected_sqlite_runtime_file(
            resolved_destination,
            database_path,
            operation="file_explorer.upload",
        )
        token.raise_if_cancelled()
        await commit_staged_upload(
            source_path=temp_path,
            destination_path=resolved_destination,
            destination_root=root_scope.root_path,
            expected_size=expected_size,
            token=token,
            storage_manager=storage_manager,
            allow_symlinks=allow_symlinks,
        )
        return resolved_destination


async def notify_upload_complete(
    *,
    root_scope: FileSystemRootScopeProtocol,
    secure_ops: SecureFileOpsProtocol,
    mutation_locks: AsyncPathTreeLock,
    event_bus: EventBusProtocol,
    virtual_path: str,
) -> None:
    virtual_path = canonicalize_virtual_path(root_scope, virtual_path)
    real_path = root_scope.resolve(virtual_path)
    event: FileSystemChangedEvent | None = None
    async with mutation_locks.lock(real_path):
        st = await asyncio.to_thread(secure_ops.stat_path, real_path)
        if stat.S_ISDIR(st.st_mode):
            raise ValidationError(
                "Upload completion target is a directory.",
                operation="file_explorer.upload.notify",
            )
        event = FileSystemChangedEvent(
            operation=FileExplorerOperation.CREATE,
            virtual_path=virtual_path,
            is_directory=False,
            workspace_root_path=root_scope.root_path,
        )
    if event is not None:
        await try_publish_filesystem_event(event_bus, event)
