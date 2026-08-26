"""SoAI - Interrupted backup restore startup recovery [backend/app/backup/restore_startup_recovery.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os

from app.backup.backup_locking import acquire_operations_lock, release_operations_lock
from app.backup.restore_committed_finalization import finalize_committed_restore_record
from app.backup.restore_journal import (
    load_restore_journal,
    remove_restore_journal,
    transition_restore_journal,
)
from app.backup.restore_snapshot import cleanup_pre_restore_snapshot, rollback_from_snapshot
from core.errors.exceptions import StateError
from core.logging.protocols import LoggerProtocol

__all__ = ("recover_interrupted_restore",)


async def recover_interrupted_restore(
    *,
    project_root: str,
    log: LoggerProtocol,
) -> None:
    state = await load_restore_journal(project_root)
    if state is None:
        return
    backups_path = os.path.dirname(state.snapshot_path)
    operations_lock = await acquire_operations_lock(backups_path, timeout_seconds=0)
    try:
        current_state = await load_restore_journal(project_root)
        if current_state is None:
            return
        state = current_state
        if state.phase == "committed":
            completion = state.completion
            if completion is None:
                raise StateError("Committed restore journal has no completion record.")
            log.warning("Finalizing a committed backup restore before application startup.")
            await finalize_committed_restore_record(completion, registry=None)
        elif state.phase == "committing":
            log.warning("Recovering an interrupted backup restore before application startup.")
            await rollback_from_snapshot(state=state, log=log)
            state = await transition_restore_journal(
                project_root,
                expected_state=state,
                phase="rolled_back",
            )
        await cleanup_pre_restore_snapshot(snapshot_path=state.snapshot_path, log=log)
        await remove_restore_journal(project_root, expected_state=state)
        log.info("Completed interrupted backup restore recovery.")
    finally:
        await release_operations_lock(operations_lock, log=log)
