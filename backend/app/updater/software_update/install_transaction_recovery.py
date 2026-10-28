"""SoAI - Update transaction rollback recovery [backend/app/updater/software_update/install_transaction_recovery.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
import sys

from app.backup.restore_journal import require_no_pending_restore
from app.installation_transaction_admission import (
    TRANSACTION_CLEANUP_PREFIX,
    list_update_transaction_storage,
)
from app.updater.software_update.activation_state import (
    activation_commit_lock_path,
    persist_committed_activation_result,
    persist_failed_activation_result,
    require_update_candidate_stopped,
    validate_update_recovery_evidence,
)
from app.updater.software_update.install_transaction_cleanup import (
    cleanup_update_transaction,
    finish_update_cleanup,
)
from app.updater.software_update.install_transaction_inventory import require_rollback_inventory
from app.updater.software_update.install_transaction_managed_data import (
    restore_managed_data,
    validate_managed_data_destinations,
)
from app.updater.software_update.install_transaction_recovery_plan import (
    UpdateRecoveryAction,
    plan_transaction_recovery,
)
from app.updater.software_update.install_transaction_snapshot_evidence import (
    UpdateSnapshotOutcomeError,
)
from app.updater.software_update.install_transaction_state import (
    OLD_COMPLETE_MARKER,
    ROLLBACK_COMPLETE_MARKER,
    ROLLBACK_REQUIRED_MARKER,
    SUCCESS_COMPLETE_MARKER,
    UpdateTransactionPaths,
    build_rollback_top_level_ignore_patterns,
    marker_path,
    paths_from_transaction_directory,
    write_marker,
)
from app.updater.software_update.install_transaction_state_transfer import (
    remove_candidate_application_roots,
    restore_application_update_state,
    restore_persisted_update_state,
)
from app.updater.software_update.update_lock import guarded_software_update_recovery
from core.bootstrap.filename_normalization import normalized_filenames_are_usable
from core.bootstrap.install_locks import inherited_install_lock_is_valid
from core.bootstrap.lock import acquire_interprocess_lock
from core.errors.exception_logging import log_exception
from core.errors.exceptions import (
    ConflictError,
    SecurityError,
    SoAIError,
    StateError,
    ValidationError,
)
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.filesystem.atomic_write_primitives import fsync_directory
from core.logging.protocols import LoggerProtocol
from core.logging.trace import get_logger
from core.meta.paths import join_data_abs
from core.timing.constants import CONTROL_TIMEOUT_SEC

__all__ = (
    "UpdateRepairRequiredError",
    "recover_interrupted_update_transactions",
    "recover_unarmed_update_transaction",
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


class UpdateRepairRequiredError(StateError): ...


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
                cleaned = cleanup_update_transaction(
                    paths, logger, retain_storage=not cleanup_after_recovery
                )
                if not cleaned and os.path.exists(
                    marker_path(paths.transaction_path, SUCCESS_COMPLETE_MARKER)
                ):
                    return normalized_filenames_are_usable(paths.base_path)
                return cleaned
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
                remove_candidate_application_roots(
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
            restore_application_update_state(paths, persisted_state_present=inventory is not None)
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
    defer_to_inherited_installer: bool = False,
    retained_installation_root: str | None = None,
    installation_lock_held: bool = False,
) -> bool:
    resolved_base_path = os.path.abspath(base_path)
    if not os.path.isdir(resolved_base_path):
        return True
    try:
        with guarded_software_update_recovery(
            resolved_base_path, installation_lock_held=installation_lock_held
        ):
            if defer_to_inherited_installer and inherited_install_lock_is_valid(
                join_data_abs(resolved_base_path, "state", "locks", "soai.install.lock.d")
            ):
                return True
            recovered = True
            for transaction_path in list_update_transaction_storage(resolved_base_path):
                item_name = os.path.basename(transaction_path)
                if item_name.startswith(TRANSACTION_CLEANUP_PREFIX):
                    if not cleanup_after_recovery:
                        continue
                    cleanup_path = os.path.join(resolved_base_path, item_name)
                    try:
                        finish_update_cleanup(resolved_base_path, cleanup_path, logger)
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
                if os.path.islink(transaction_path) or not os.path.isdir(transaction_path):
                    logger.error(
                        "Update transaction storage is not a regular directory; preserve it for repair."
                    )
                    recovered = False
                    continue
                paths = paths_from_transaction_directory(resolved_base_path, transaction_path)
                try:
                    action = plan_transaction_recovery(
                        paths,
                        allow_pending_activation=allow_pending_activation,
                        retained_installation_root=retained_installation_root,
                    )
                    if action is UpdateRecoveryAction.ACTIVATE:
                        continue
                    if action is UpdateRecoveryAction.CLEAN_COMMITTED:
                        persist_committed_activation_result(paths)
                        cleaned = cleanup_update_transaction(
                            paths, logger, retain_storage=not cleanup_after_recovery
                        )
                        if not cleaned and not normalized_filenames_are_usable(resolved_base_path):
                            recovered = False
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


def recover_unarmed_update_transaction(
    paths: UpdateTransactionPaths,
    logger: LoggerProtocol,
    *,
    cause: BaseException,
    retained_installation_root: str | None = None,
    cleanup_after_recovery: bool = True,
    installation_lock_held: bool = False,
) -> None:
    if not os.path.exists(paths.transaction_path) or os.path.exists(
        marker_path(paths.transaction_path, ROLLBACK_REQUIRED_MARKER)
    ):
        return
    try:
        with guarded_software_update_recovery(
            paths.base_path, installation_lock_held=installation_lock_held
        ):
            if list_update_transaction_storage(paths.base_path) != (paths.transaction_path,):
                raise StateError("Installer abort does not match the unfinished transaction.")
            action = plan_transaction_recovery(
                paths,
                allow_pending_activation=False,
                retained_installation_root=retained_installation_root,
            )
            if action is not UpdateRecoveryAction.CLEAN_INTERRUPTED:
                raise StateError("Installer abort is no longer an unarmed preparation.")
            persist_failed_activation_result(paths)
            if cleanup_after_recovery and (
                not cleanup_update_transaction(paths, logger)
                or os.path.lexists(paths.transaction_path)
            ):
                raise StateError(
                    "Installer preparation abort did not reach its cleanup postcondition."
                )
    except RECOVERY_OPERATION_EXCEPTIONS as exception:
        exception.add_note(f"Interrupted preparation cause: {type(cause).__name__}")
        failure_cause = cause if isinstance(cause, UpdateSnapshotOutcomeError) else exception
        raise UpdateRepairRequiredError(
            "Update preparation recovery requires repair; the transaction was retained.",
            details=failure_cause.details if isinstance(failure_cause, SoAIError) else None,
            cause=failure_cause,
        ) from exception


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: update recovery INSTALL_ROOT")
    raise SystemExit(
        0
        if recover_interrupted_update_transactions(
            sys.argv[1],
            get_logger(LOGGER_NAME),
            allow_pending_activation=True,
            defer_to_inherited_installer=True,
        )
        else 1
    )
