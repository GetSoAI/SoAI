"""SoAI - Update transaction rollback recovery [backend/app/updater/software_update/install_transaction_recovery.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os

from app.backup.backup_removal import sync_remove_tree_no_symlinks
from app.updater.software_update.install_transaction_managed_data import (
    restore_managed_data,
)
from app.updater.software_update.install_transaction_state import (
    MANAGED_ROLLBACK_DIR,
    OLD_COMPLETE_MARKER,
    ROLLBACK_REQUIRED_MARKER,
    SUCCESS_COMPLETE_MARKER,
    TRANSACTION_PREFIX,
    UpdateTransactionPaths,
    build_rollback_top_level_ignore_patterns,
    is_preserved_top_level_item,
    marker_path,
    paths_from_transaction_directory,
)
from core.errors.exception_logging import log_exception
from core.errors.exceptions import StateError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.protocols import LoggerProtocol

__all__ = (
    "cleanup_uncommitted_transaction",
    "recover_interrupted_update_transactions",
    "restore_transaction",
)

OPERATION_APPLICATION_UPDATER_RECOVER_TRANSACTION = "application_updater.recover_update_transaction"
RECOVERY_OPERATION_EXCEPTIONS = RECOVERABLE_EXCEPTIONS + (OSError, StateError)


def _remove_non_preserved_core_items(
    *,
    base_path: str,
    top_level_ignore_patterns: tuple[str, ...],
) -> None:
    for item_name in os.listdir(base_path):
        if is_preserved_top_level_item(item_name, top_level_ignore_patterns):
            continue
        sync_remove_tree_no_symlinks(os.path.join(base_path, item_name))


def _move_directory_contents(source_path: str, destination_path: str) -> None:
    for item_name in os.listdir(source_path):
        if item_name == MANAGED_ROLLBACK_DIR:
            continue
        source_item = os.path.join(source_path, item_name)
        destination_item = os.path.join(destination_path, item_name)
        if os.path.lexists(destination_item):
            sync_remove_tree_no_symlinks(destination_item)
        os.rename(source_item, destination_item)


def restore_transaction(
    *,
    paths: UpdateTransactionPaths,
    top_level_ignore_patterns: tuple[str, ...],
    logger: LoggerProtocol,
) -> bool:
    try:
        old_complete = os.path.exists(marker_path(paths.transaction_path, OLD_COMPLETE_MARKER))
        if old_complete:
            _remove_non_preserved_core_items(
                base_path=paths.base_path,
                top_level_ignore_patterns=top_level_ignore_patterns,
            )
        restore_managed_data(paths, remove_installed=old_complete)
        _move_directory_contents(paths.rollback_old_path, paths.base_path)
        sync_remove_tree_no_symlinks(paths.transaction_path)
        logger.info("Update transaction rollback completed.")
        return True
    except RECOVERY_OPERATION_EXCEPTIONS as exception:
        log_exception(
            logger,
            exception,
            message="Failed to rollback update transaction.",
            operation=OPERATION_APPLICATION_UPDATER_RECOVER_TRANSACTION,
            details={"transaction_path": paths.transaction_path},
        )
        return False


def cleanup_uncommitted_transaction(paths: UpdateTransactionPaths, logger: LoggerProtocol) -> bool:
    try:
        sync_remove_tree_no_symlinks(paths.transaction_path)
        return True
    except RECOVERY_OPERATION_EXCEPTIONS as exception:
        log_exception(
            logger,
            exception,
            message="Failed to clean up uncommitted update transaction.",
            operation=OPERATION_APPLICATION_UPDATER_RECOVER_TRANSACTION,
            details={"transaction_path": paths.transaction_path},
            level="warning",
        )
        return False


def recover_interrupted_update_transactions(base_path: str, logger: LoggerProtocol) -> bool:
    resolved_base_path = os.path.abspath(base_path)
    if not os.path.isdir(resolved_base_path):
        return True
    recovered = True
    for item_name in os.listdir(resolved_base_path):
        if not item_name.startswith(TRANSACTION_PREFIX):
            continue
        transaction_path = os.path.join(resolved_base_path, item_name)
        if not os.path.isdir(transaction_path):
            continue
        paths = paths_from_transaction_directory(resolved_base_path, transaction_path)
        if os.path.exists(marker_path(transaction_path, SUCCESS_COMPLETE_MARKER)):
            recovered = cleanup_uncommitted_transaction(paths, logger) and recovered
            continue
        if os.path.exists(marker_path(transaction_path, ROLLBACK_REQUIRED_MARKER)):
            top_level_ignore_patterns = build_rollback_top_level_ignore_patterns(transaction_path)
            recovered = (
                restore_transaction(
                    paths=paths,
                    top_level_ignore_patterns=top_level_ignore_patterns,
                    logger=logger,
                )
                and recovered
            )
            continue
        recovered = cleanup_uncommitted_transaction(paths, logger) and recovered
    return recovered
