"""SoAI - Restore task rollback from durable transaction state [backend/app/backup/restore_task_rollback.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from app.backup.restore_journal import (
    load_restore_journal,
    remove_restore_journal,
    transition_restore_journal,
)
from app.backup.restore_snapshot import cleanup_pre_restore_snapshot, rollback_from_snapshot
from core.errors.exception_logging import log_exception, log_handled_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.protocols import LoggerProtocol

if TYPE_CHECKING:
    from typing import Literal

    type RestoreRollbackResult = Literal[
        "not_required",
        "rolled_back",
        "recovery_pending",
        "commit_recovery_pending",
    ]

__all__ = ("attempt_restore_rollback_from_journal",)

OPERATION_CLEANUP = "application_restore.recovery.cleanup_transaction"
OPERATION_ROLLBACK = "application_restore.recovery.rollback"


async def attempt_restore_rollback_from_journal(
    *,
    project_root: str,
    logger: LoggerProtocol,
) -> RestoreRollbackResult:
    try:
        state = await load_restore_journal(project_root)
    except RECOVERABLE_EXCEPTIONS as journal_exception:
        log_exception(
            logger,
            journal_exception,
            message="Failed to read restore journal after restore failure",
            operation=OPERATION_ROLLBACK,
        )
        return "recovery_pending"
    if state is None:
        return "not_required"
    if state.phase == "committed":
        return "commit_recovery_pending"
    if state.phase in {"snapshotting", "prepared", "rolled_back"}:
        try:
            await cleanup_pre_restore_snapshot(snapshot_path=state.snapshot_path, log=logger)
            await remove_restore_journal(project_root, expected_state=state)
        except RECOVERABLE_EXCEPTIONS as cleanup_exception:
            log_handled_exception(
                logger,
                cleanup_exception,
                message="Failed to clean terminal restore transaction artifacts.",
                operation=OPERATION_CLEANUP,
                level="warning",
            )
        return "rolled_back" if state.phase == "rolled_back" else "not_required"
    logger.warning("Restore failure occurred; attempting rollback from durable snapshot.")
    try:
        await rollback_from_snapshot(state=state, log=logger)
        rolled_back_state = await transition_restore_journal(
            project_root,
            expected_state=state,
            phase="rolled_back",
        )
    except RECOVERABLE_EXCEPTIONS as rollback_exception:
        log_exception(
            logger,
            rollback_exception,
            message="Failed to rollback from snapshot after restore failure",
            operation=OPERATION_ROLLBACK,
        )
        return "recovery_pending"
    try:
        await cleanup_pre_restore_snapshot(
            snapshot_path=rolled_back_state.snapshot_path,
            log=logger,
        )
        await remove_restore_journal(
            project_root,
            expected_state=rolled_back_state,
        )
    except RECOVERABLE_EXCEPTIONS as cleanup_exception:
        log_handled_exception(
            logger,
            cleanup_exception,
            message="Failed to clean rolled-back restore transaction artifacts.",
            operation=OPERATION_CLEANUP,
            level="warning",
        )
    return "rolled_back"
