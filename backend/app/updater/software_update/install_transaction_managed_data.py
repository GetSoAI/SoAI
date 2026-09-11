"""SoAI - Managed data subtree update transactions [backend/app/updater/software_update/install_transaction_managed_data.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os

from app.backup.backup_removal import sync_remove_tree_no_symlinks
from app.backup.restore_destinations import ensure_restore_destination_is_safe
from app.updater.software_update.install_transaction_state import (
    CONFIG_PARENT_WAS_ABSENT_MARKER,
    DATA_PARENT_WAS_ABSENT_MARKER,
    MANAGED_CONFIG_DEFAULT_RELATIVE_COMPONENTS,
    MANAGED_DATA_PARENT,
    MANAGED_INSTALL_METADATA_RELATIVE_COMPONENTS,
    MANAGED_ROLLBACK_DIR,
    MANAGED_VENDOR_RELATIVE_COMPONENTS,
    UpdateTransactionPaths,
    marker_path,
    write_marker,
)
from core.bootstrap.install_payload_transaction import copy_install_entry, replace_install_entry
from core.errors.exceptions import StateError
from core.filesystem.atomic_write_primitives import fsync_directory
from core.filesystem.file_sync import fsync_install_entry

__all__ = (
    "install_staged_managed_data",
    "copy_managed_data_to_rollback",
    "prepare_managed_data_commit",
    "restore_managed_data",
    "validate_managed_data_destinations",
)


def _relative_path(root: str, relative_path: str) -> str:
    return os.path.join(root, *relative_path.split("/"))


def _base_data_path(paths: UpdateTransactionPaths) -> str:
    return _relative_path(paths.base_path, MANAGED_DATA_PARENT)


def _base_vendor_path(paths: UpdateTransactionPaths) -> str:
    return os.path.join(paths.base_path, *MANAGED_VENDOR_RELATIVE_COMPONENTS)


def _base_config_default_path(paths: UpdateTransactionPaths) -> str:
    return os.path.join(paths.base_path, *MANAGED_CONFIG_DEFAULT_RELATIVE_COMPONENTS)


def _staged_data_path(paths: UpdateTransactionPaths) -> str:
    return _relative_path(paths.staged_new_path, MANAGED_DATA_PARENT)


def _staged_vendor_path(paths: UpdateTransactionPaths) -> str:
    return os.path.join(paths.staged_new_path, *MANAGED_VENDOR_RELATIVE_COMPONENTS)


def _staged_config_default_path(paths: UpdateTransactionPaths) -> str:
    return os.path.join(paths.staged_new_path, *MANAGED_CONFIG_DEFAULT_RELATIVE_COMPONENTS)


def _rollback_vendor_path(paths: UpdateTransactionPaths) -> str:
    return os.path.join(
        paths.rollback_old_path,
        MANAGED_ROLLBACK_DIR,
        *MANAGED_VENDOR_RELATIVE_COMPONENTS,
    )


def _rollback_config_default_path(paths: UpdateTransactionPaths) -> str:
    return os.path.join(
        paths.rollback_old_path,
        MANAGED_ROLLBACK_DIR,
        *MANAGED_CONFIG_DEFAULT_RELATIVE_COMPONENTS,
    )


def _require_regular_directory(path: str, *, label: str) -> None:
    if not os.path.isdir(path) or os.path.islink(path):
        raise StateError(f"{label} must be a regular directory: {path}")


def validate_managed_data_destinations(paths: UpdateTransactionPaths) -> None:
    for destination in (
        _base_vendor_path(paths),
        _base_config_default_path(paths),
        os.path.join(paths.base_path, *MANAGED_INSTALL_METADATA_RELATIVE_COMPONENTS),
    ):
        ensure_restore_destination_is_safe(destination)


def prepare_managed_data_commit(paths: UpdateTransactionPaths) -> None:
    validate_managed_data_destinations(paths)
    staged_data_path = _staged_data_path(paths)
    staged_vendor_path = _staged_vendor_path(paths)
    staged_config_path = os.path.dirname(_staged_config_default_path(paths))
    _require_regular_directory(staged_data_path, label="Staged data path")
    _require_regular_directory(staged_vendor_path, label="Staged vendor path")
    _require_regular_directory(staged_config_path, label="Staged config path")
    if sorted(os.listdir(staged_data_path)) != ["config", "vendor"]:
        raise StateError("The update data payload has unexpected entries.")
    if os.listdir(staged_config_path) != ["config.default.yaml"]:
        raise StateError("The update config payload has unexpected entries.")
    staged_config_default_path = _staged_config_default_path(paths)
    if not os.path.isfile(staged_config_default_path) or os.path.islink(staged_config_default_path):
        raise StateError("The staged default configuration must be a regular file.")
    base_data_path = _base_data_path(paths)
    if not os.path.lexists(base_data_path):
        write_marker(paths.transaction_path, DATA_PARENT_WAS_ABSENT_MARKER)
        return
    _require_regular_directory(base_data_path, label="Installed data path")
    base_config_path = os.path.dirname(_base_config_default_path(paths))
    if os.path.lexists(base_config_path):
        _require_regular_directory(base_config_path, label="Installed config path")
    else:
        write_marker(paths.transaction_path, CONFIG_PARENT_WAS_ABSENT_MARKER)
    base_vendor_path = _base_vendor_path(paths)
    if os.path.lexists(base_vendor_path):
        _require_regular_directory(base_vendor_path, label="Installed vendor path")
    base_config_default_path = _base_config_default_path(paths)
    if os.path.lexists(base_config_default_path) and (
        not os.path.isfile(base_config_default_path) or os.path.islink(base_config_default_path)
    ):
        raise StateError("The installed default configuration must be a regular file.")


def copy_managed_data_to_rollback(paths: UpdateTransactionPaths) -> None:
    metadata_path = os.path.join(paths.base_path, *MANAGED_INSTALL_METADATA_RELATIVE_COMPONENTS)
    if os.path.lexists(metadata_path):
        metadata_storage = os.path.join(paths.rollback_old_path, MANAGED_ROLLBACK_DIR)
        os.makedirs(metadata_storage, mode=0o700, exist_ok=True)
        copy_install_entry(metadata_path, metadata_storage)
        fsync_install_entry(
            os.path.join(metadata_storage, *MANAGED_INSTALL_METADATA_RELATIVE_COMPONENTS)
        )
    managed_paths = (
        (_base_vendor_path(paths), _rollback_vendor_path(paths)),
        (_base_config_default_path(paths), _rollback_config_default_path(paths)),
    )
    for source_path, destination_path in managed_paths:
        if not os.path.lexists(source_path):
            continue
        os.makedirs(os.path.dirname(destination_path), mode=0o700, exist_ok=True)
        copy_install_entry(source_path, os.path.dirname(destination_path))
        fsync_directory(os.path.dirname(destination_path), strict=True)
        fsync_directory(os.path.dirname(source_path), strict=True)


def install_staged_managed_data(paths: UpdateTransactionPaths) -> None:
    base_data_path = _base_data_path(paths)
    if not os.path.exists(base_data_path):
        os.makedirs(base_data_path, mode=0o700, exist_ok=False)
    base_config_path = os.path.dirname(_base_config_default_path(paths))
    os.makedirs(base_config_path, mode=0o700, exist_ok=True)
    managed_paths = (
        (_staged_vendor_path(paths), _base_vendor_path(paths)),
        (_staged_config_default_path(paths), _base_config_default_path(paths)),
    )
    for source_path, destination_path in managed_paths:
        replace_install_entry(
            source_path, os.path.dirname(destination_path), staging_root=paths.transaction_path
        )
        fsync_directory(os.path.dirname(destination_path), strict=True)
        fsync_directory(os.path.dirname(source_path), strict=True)
    sync_remove_tree_no_symlinks(_staged_data_path(paths))


def restore_managed_data(
    paths: UpdateTransactionPaths,
    *,
    remove_installed: bool,
) -> None:
    managed_paths = (
        (_base_vendor_path(paths), _rollback_vendor_path(paths)),
        (_base_config_default_path(paths), _rollback_config_default_path(paths)),
        (
            os.path.join(paths.base_path, *MANAGED_INSTALL_METADATA_RELATIVE_COMPONENTS),
            os.path.join(
                paths.rollback_old_path,
                MANAGED_ROLLBACK_DIR,
                *MANAGED_INSTALL_METADATA_RELATIVE_COMPONENTS,
            ),
        ),
    )
    for base_path, rollback_path in managed_paths:
        if not os.path.lexists(rollback_path):
            if remove_installed and os.path.lexists(base_path):
                sync_remove_tree_no_symlinks(base_path)
            continue
        os.makedirs(os.path.dirname(base_path), mode=0o700, exist_ok=True)
        replace_install_entry(
            rollback_path, os.path.dirname(base_path), staging_root=paths.transaction_path
        )
        fsync_install_entry(base_path)
    base_config_path = os.path.dirname(_base_config_default_path(paths))
    config_parent_was_absent = os.path.exists(
        marker_path(paths.transaction_path, CONFIG_PARENT_WAS_ABSENT_MARKER)
    ) or os.path.exists(marker_path(paths.transaction_path, DATA_PARENT_WAS_ABSENT_MARKER))
    if (
        config_parent_was_absent
        and os.path.isdir(base_config_path)
        and not os.listdir(base_config_path)
    ):
        os.rmdir(base_config_path)
    if os.path.exists(marker_path(paths.transaction_path, DATA_PARENT_WAS_ABSENT_MARKER)):
        base_data_path = _base_data_path(paths)
        if os.path.isdir(base_data_path) and not os.listdir(base_data_path):
            os.rmdir(base_data_path)
