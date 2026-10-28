"""SoAI - Exclusive admission of update and backup restore transactions [backend/app/installation_transaction_admission.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
from collections.abc import Callable, Generator
from contextlib import contextmanager

from core.bootstrap.lock import (
    INSTALLATION_TRANSACTION_LOCK_FILENAME,
    acquire_interprocess_lock,
    require_no_foreign_install_lock,
)
from core.errors.exceptions import ConflictError, StateError
from core.filesystem.path_coercion import normalize_filesystem_path
from core.meta.paths import join_data_abs
from core.timing.constants import CONTROL_TIMEOUT_SEC

__all__ = (
    "INSTALLATION_TRANSACTION_LOCK_FILENAME",
    "RESTORE_JOURNAL_RELATIVE_PATH",
    "TRANSACTION_CLEANUP_PREFIX",
    "TRANSACTION_PREFIX",
    "guard_installation_transaction_admission",
    "list_update_transaction_storage",
    "reject_unfinished_installation_transactions",
)

TRANSACTION_PREFIX = ".soai_update_transaction_"
TRANSACTION_CLEANUP_PREFIX = ".soai_update_cleanup_"
RESTORE_JOURNAL_RELATIVE_PATH = ("state", "backup_restore_journal.json")


@contextmanager
def guard_installation_transaction_admission(
    project_root: str,
    *,
    installation_lock_held: bool = False,
    inherited_install_lock_validator: Callable[[str], bool] | None = None,
) -> Generator[None]:
    require_no_foreign_install_lock(
        project_root, inherited_install_lock_validator=inherited_install_lock_validator
    )
    if installation_lock_held:
        reject_unfinished_installation_transactions(project_root)
        yield
        return
    with acquire_interprocess_lock(
        join_data_abs(project_root, "locks", INSTALLATION_TRANSACTION_LOCK_FILENAME),
        timeout_sec=CONTROL_TIMEOUT_SEC,
    ):
        require_no_foreign_install_lock(
            project_root, inherited_install_lock_validator=inherited_install_lock_validator
        )
        reject_unfinished_installation_transactions(project_root)
        yield


def list_update_transaction_storage(project_root: str) -> tuple[str, ...]:
    names = tuple(
        sorted(
            name
            for name in os.listdir(project_root)
            if name.startswith((TRANSACTION_PREFIX, TRANSACTION_CLEANUP_PREFIX))
        )
    )
    if len(names) > 1:
        raise StateError("Multiple update transactions conflict; preserve all evidence for repair.")
    paths = tuple(os.path.join(project_root, name) for name in names)
    if any(os.path.islink(path) or not os.path.isdir(path) for path in paths):
        raise StateError("Update transaction storage is invalid; preserve it for repair.")
    return paths


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
