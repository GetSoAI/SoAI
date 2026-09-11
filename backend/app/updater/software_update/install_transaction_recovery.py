"""SoAI - Update transaction rollback recovery [backend/app/updater/software_update/install_transaction_recovery.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
import sys

from app.backup.backup_removal import sync_remove_tree_no_symlinks
from app.backup.restore_journal import require_no_pending_restore
from app.installation_transaction_admission import (
    TRANSACTION_CLEANUP_PREFIX,
    TRANSACTION_PREFIX,
)
from app.updater.software_update.activation_state import (
    activation_commit_lock_path,
    persist_committed_activation_result,
    persist_failed_activation_result,
    require_update_candidate_stopped,
    validate_update_recovery_evidence,
)
from app.updater.software_update.install_transaction_inventory import require_rollback_inventory
from app.updater.software_update.install_transaction_managed_data import (
    restore_managed_data,
    validate_managed_data_destinations,
)
from app.updater.software_update.install_transaction_persisted_state import (
    PERSISTED_STATE_DIRECTORY,
)
from app.updater.software_update.install_transaction_recovery_plan import (
    UpdateRecoveryAction,
    plan_transaction_recovery,
)
from app.updater.software_update.install_transaction_state import (
    MANAGED_INSTALL_METADATA_RELATIVE_COMPONENTS,
    MANAGED_ROLLBACK_DIR,
    OLD_COMPLETE_MARKER,
    ROLLBACK_COMPLETE_MARKER,
    SUCCESS_COMPLETE_MARKER,
    UpdateTransactionPaths,
    build_rollback_top_level_ignore_patterns,
    cleanup_update_transaction,
    is_preserved_top_level_item,
    marker_path,
    paths_from_transaction_directory,
    write_marker,
)
from app.updater.software_update.install_transaction_state_transfer import (
    restore_persisted_update_state,
)
from app.updater.software_update.update_lock import guarded_software_update_recovery
from core.bootstrap.install_payload_transaction import replace_install_entry
from core.bootstrap.lock import acquire_interprocess_lock
from core.errors.exception_logging import log_exception
from core.errors.exceptions import ConflictError, SecurityError, StateError, ValidationError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.filesystem.atomic_write_primitives import fsync_directory
from core.filesystem.file_sync import fsync_install_entry
from core.logging.protocols import LoggerProtocol
from core.logging.trace import get_logger
from core.timing.constants import CONTROL_TIMEOUT_SEC

__all__ = (
    "recover_interrupted_update_transactions",
    "restore_transaction",
)

OPERATION_APPLICATION_UPDATER_RECOVER_TRANSACTION = "application_updater.recover_update_transaction"
LOGGER_NAME = "SoAI.app.updater.install_transaction_recovery"
RECOVERY_OPERATION_EXCEPTIONS = RECOVERABLE_EXCEPTIONS + (
    OSError,
    ConflictError,
    SecurityError,
    StateError,
    ValidationError,
)


def _remove_candidate_roots_without_originals(
    *,
    base_path: str,
    top_level_ignore_patterns: tuple[str, ...],
    replacement_roots: tuple[str, ...] | None,
    rollback_old_path: str,
) -> None:
    for item_name in os.listdir(base_path) if replacement_roots is None else replacement_roots:
        if (item_name,) == MANAGED_INSTALL_METADATA_RELATIVE_COMPONENTS:
            continue
        if is_preserved_top_level_item(item_name, top_level_ignore_patterns):
            continue
        if os.path.lexists(os.path.join(rollback_old_path, item_name)):
            continue
        sync_remove_tree_no_symlinks(os.path.join(base_path, item_name))


def _restore_directory_contents(
    source_path: str, destination_path: str, *, staging_root: str, persisted_state_present: bool
) -> None:
    for item_name in os.listdir(source_path):
        if item_name == MANAGED_ROLLBACK_DIR or (
            persisted_state_present and item_name == PERSISTED_STATE_DIRECTORY
        ):
            continue
        source_item = os.path.join(source_path, item_name)
        destination_item = os.path.join(destination_path, item_name)
        replace_install_entry(source_item, destination_path, staging_root=staging_root)
        fsync_install_entry(destination_item)


def restore_transaction(
    *,
    paths: UpdateTransactionPaths,
    top_level_ignore_patterns: tuple[str, ...],
    logger: LoggerProtocol,
    cleanup_after_recovery: bool = True,
) -> bool:
    try:
        with acquire_interprocess_lock(
            activation_commit_lock_path(paths.base_path), timeout_sec=CONTROL_TIMEOUT_SEC
        ):
            validate_update_recovery_evidence(paths)
            require_no_pending_restore(paths.base_path)
            if any(
                os.path.exists(marker_path(paths.transaction_path, marker))
                for marker in (SUCCESS_COMPLETE_MARKER, ROLLBACK_COMPLETE_MARKER)
            ):
                if os.path.exists(marker_path(paths.transaction_path, SUCCESS_COMPLETE_MARKER)):
                    persist_committed_activation_result(paths)
                else:
                    persist_failed_activation_result(paths)
                if not cleanup_after_recovery:
                    return True
                return cleanup_update_transaction(paths, logger)
            require_update_candidate_stopped(paths)
            if not os.path.isdir(paths.rollback_old_path) or os.path.islink(
                paths.rollback_old_path
            ):
                raise StateError(
                    "Update rollback originals are unavailable; preserve the transaction for repair."
                )
            old_complete = os.path.exists(marker_path(paths.transaction_path, OLD_COMPLETE_MARKER))
            inventory = require_rollback_inventory(paths, old_complete=old_complete)
            validate_managed_data_destinations(paths)
            if old_complete:
                _remove_candidate_roots_without_originals(
                    base_path=paths.base_path,
                    top_level_ignore_patterns=top_level_ignore_patterns,
                    replacement_roots=(
                        inventory.replacement_roots if inventory is not None else None
                    ),
                    rollback_old_path=paths.rollback_old_path,
                )
            restore_managed_data(paths, remove_installed=old_complete)
            if inventory is not None:
                restore_persisted_update_state(paths, inventory.persisted_state)
            _restore_directory_contents(
                paths.rollback_old_path,
                paths.base_path,
                staging_root=paths.transaction_path,
                persisted_state_present=inventory is not None,
            )
            fsync_directory(paths.base_path, strict=True)
            write_marker(paths.transaction_path, ROLLBACK_COMPLETE_MARKER)
            persist_failed_activation_result(paths)
            if cleanup_after_recovery and not cleanup_update_transaction(paths, logger):
                return False
            if cleanup_after_recovery:
                logger.info("Update transaction rollback completed.")
            else:
                logger.info("Update restoration completed; cleanup awaits recovery process exit.")
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


def recover_interrupted_update_transactions(
    base_path: str,
    logger: LoggerProtocol,
    *,
    allow_pending_activation: bool = False,
    cleanup_after_recovery: bool = True,
    allow_restoration: bool = True,
) -> bool:
    resolved_base_path = os.path.abspath(base_path)
    if not os.path.isdir(resolved_base_path):
        return True
    try:
        with guarded_software_update_recovery(resolved_base_path):
            recovered = True
            for item_name in os.listdir(resolved_base_path):
                if item_name.startswith(TRANSACTION_CLEANUP_PREFIX):
                    if not cleanup_after_recovery:
                        continue
                    cleanup_path = os.path.join(resolved_base_path, item_name)
                    try:
                        sync_remove_tree_no_symlinks(cleanup_path)
                        fsync_directory(resolved_base_path, strict=True)
                    except RECOVERY_OPERATION_EXCEPTIONS as exception:
                        log_exception(
                            logger,
                            exception,
                            message="Failed to finish update transaction cleanup.",
                            operation=OPERATION_APPLICATION_UPDATER_RECOVER_TRANSACTION,
                            details={"transaction_path": cleanup_path},
                        )
                        recovered = False
                    continue
                if not item_name.startswith(TRANSACTION_PREFIX):
                    continue
                transaction_path = os.path.join(resolved_base_path, item_name)
                if os.path.islink(transaction_path) or not os.path.isdir(transaction_path):
                    logger.error(
                        "Update transaction storage is not a regular directory; preserve it for repair."
                    )
                    recovered = False
                    continue
                paths = paths_from_transaction_directory(resolved_base_path, transaction_path)
                try:
                    action = plan_transaction_recovery(
                        paths, allow_pending_activation=allow_pending_activation
                    )
                    if action is UpdateRecoveryAction.ACTIVATE:
                        continue
                    if action is UpdateRecoveryAction.CLEAN_COMMITTED:
                        persist_committed_activation_result(paths)
                        if cleanup_after_recovery:
                            recovered = cleanup_update_transaction(paths, logger) and recovered
                        continue
                    if action is UpdateRecoveryAction.RESTORE:
                        if not allow_restoration:
                            raise StateError(
                                "Update restoration requires launcher exit before recovery."
                            )
                        recovered = (
                            restore_transaction(
                                paths=paths,
                                top_level_ignore_patterns=build_rollback_top_level_ignore_patterns(
                                    transaction_path
                                ),
                                logger=logger,
                                cleanup_after_recovery=cleanup_after_recovery,
                            )
                            and recovered
                        )
                        continue
                    if action is not UpdateRecoveryAction.CLEAN_INTERRUPTED:
                        raise StateError(
                            "Update recovery action is unsupported; preserve evidence for repair."
                        )
                except RECOVERY_OPERATION_EXCEPTIONS as exception:
                    log_exception(
                        logger,
                        exception,
                        message="Update phase evidence is invalid; recovery requires repair.",
                        operation=OPERATION_APPLICATION_UPDATER_RECOVER_TRANSACTION,
                        details={"transaction_path": transaction_path},
                    )
                    recovered = False
                    continue
                persist_failed_activation_result(paths)
                if cleanup_after_recovery:
                    recovered = cleanup_update_transaction(paths, logger) and recovered
            return recovered
    except RECOVERY_OPERATION_EXCEPTIONS as exception:
        log_exception(
            logger,
            exception,
            message="Update recovery could not acquire exclusive installation access.",
            operation=OPERATION_APPLICATION_UPDATER_RECOVER_TRANSACTION,
        )
        return False


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: update recovery INSTALL_ROOT")
    raise SystemExit(
        0
        if recover_interrupted_update_transactions(
            sys.argv[1], get_logger(LOGGER_NAME), allow_pending_activation=True
        )
        else 1
    )
