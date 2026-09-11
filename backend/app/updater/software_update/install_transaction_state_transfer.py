"""SoAI - Snapshot and restore configured update destinations [backend/app/updater/software_update/install_transaction_state_transfer.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os

from app.backup.backup_removal import sync_remove_tree_no_symlinks
from app.updater.software_update.install_transaction_persisted_state import (
    PersistedUpdateState,
    persisted_directory_staging,
)
from app.updater.software_update.install_transaction_state import UpdateTransactionPaths
from core.bootstrap.install_payload_transaction import copy_install_entry, replace_install_entry
from core.errors.exceptions import StateError
from core.filesystem.atomic_write_primitives import fsync_directory
from core.filesystem.file_sync import fsync_install_entry

__all__ = (
    "copy_persisted_update_state",
    "install_persisted_update_directories",
    "restore_persisted_update_state",
)


def copy_persisted_update_state(paths: UpdateTransactionPaths, state: PersistedUpdateState) -> None:
    for slot in state.original_entries:
        source = state.destinations[slot]
        destination = os.path.join(paths.rollback_old_path, *slot.split("/"))
        copy_install_entry(source, os.path.dirname(destination))
        fsync_install_entry(destination)


def _replace_directory(
    paths: UpdateTransactionPaths, slot: str, source: str, destination: str
) -> None:
    if os.path.basename(source) != os.path.basename(destination):
        raise StateError("Update directory source does not match its destination name.")
    os.makedirs(os.path.dirname(destination), exist_ok=True)
    staging = persisted_directory_staging(paths, slot, destination)
    if os.path.lexists(staging):
        sync_remove_tree_no_symlinks(staging)
    os.mkdir(staging, mode=0o700)
    fsync_directory(os.path.dirname(staging), strict=True)
    try:
        replace_install_entry(source, os.path.dirname(destination), staging_root=staging)
    finally:
        sync_remove_tree_no_symlinks(staging)
        fsync_directory(os.path.dirname(staging), strict=True)


def install_persisted_update_directories(
    paths: UpdateTransactionPaths,
    state: PersistedUpdateState,
    staged_directories: dict[str, str],
) -> None:
    if any(destination not in state.directory_destinations for destination in staged_directories):
        raise StateError("Update directory installation is outside the rollback inventory.")
    for slot, destination in state.destinations.items():
        source = staged_directories.get(destination)
        if source is not None:
            _replace_directory(paths, slot, source, destination)


def restore_persisted_update_state(
    paths: UpdateTransactionPaths, state: PersistedUpdateState
) -> None:
    for slot, destination in state.destinations.items():
        if slot in state.original_entries:
            source = os.path.join(paths.rollback_old_path, *slot.split("/"))
            if destination in state.directory_destinations:
                _replace_directory(paths, slot, source, destination)
            else:
                if os.path.isdir(destination):
                    sync_remove_tree_no_symlinks(destination)
                copy_install_entry(source, os.path.dirname(destination))
            fsync_install_entry(destination)
        elif os.path.lexists(destination):
            sync_remove_tree_no_symlinks(destination)
        if destination in state.directory_destinations and slot not in state.original_entries:
            staging = persisted_directory_staging(paths, slot, destination)
            if os.path.lexists(staging):
                sync_remove_tree_no_symlinks(staging)
        parent = os.path.dirname(destination)
        if os.path.isdir(parent):
            fsync_directory(parent, strict=True)
    for parent in sorted(state.absent_parents, key=len, reverse=True):
        if os.path.isdir(parent) and not os.listdir(parent):
            os.rmdir(parent)
            fsync_directory(os.path.dirname(parent), strict=True)
