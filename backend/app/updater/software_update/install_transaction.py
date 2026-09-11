"""SoAI - Transactional software update installation [backend/app/updater/software_update/install_transaction.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os

from app.updater.software_update.activation_state import (
    persist_committed_activation_result,
)
from app.updater.software_update.install_transaction_inventory import (
    prepare_update_rollback,
    require_rollback_inventory,
)
from app.updater.software_update.install_transaction_managed_data import (
    install_staged_managed_data,
)
from app.updater.software_update.install_transaction_recovery import (
    restore_transaction,
)
from app.updater.software_update.install_transaction_state import (
    ACTIVATION_FAILED_MARKER,
    NEW_COMPLETE_MARKER,
    OLD_COMPLETE_MARKER,
    ROLLBACK_COMPLETE_MARKER,
    ROLLBACK_REQUIRED_MARKER,
    SUCCESS_COMPLETE_MARKER,
    AppliedUpdateTransaction,
    UpdateTransactionPaths,
    build_rollback_top_level_ignore_patterns,
    cleanup_update_transaction,
    marker_path,
    paths_from_transaction_directory,
    remove_marker,
    validate_transaction_markers,
    write_marker,
)
from app.updater.software_update.install_transaction_state_transfer import (
    install_persisted_update_directories,
)
from core.bootstrap.install_payload_transaction import replace_install_entry
from core.errors.exception_logging import log_exception
from core.errors.exceptions import (
    InsufficientDiskSpaceError,
    SecurityError,
    StateError,
    ValidationError,
)
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.filesystem.atomic_write_primitives import fsync_directory
from core.logging.protocols import LoggerProtocol

__all__ = (
    "AppliedUpdateTransaction",
    "commit_staged_update",
    "finalize_update_transaction",
)

OPERATION_APPLICATION_UPDATER_FINALIZE_TRANSACTION = (
    "application_updater.finalize_update_transaction"
)
TRANSACTION_COMMIT_EXCEPTIONS = RECOVERABLE_EXCEPTIONS + (
    OSError,
    StateError,
    InsufficientDiskSpaceError,
    SecurityError,
)
TRANSACTION_CLEANUP_EXCEPTIONS = RECOVERABLE_EXCEPTIONS + (
    OSError,
    StateError,
    SecurityError,
    ValidationError,
)


def commit_staged_update(
    *,
    paths: UpdateTransactionPaths,
    top_level_ignore_patterns: tuple[str, ...],
    logger: LoggerProtocol,
    edition: str,
    state_files: tuple[str, ...] = (),
    state_directories: tuple[str, ...] = (),
    staged_directories: dict[str, str] | None = None,
) -> AppliedUpdateTransaction:
    try:
        prepare_update_rollback(
            paths,
            edition=edition,
            state_files=state_files,
            state_directories=state_directories,
        )
        write_marker(paths.transaction_path, ROLLBACK_REQUIRED_MARKER)
        if staged_directories:
            inventory = require_rollback_inventory(paths, old_complete=True)
            if inventory is None:
                raise StateError("Configured directory replacement requires a rollback inventory.")
            install_persisted_update_directories(
                paths, inventory.persisted_state, staged_directories
            )
        install_staged_managed_data(paths)
        for item_name in os.listdir(paths.staged_new_path):
            replace_install_entry(
                os.path.join(paths.staged_new_path, item_name),
                paths.base_path,
                staging_root=paths.transaction_path,
            )
            fsync_directory(paths.base_path, strict=True)
            fsync_directory(paths.staged_new_path, strict=True)
        write_marker(paths.transaction_path, NEW_COMPLETE_MARKER)
        return AppliedUpdateTransaction(
            base_path=paths.base_path,
            transaction_path=paths.transaction_path,
        )
    except TRANSACTION_COMMIT_EXCEPTIONS:
        if os.path.exists(marker_path(paths.transaction_path, ROLLBACK_REQUIRED_MARKER)):
            restore_transaction(
                paths=paths,
                top_level_ignore_patterns=top_level_ignore_patterns,
                logger=logger,
            )
        else:
            cleanup_update_transaction(paths, logger)
        raise


def _finalize_successful_transaction(
    *,
    paths: UpdateTransactionPaths,
    logger: LoggerProtocol,
) -> bool:
    committed = False
    try:
        validate_transaction_markers(paths.transaction_path)
        if os.path.exists(marker_path(paths.transaction_path, ACTIVATION_FAILED_MARKER)):
            raise StateError("A failed candidate cannot be committed as an activated update.")
        if os.path.exists(marker_path(paths.transaction_path, ROLLBACK_COMPLETE_MARKER)):
            raise StateError("A restored update cannot be committed as an activated candidate.")
        if os.path.exists(marker_path(paths.transaction_path, SUCCESS_COMPLETE_MARKER)):
            persist_committed_activation_result(paths)
            cleanup_update_transaction(paths, logger)
            return True
        if not all(
            os.path.exists(marker_path(paths.transaction_path, marker))
            for marker in (OLD_COMPLETE_MARKER, NEW_COMPLETE_MARKER, ROLLBACK_REQUIRED_MARKER)
        ):
            raise StateError("Update replacement is incomplete; commit evidence was preserved.")
        require_rollback_inventory(paths, old_complete=True)
        write_marker(paths.transaction_path, SUCCESS_COMPLETE_MARKER)
        committed = True
        persist_committed_activation_result(paths)
        remove_marker(paths.transaction_path, ROLLBACK_REQUIRED_MARKER)
        cleanup_update_transaction(paths, logger)
        return True
    except TRANSACTION_CLEANUP_EXCEPTIONS as exception:
        if committed:
            log_exception(
                logger,
                exception,
                message="Update transaction is committed but cleanup failed.",
                operation=OPERATION_APPLICATION_UPDATER_FINALIZE_TRANSACTION,
                details={"transaction_path": paths.transaction_path},
                level="warning",
            )
            return True
        log_exception(
            logger,
            exception,
            message="Failed to finalize successful update transaction.",
            operation=OPERATION_APPLICATION_UPDATER_FINALIZE_TRANSACTION,
            details={"transaction_path": paths.transaction_path},
        )
        return False


def finalize_update_transaction(
    *,
    transaction: AppliedUpdateTransaction,
    update_success: bool,
    logger: LoggerProtocol,
) -> bool:
    paths = paths_from_transaction_directory(
        transaction.base_path,
        transaction.transaction_path,
    )
    top_level_ignore_patterns = build_rollback_top_level_ignore_patterns(paths.transaction_path)
    if not os.path.isdir(paths.transaction_path):
        return True
    if update_success:
        return _finalize_successful_transaction(paths=paths, logger=logger)
    return restore_transaction(
        paths=paths,
        top_level_ignore_patterns=top_level_ignore_patterns,
        logger=logger,
    )
