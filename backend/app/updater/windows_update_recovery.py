"""SoAI - Exclusive launcher-exit recovery handoff [backend/app/updater/windows_update_recovery.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os

import psutil

from app.updater.software_update.activation_state import read_update_activation_identity
from app.updater.software_update.install_transaction_recovery import (
    recover_interrupted_update_transactions,
)
from app.updater.software_update.install_transaction_recovery_plan import (
    UpdateRecoveryAction,
    inspect_update_restorations,
    plan_transaction_recovery,
)
from app.updater.software_update.install_transaction_state import paths_from_transaction_directory
from app.updater.software_update.update_lock import guarded_software_update_lock
from core.errors.exceptions import StateError
from core.files.path_policy import safe_join_relative_under_base
from core.filesystem.atomic_writes import atomic_create_text_content_exclusive
from core.logging.protocols import LoggerProtocol
from core.runtime.event_loop_runner import run_coroutine_in_new_event_loop
from core.runtime.process_identity_signals import (
    read_process_create_time_ms,
    wait_for_process_identity_mismatch_or_gone,
)
from core.timing.constants import CONTROL_TIMEOUT_SEC

__all__ = ("recover_after_launcher_exit",)


def recover_after_launcher_exit(
    *,
    base_path: str,
    transaction_path: str,
    launcher_pid: int,
    supervisor_pid: int,
    ready_path: str,
    logger: LoggerProtocol,
) -> str:
    paths = paths_from_transaction_directory(base_path, transaction_path)
    identity = read_update_activation_identity(paths)
    if supervisor_pid != os.getppid():
        raise StateError("Recovery supervisor does not identify the invoking process.")
    ready_path = safe_join_relative_under_base(
        base_path=paths.transaction_path,
        relative_path=os.path.relpath(ready_path, paths.transaction_path),
        description="Launcher recovery acknowledgement",
        error_cls=StateError,
    )
    with guarded_software_update_lock(base_path=base_path, logger=logger, edition=identity.edition):
        if (
            not inspect_update_restorations(base_path)
            or plan_transaction_recovery(paths, allow_pending_activation=True)
            is not UpdateRecoveryAction.RESTORE
        ):
            raise StateError("The requested recovery was superseded; no restoration was attempted.")
        launcher = psutil.Process(launcher_pid)
        launcher_created_ms = read_process_create_time_ms(launcher)
        atomic_create_text_content_exclusive(
            ready_path,
            str(supervisor_pid),
            ensure_parent=False,
            file_mode=0o600,
            fsync_parent_directory=True,
        )
        if not run_coroutine_in_new_event_loop(
            wait_for_process_identity_mismatch_or_gone(
                launcher_pid, launcher_created_ms, timeout_sec=CONTROL_TIMEOUT_SEC
            )
        ):
            raise StateError("The invoking launcher remains active; no restoration was attempted.")
        if not recover_interrupted_update_transactions(
            base_path, logger, allow_pending_activation=True, cleanup_after_recovery=False
        ):
            raise StateError("Shared update recovery failed; preserve the transaction for repair.")
    return identity.config_path
