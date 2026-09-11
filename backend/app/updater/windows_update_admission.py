"""SoAI - Verified admission of native Windows installation mutation [backend/app/updater/windows_update_admission.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os

from app.updater.software_update.activation_state import (
    read_update_activation_identity,
    validate_update_recovery_evidence,
)
from app.updater.software_update.install_transaction_inventory import require_rollback_inventory
from app.updater.software_update.install_transaction_state import (
    OLD_COMPLETE_MARKER,
    ROLLBACK_REQUIRED_MARKER,
    marker_path,
    paths_from_transaction_directory,
    write_marker,
)
from core.errors.exceptions import StateError

__all__ = ("begin_windows_update_transaction",)


def begin_windows_update_transaction(base_path: str, transaction_path: str, task_id: str) -> None:
    paths = paths_from_transaction_directory(base_path, transaction_path)
    validate_update_recovery_evidence(paths)
    if read_update_activation_identity(paths).task_id != task_id:
        raise StateError("Windows replacement does not identify the accepted update task.")
    if not os.path.isfile(
        marker_path(paths.transaction_path, OLD_COMPLETE_MARKER)
    ) or os.path.lexists(marker_path(paths.transaction_path, ROLLBACK_REQUIRED_MARKER)):
        raise StateError("Windows replacement requires complete, unarmed preparation.")
    if require_rollback_inventory(paths, old_complete=True) is None:
        raise StateError("Windows replacement has no retained rollback inventory.")
    write_marker(paths.transaction_path, ROLLBACK_REQUIRED_MARKER)
