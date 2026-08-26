"""SoAI - Pre-restore snapshot creation and rollback operations [backend/app/backup/restore_snapshot.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
from functools import partial
from typing import TYPE_CHECKING

from app.backup.backup_removal import (
    remove_tree_no_symlinks,
    sync_remove_tree_no_symlinks,
)
from app.backup.copy_no_symlinks.file_copy import sync_copy_file_no_symlinks
from app.backup.copy_no_symlinks.tree_copy import (
    sync_copy_tree_no_symlinks,
    sync_fsync_directory_tree,
)
from app.backup.restore_destinations import (
    ensure_restore_destination_is_safe,
    resolve_restore_destination,
)
from app.backup.restore_journal import (
    RestoreJournalItem,
    RestoreJournalState,
    create_restore_journal,
    get_restore_journal_path,
    transition_restore_journal,
)
from core.backup.manifest import normalize_manifest_rel_path
from core.concurrency.joined_thread_call import run_joined_thread_call
from core.errors.exceptions import StateError
from core.filesystem.async_queries import async_isdir, async_path_exists
from core.filesystem.atomic_write_primitives import fsync_directory
from core.logging.protocols import LoggerProtocol

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "cleanup_pre_restore_snapshot",
    "create_pre_restore_snapshot",
    "get_pre_restore_snapshot_path",
    "rollback_from_snapshot",
)


def get_pre_restore_snapshot_path(backups_path: str) -> str:
    return os.path.abspath(os.path.join(backups_path, ".pre_restore_snapshot"))


def _sync_fsync_snapshot(snapshot_path: str) -> None:
    sync_fsync_directory_tree(snapshot_path)
    fsync_directory(os.path.dirname(snapshot_path), strict=True)


def _sync_remove_path_durably(path: str) -> bool:
    existed = os.path.lexists(path)
    sync_remove_tree_no_symlinks(path)
    parent_path = os.path.dirname(path)
    if os.path.isdir(parent_path):
        fsync_directory(parent_path, strict=True)
    elif existed:
        raise StateError("Restore rollback destination parent disappeared during cleanup.")
    return existed


def _paths_overlap(first_path: str, second_path: str) -> bool:
    normalized_first = os.path.normcase(os.path.abspath(first_path))
    normalized_second = os.path.normcase(os.path.abspath(second_path))
    try:
        common_path = os.path.commonpath((normalized_first, normalized_second))
    except ValueError:
        return False
    return common_path in {normalized_first, normalized_second}


def _validate_transaction_paths(
    *,
    project_root: str,
    snapshot_path: str,
    snapshot_items: dict[str, RestoreJournalItem],
) -> None:
    transaction_paths = (snapshot_path, get_restore_journal_path(project_root))
    destinations = list(snapshot_items.values())
    for index, item in enumerate(destinations):
        for transaction_path in transaction_paths:
            if _paths_overlap(item.destination_path, transaction_path):
                raise StateError("Restore destination overlaps transaction recovery storage.")
        for other_item in destinations[index + 1 :]:
            if _paths_overlap(item.destination_path, other_item.destination_path):
                raise StateError("Restore destinations overlap each other.")


async def create_pre_restore_snapshot(
    *,
    project_root: str,
    backups_path: str,
    manifest_files: JSONDict,
    restore_destinations: dict[str, str],
    log: LoggerProtocol,
) -> RestoreJournalState:
    snapshot_path = get_pre_restore_snapshot_path(backups_path)
    snapshot_items: dict[str, RestoreJournalItem] = {}
    for rel_path in manifest_files:
        normalized_rel_path = normalize_manifest_rel_path(str(rel_path))
        destination_path = resolve_restore_destination(
            normalized_rel_path,
            restore_destinations=restore_destinations,
        )
        snapshot_items[normalized_rel_path] = RestoreJournalItem(
            destination_path=destination_path,
            existed=await async_path_exists(destination_path),
        )
    _validate_transaction_paths(
        project_root=project_root,
        snapshot_path=snapshot_path,
        snapshot_items=snapshot_items,
    )
    journal_state = await create_restore_journal(
        project_root,
        snapshot_path=snapshot_path,
        items=snapshot_items,
    )
    if await async_path_exists(snapshot_path):
        await remove_tree_no_symlinks(snapshot_path)
    await run_joined_thread_call(
        partial(os.makedirs, snapshot_path, mode=0o700, exist_ok=False),
        task_name="backup-restore-snapshot-root-create",
    )
    for rel_path, snapshot_item in snapshot_items.items():
        if not snapshot_item.existed:
            continue
        snapshot_item_path = os.path.join(snapshot_path, rel_path)
        ensure_restore_destination_is_safe(snapshot_item_path)
        await run_joined_thread_call(
            partial(
                os.makedirs,
                os.path.dirname(snapshot_item_path),
                mode=0o700,
                exist_ok=True,
            ),
            task_name="backup-restore-snapshot-parent-create",
        )
        if await async_isdir(snapshot_item.destination_path):
            await run_joined_thread_call(
                sync_copy_tree_no_symlinks,
                snapshot_item.destination_path,
                snapshot_item_path,
                task_name="backup-restore-snapshot-directory-copy",
            )
        else:
            await run_joined_thread_call(
                sync_copy_file_no_symlinks,
                snapshot_item.destination_path,
                snapshot_item_path,
                task_name="backup-restore-snapshot-file-copy",
            )
    await run_joined_thread_call(
        _sync_fsync_snapshot,
        snapshot_path,
        task_name="backup-restore-snapshot-sync",
    )
    prepared_state = await transition_restore_journal(
        project_root,
        expected_state=journal_state,
        phase="prepared",
    )
    log.info(
        "Created durable pre-restore snapshot with %d items at %s",
        len(snapshot_items),
        snapshot_path,
    )
    return prepared_state


async def rollback_from_snapshot(
    *,
    state: RestoreJournalState,
    log: LoggerProtocol,
) -> int:
    snapshot_path = state.snapshot_path
    if not await async_path_exists(snapshot_path):
        raise StateError("Pre-restore snapshot is unavailable for rollback.")
    rollback_count = 0
    for rel_path, snapshot_item in state.items.items():
        destination_path = snapshot_item.destination_path
        ensure_restore_destination_is_safe(destination_path)
        destination_parent = os.path.dirname(destination_path)
        if not snapshot_item.existed:
            removed = await run_joined_thread_call(
                _sync_remove_path_durably,
                destination_path,
                task_name="backup-restore-rollback-new-item-remove",
            )
            if removed:
                rollback_count += 1
            continue
        snapshot_item_path = os.path.join(snapshot_path, rel_path)
        ensure_restore_destination_is_safe(snapshot_item_path)
        if not await async_path_exists(snapshot_item_path):
            raise StateError(
                f"Pre-restore snapshot is missing item for {rel_path}.",
                details={
                    "rel_path": rel_path,
                    "destination_path": destination_path,
                },
            )
        if await async_path_exists(destination_path):
            await run_joined_thread_call(
                sync_remove_tree_no_symlinks,
                destination_path,
                task_name="backup-restore-rollback-destination-remove",
            )
        await run_joined_thread_call(
            partial(os.makedirs, destination_parent, mode=0o700, exist_ok=True),
            task_name="backup-restore-rollback-parent-create",
        )
        if await async_isdir(snapshot_item_path):
            await run_joined_thread_call(
                sync_copy_tree_no_symlinks,
                snapshot_item_path,
                destination_path,
                task_name="backup-restore-rollback-directory-copy",
            )
            await run_joined_thread_call(
                sync_fsync_directory_tree,
                destination_path,
                task_name="backup-restore-rollback-directory-sync",
            )
        else:
            await run_joined_thread_call(
                sync_copy_file_no_symlinks,
                snapshot_item_path,
                destination_path,
                task_name="backup-restore-rollback-file-copy",
            )
        await run_joined_thread_call(
            partial(fsync_directory, destination_parent, strict=True),
            task_name="backup-restore-rollback-parent-sync",
        )
        rollback_count += 1
    log.info("Rolled back %d items from pre-restore snapshot.", rollback_count)
    return rollback_count


async def cleanup_pre_restore_snapshot(
    *,
    snapshot_path: str,
    log: LoggerProtocol,
) -> None:
    removed = await run_joined_thread_call(
        _sync_remove_path_durably,
        snapshot_path,
        task_name="backup-restore-snapshot-cleanup",
    )
    if removed:
        log.info("Cleaned up pre-restore snapshot.")
