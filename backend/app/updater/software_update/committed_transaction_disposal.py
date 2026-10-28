"""SoAI - Background disposal of committed update transaction storage [backend/app/updater/software_update/committed_transaction_disposal.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import os

from app.backup.backup_removal import sync_remove_tree_no_symlinks
from app.installation_transaction_admission import (
    TRANSACTION_CLEANUP_PREFIX,
    TRANSACTION_PREFIX,
    list_update_transaction_storage,
)
from app.updater.software_update.activation_state import (
    activation_commit_lock_path,
    find_pending_update_activation,
    persist_committed_activation_result,
    read_update_activation_identity,
    require_update_candidate_stopped,
    validate_update_recovery_evidence,
)
from app.updater.software_update.install_transaction_cleanup import (
    cleanup_update_transaction,
    finish_update_cleanup,
    verify_cleanup_diagnostics,
)
from app.updater.software_update.install_transaction_inventory import require_rollback_inventory
from app.updater.software_update.install_transaction_recovery_plan import (
    UpdateRecoveryAction,
    plan_transaction_recovery,
)
from app.updater.software_update.install_transaction_state import (
    OLD_COMPLETE_MARKER,
    SUCCESS_COMPLETE_MARKER,
    UpdateTransactionPaths,
    marker_path,
    paths_from_transaction_directory,
)
from app.updater.software_update.update_lock import guarded_software_update_recovery
from core.bootstrap.filename_normalization import normalize_installed_filenames
from core.bootstrap.install_payload import validate_existing_install_edition
from core.bootstrap.lock import acquire_interprocess_lock
from core.errors.exception_logging import log_exception
from core.errors.exceptions import ConflictError, SecurityError, StateError, ValidationError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.filesystem.atomic_write_primitives import fsync_directory
from core.logging.protocols import LoggerProtocol
from core.tasks.software_update_result import (
    clear_software_update_result,
    read_software_update_result,
)
from core.timing.constants import (
    BACKGROUND_TIMEOUT_SEC,
    CONTROL_TIMEOUT_SEC,
    LONG_IDLE_TIMEOUT_SEC,
    STANDARD_DELAY_SEC,
)
from core.timing.monotonic import monotonic_ms

__all__ = (
    "inspect_update_transaction_for_all_data_uninstall",
    "dispose_update_transaction_for_all_data_uninstall",
    "discard_unstarted_installer_activation",
    "dispose_committed_update_storage",
    "dispose_committed_update_storage_once",
)

DISPOSAL_EXCEPTIONS = RECOVERABLE_EXCEPTIONS + (
    OSError,
    ConflictError,
    SecurityError,
    StateError,
    ValidationError,
)
OPERATION_DISPOSE_COMMITTED_UPDATE_STORAGE = "application_updater.dispose_committed_update_storage"


def dispose_update_transaction_for_all_data_uninstall(
    base_path: str, logger: LoggerProtocol, *, edition: str, installation_lock_held: bool = False
) -> None:
    with guarded_software_update_recovery(base_path, installation_lock_held=installation_lock_held):
        paths = inspect_update_transaction_for_all_data_uninstall(base_path, edition=edition)
        if paths is None:
            return
        if os.path.basename(paths.transaction_path).startswith(TRANSACTION_CLEANUP_PREFIX):
            finish_update_cleanup(base_path, paths.transaction_path, logger)
            return
        require_update_candidate_stopped(paths)
        if not cleanup_update_transaction(paths, logger) or os.path.lexists(paths.transaction_path):
            raise StateError(
                "Uninstall transaction disposal did not complete; diagnostic evidence was retained."
            )


def inspect_update_transaction_for_all_data_uninstall(
    base_path: str, *, edition: str
) -> UpdateTransactionPaths | None:
    validate_existing_install_edition(base_path, edition)
    storage = list_update_transaction_storage(base_path)
    if not storage:
        return None
    paths = paths_from_transaction_directory(base_path, storage[0])
    if os.path.basename(storage[0]).startswith(TRANSACTION_CLEANUP_PREFIX):
        verify_cleanup_diagnostics(base_path, paths.transaction_path)
        return paths
    validate_update_recovery_evidence(paths)
    if read_update_activation_identity(paths).edition != edition:
        raise StateError("Uninstall transaction disposal edition conflicts with the installation.")
    inventory = require_rollback_inventory(
        paths,
        old_complete=os.path.exists(marker_path(paths.transaction_path, OLD_COMPLETE_MARKER)),
        verify_content=False,
    )
    if inventory is None:
        raise StateError("Uninstall transaction disposal is missing its path ownership inventory.")
    return paths


def discard_unstarted_installer_activation(
    base_path: str, *, installation_lock_held: bool = False
) -> bool:
    resolved_base_path = os.path.abspath(base_path)
    with acquire_interprocess_lock(
        activation_commit_lock_path(resolved_base_path), timeout_sec=CONTROL_TIMEOUT_SEC
    ):
        with guarded_software_update_recovery(
            resolved_base_path, installation_lock_held=installation_lock_held
        ):
            pending = find_pending_update_activation(resolved_base_path)
            if pending is None:
                return False
            try:
                action = plan_transaction_recovery(pending.paths, allow_pending_activation=True)
            except StateError:
                return False
            if action is not UpdateRecoveryAction.ACTIVATE:
                return False
            sync_remove_tree_no_symlinks(pending.paths.transaction_path)
            fsync_directory(resolved_base_path, strict=True)
            result = read_software_update_result(resolved_base_path)
            if result is not None and result.task_id == pending.task_id:
                clear_software_update_result(resolved_base_path)
    return True


def dispose_committed_update_storage_once(base_path: str, logger: LoggerProtocol) -> bool:
    resolved_base_path = os.path.abspath(base_path)
    with guarded_software_update_recovery(resolved_base_path):
        names = sorted(
            name
            for name in os.listdir(resolved_base_path)
            if name.startswith((TRANSACTION_PREFIX, TRANSACTION_CLEANUP_PREFIX))
        )
        if not names:
            normalize_installed_filenames(resolved_base_path)
            return True
        committed: list[UpdateTransactionPaths] = []
        for name in names:
            if name.startswith(TRANSACTION_CLEANUP_PREFIX):
                continue
            transaction_path = os.path.join(resolved_base_path, name)
            if os.path.islink(transaction_path) or not os.path.isdir(transaction_path):
                return True
            if not os.path.isfile(marker_path(transaction_path, SUCCESS_COMPLETE_MARKER)):
                return True
            paths = paths_from_transaction_directory(resolved_base_path, transaction_path)
            if (
                plan_transaction_recovery(paths, allow_pending_activation=False)
                is not UpdateRecoveryAction.CLEAN_COMMITTED
            ):
                return True
            committed.append(paths)
        disposed = True
        for name in names:
            if not name.startswith(TRANSACTION_CLEANUP_PREFIX):
                continue
            cleanup_path = os.path.join(resolved_base_path, name)
            finish_update_cleanup(resolved_base_path, cleanup_path, logger)
        for paths in committed:
            persist_committed_activation_result(paths)
            disposed = (
                cleanup_update_transaction(paths, logger, deferrable=True, log_deferral=False)
                and disposed
            )
        return disposed


async def dispose_committed_update_storage(
    base_path: str, logger: LoggerProtocol, shutdown_event: asyncio.Event
) -> None:
    deadline_ms = monotonic_ms() + int(LONG_IDLE_TIMEOUT_SEC * 1000)
    delay_sec = STANDARD_DELAY_SEC
    while not shutdown_event.is_set():
        try:
            if await asyncio.to_thread(dispose_committed_update_storage_once, base_path, logger):
                logger.info("Installation filename and transaction cleanup finished.")
                return
        except DISPOSAL_EXCEPTIONS as exception:
            if not isinstance(exception, OSError):
                log_exception(
                    logger,
                    exception,
                    message=(
                        "Installation filename cleanup requires attention; "
                        "recovery evidence remains available for the next startup."
                    ),
                    operation=OPERATION_DISPOSE_COMMITTED_UPDATE_STORAGE,
                    level="warning",
                )
                return
            logger.debug("Committed update transaction storage is still in use: %s", str(exception))
        if monotonic_ms() >= deadline_ms:
            logger.info("Installation cleanup remains pending; the next startup retries it.")
            return
        try:
            await asyncio.wait_for(shutdown_event.wait(), timeout=delay_sec)
        except TimeoutError:
            delay_sec = min(delay_sec * 2.0, BACKGROUND_TIMEOUT_SEC)
