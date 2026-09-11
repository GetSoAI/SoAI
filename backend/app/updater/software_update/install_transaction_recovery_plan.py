"""SoAI - Read-only update recovery decisions [backend/app/updater/software_update/install_transaction_recovery_plan.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
from enum import Enum

from app.backup.restore_journal import require_no_pending_restore
from app.installation_transaction_admission import TRANSACTION_PREFIX
from app.updater.software_update.activation_state import (
    activation_process_path,
    read_pending_update_activation,
    require_update_candidate_stopped,
    validate_update_recovery_evidence,
)
from app.updater.software_update.install_transaction_inventory import require_rollback_inventory
from app.updater.software_update.install_transaction_managed_data import (
    validate_managed_data_destinations,
)
from app.updater.software_update.install_transaction_state import (
    ACTIVATION_FAILED_MARKER,
    OLD_COMPLETE_MARKER,
    PREPARING_MARKER,
    ROLLBACK_COMPLETE_MARKER,
    ROLLBACK_REQUIRED_MARKER,
    SUCCESS_COMPLETE_MARKER,
    UpdateTransactionPaths,
    marker_path,
    paths_from_transaction_directory,
)
from app.updater.software_update.update_lock import guarded_software_update_recovery
from core.errors.exceptions import StateError

__all__ = (
    "UpdateRecoveryAction",
    "inspect_update_restorations",
    "plan_transaction_recovery",
)


class UpdateRecoveryAction(Enum):
    ACTIVATE = "activate"
    RESTORE = "restore"
    CLEAN_COMMITTED = "clean_committed"
    CLEAN_INTERRUPTED = "clean_interrupted"


def plan_transaction_recovery(
    paths: UpdateTransactionPaths, *, allow_pending_activation: bool
) -> UpdateRecoveryAction:
    validate_update_recovery_evidence(paths)
    transaction_path = paths.transaction_path
    if os.path.exists(marker_path(transaction_path, SUCCESS_COMPLETE_MARKER)):
        return UpdateRecoveryAction.CLEAN_COMMITTED
    rollback_complete = os.path.exists(marker_path(transaction_path, ROLLBACK_COMPLETE_MARKER))
    if read_pending_update_activation(paths) is not None:
        if (
            not os.path.lexists(activation_process_path(paths))
            and not rollback_complete
            and not os.path.exists(marker_path(transaction_path, ACTIVATION_FAILED_MARKER))
        ):
            if not allow_pending_activation:
                raise StateError("An installed update awaits explicit startup activation.")
            if require_rollback_inventory(paths, old_complete=True) is None:
                raise StateError("Pending activation has no required rollback inventory.")
            return UpdateRecoveryAction.ACTIVATE
        require_update_candidate_stopped(paths)
    if rollback_complete:
        return UpdateRecoveryAction.CLEAN_INTERRUPTED
    if os.path.exists(marker_path(transaction_path, ROLLBACK_REQUIRED_MARKER)):
        if not os.path.isdir(paths.rollback_old_path) or os.path.islink(paths.rollback_old_path):
            raise StateError(
                "Update rollback originals are unavailable; preserve the transaction for repair."
            )
        require_rollback_inventory(
            paths,
            old_complete=os.path.exists(marker_path(transaction_path, OLD_COMPLETE_MARKER)),
        )
        validate_managed_data_destinations(paths)
        return UpdateRecoveryAction.RESTORE
    if os.path.exists(marker_path(transaction_path, PREPARING_MARKER)):
        inventory = require_rollback_inventory(
            paths, old_complete=False, originals_at_installation=True
        )
        if inventory is None:
            raise StateError("Prepared update is missing its original inventory.")
        return UpdateRecoveryAction.CLEAN_INTERRUPTED
    if os.path.lexists(paths.rollback_old_path) and (
        os.path.islink(paths.rollback_old_path)
        or not os.path.isdir(paths.rollback_old_path)
        or os.listdir(paths.rollback_old_path)
    ):
        raise StateError(
            "Unmarked update transaction contains rollback evidence; preserve it for repair."
        )
    return UpdateRecoveryAction.CLEAN_INTERRUPTED


def inspect_update_restorations(base_path: str) -> tuple[str, ...]:
    resolved_base_path = os.path.abspath(base_path)
    if not os.path.isdir(resolved_base_path):
        return ()
    restoration_paths: list[str] = []
    with guarded_software_update_recovery(resolved_base_path):
        for name in os.listdir(resolved_base_path):
            if not name.startswith(TRANSACTION_PREFIX):
                continue
            transaction_path = os.path.join(resolved_base_path, name)
            if os.path.islink(transaction_path) or not os.path.isdir(transaction_path):
                raise StateError("Update transaction storage is invalid; preserve it for repair.")
            action = plan_transaction_recovery(
                paths_from_transaction_directory(resolved_base_path, transaction_path),
                allow_pending_activation=True,
            )
            if action is UpdateRecoveryAction.RESTORE:
                require_no_pending_restore(resolved_base_path)
                restoration_paths.append(transaction_path)
    return tuple(restoration_paths)
