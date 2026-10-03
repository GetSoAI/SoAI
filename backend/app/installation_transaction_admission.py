"""SoAI - Exclusive admission of update and backup restore transactions [backend/app/installation_transaction_admission.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
from collections.abc import Generator
from contextlib import contextmanager

from core.bootstrap.lock import INSTALLATION_TRANSACTION_LOCK_FILENAME, acquire_interprocess_lock
from core.errors.exceptions import ConflictError
from core.filesystem.path_coercion import normalize_filesystem_path
from core.meta.paths import join_data_abs
from core.timing.constants import CONTROL_TIMEOUT_SEC

__all__ = (
    "INSTALLATION_TRANSACTION_LOCK_FILENAME",
    "RESTORE_JOURNAL_RELATIVE_PATH",
    "TRANSACTION_CLEANUP_PREFIX",
    "TRANSACTION_PREFIX",
    "guard_installation_transaction_admission",
    "reject_unfinished_installation_transactions",
)

TRANSACTION_PREFIX = ".soai_update_transaction_"
TRANSACTION_CLEANUP_PREFIX = ".soai_update_cleanup_"
RESTORE_JOURNAL_RELATIVE_PATH = ("state", "backup_restore_journal.json")


@contextmanager
def guard_installation_transaction_admission(project_root: str) -> Generator[None]:
    with acquire_interprocess_lock(
        join_data_abs(project_root, "locks", INSTALLATION_TRANSACTION_LOCK_FILENAME),
        timeout_sec=CONTROL_TIMEOUT_SEC,
    ):
        reject_unfinished_installation_transactions(project_root)
        yield


def reject_unfinished_installation_transactions(project_root: str) -> None:
    if os.path.lexists(
        normalize_filesystem_path(join_data_abs(project_root, *RESTORE_JOURNAL_RELATIVE_PATH))
    ):
        raise ConflictError("An unfinished backup restore transaction already exists.")
    if any(
        name.startswith((TRANSACTION_PREFIX, TRANSACTION_CLEANUP_PREFIX))
        for name in os.listdir(normalize_filesystem_path(project_root))
    ):
        raise ConflictError(
            "A software update awaits activation or recovery. Complete it before starting another update or backup restore."
        )
