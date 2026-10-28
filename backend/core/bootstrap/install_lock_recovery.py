"""SoAI - Native Windows abandoned install lock admission [backend/core/bootstrap/install_lock_recovery.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import math
import os
from collections.abc import Callable
from contextlib import ExitStack

from core.bootstrap.install_locks import guard_windows_installer_gate
from core.bootstrap.install_target_windows import retain_windows_install_ancestors
from core.bootstrap.lock import INSTALLATION_TRANSACTION_LOCK_FILENAME, acquire_interprocess_lock
from core.errors.exceptions import StateError
from core.meta.paths import join_data_abs
from core.system.commands import run_argv_capture
from core.system.native_image_budget import native_image_allowance
from core.timing.constants import CONTROL_TIMEOUT_SEC, EXTENDED_TIMEOUT_SEC

__all__ = ("recover_windows_install_lock", "recover_windows_startup_install_lock")


def recover_windows_install_lock(lock_dir: str, launcher_path: str) -> bool:
    if os.name != "nt":
        return False
    allowance = native_image_allowance(EXTENDED_TIMEOUT_SEC, roots=(launcher_path,))
    result = run_argv_capture(
        [launcher_path, "--recover-install-lock", lock_dir],
        check=True,
        timeout=math.ceil(allowance.seconds),
        encoding="utf-8",
        errors="strict",
    )
    return bool(result.stdout.strip())


def recover_windows_startup_install_lock(
    repo_root_path: str, check_transaction_admission: Callable[[str], None]
) -> bool:
    with ExitStack() as admission:
        admission.enter_context(guard_windows_installer_gate())
        retain_windows_install_ancestors(repo_root_path, admission)
        admission.enter_context(
            acquire_interprocess_lock(
                join_data_abs(repo_root_path, "locks", INSTALLATION_TRANSACTION_LOCK_FILENAME),
                timeout_sec=CONTROL_TIMEOUT_SEC,
            )
        )
        lock_dir = join_data_abs(repo_root_path, "state", "locks", "soai.install.lock.d")
        recover_windows_install_lock(lock_dir, os.path.join(repo_root_path, "soai.exe"))
        if os.path.isdir(lock_dir):
            return False
        runtime_lock_dir = join_data_abs(repo_root_path, "state", "locks", "soai.runtime.lock.d")
        recover_windows_install_lock(runtime_lock_dir, os.path.join(repo_root_path, "soai.exe"))
        if os.path.lexists(runtime_lock_dir):
            return False
        check_transaction_admission(repo_root_path)
        marker_path = os.path.join(repo_root_path, ".soai_install_in_progress")
        if os.path.isfile(marker_path):
            raise StateError(
                "An interrupted SoAI installation requires repair. Run the SoAI installer again before starting.",
                details={"marker_path": marker_path},
                operation="bootstrap.install.recover_abandoned_installation",
            )
        return True
