"""SoAI - File explorer upload-specific mutations [backend/features/file_explorer/upload_mutation_service.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import os
import stat
from functools import partial
from typing import TYPE_CHECKING

from core.concurrency.bounded_blocking import BoundedBlockingPool
from core.concurrency.joined_thread_call import run_joined_thread_call
from core.concurrency.path_tree_lock import AsyncPathTreeLock
from core.concurrency.protocols import CancellationTokenProtocol
from core.errors.exceptions import ValidationError
from core.events.types_file_explorer import (
    FileExplorerOperation,
    FileSystemChangedEvent,
)
from core.files.commit_cleanup import remove_committed_file
from core.files.commit_receipt import FileCommitReceipt
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
    mutation_locks: AsyncPathTreeLock,
    storage_manager: StorageManagerProtocol,
    temp_path: str,
    expected_size: int,
    expected_sha256: str,
    file_content_pool: BoundedBlockingPool,
    virtual_destination: str,
    token: CancellationTokenProtocol,
    create_missing_parents: bool,
    database_path: str | None,
    allow_symlinks: bool,
) -> FileCommitReceipt:
    virtual_destination = canonicalize_virtual_path(root_scope, virtual_destination)
    real_destination = root_scope.resolve(virtual_destination)
    relative_destination = os.path.relpath(real_destination, root_scope.root_path)
    locked_destination = (
        os.path.join(root_scope.root_path, relative_destination.split(os.sep, maxsplit=1)[0])
        if create_missing_parents
        else real_destination
    )
    async with mutation_locks.lock_many([temp_path, locked_destination]):
        ensure_not_protected_sqlite_runtime_file(
            real_destination,
            database_path,
            operation="file_explorer.upload",
        )
        resolved_destination = await run_joined_thread_call(
            partial(
                resolve_upload_destination,
                root_scope,
                virtual_destination,
                create_missing_parents=create_missing_parents,
            ),
            task_name="file-upload-destination",
            pool=file_content_pool,
            retain_resources_until_complete=True,
        )
        ensure_not_protected_sqlite_runtime_file(
            resolved_destination,
            database_path,
            operation="file_explorer.upload",
        )
        token.raise_if_cancelled()
        return await commit_staged_upload(
            source_path=temp_path,
            destination_path=resolved_destination,
            destination_root=root_scope.root_path,
            expected_size=expected_size,
            expected_sha256=expected_sha256,
            file_content_pool=file_content_pool,
            token=token,
            storage_manager=storage_manager,
            allow_symlinks=allow_symlinks,
        )


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


async def cleanup_upload_commit(
    *,
    root_scope: FileSystemRootScopeProtocol,
    receipt: FileCommitReceipt,
    mutation_locks: AsyncPathTreeLock,
) -> None:
    if os.path.normcase(os.path.abspath(root_scope.root_path)) != os.path.normcase(
        receipt.root_path
    ):
        raise ValidationError("The upload receipt belongs to a different workspace.")
    async with mutation_locks.lock(receipt.destination_path):
        await run_joined_thread_call(
            remove_committed_file,
            receipt,
            task_name="file-upload-cleanup",
            retain_resources_until_complete=True,
        )
