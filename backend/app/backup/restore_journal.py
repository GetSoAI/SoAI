"""SoAI - Durable backup restore transaction journal [backend/app/backup/restore_journal.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import os
from typing import TYPE_CHECKING

from app.backup.restore_destinations import ensure_restore_destination_is_safe
from app.backup.restore_journal_codec import (
    RestoreCompletionRecord,
    RestoreJournalItem,
    RestoreJournalState,
    parse_restore_journal_state,
    serialize_restore_journal_state,
    validate_restore_absolute_path,
)
from app.installation_transaction_admission import (
    RESTORE_JOURNAL_RELATIVE_PATH,
    guard_installation_transaction_admission,
)
from core.concurrency.joined_thread_call import run_joined_thread_call
from core.errors.exceptions import ConflictError, StateError
from core.filesystem.atomic_write_primitives import fsync_directory
from core.filesystem.atomic_writes import (
    atomic_create_text_content_exclusive,
    atomic_write_text_content,
)
from core.filesystem.open_files import read_regular_file_no_symlink
from core.meta.paths import join_data_abs

if TYPE_CHECKING:
    from app.backup.restore_journal_codec import RestoreJournalPhase

__all__ = (
    "RestoreCompletionRecord",
    "RestoreJournalItem",
    "RestoreJournalState",
    "create_restore_journal",
    "get_restore_journal_path",
    "load_restore_journal",
    "remove_restore_journal",
    "require_no_pending_restore",
    "transition_restore_journal",
)

_MAX_JOURNAL_BYTES = 1024 * 1024


def _transition_is_allowed(
    current_phase: RestoreJournalPhase,
    next_phase: RestoreJournalPhase,
) -> bool:
    if current_phase == "snapshotting":
        return next_phase == "prepared"
    if current_phase == "prepared":
        return next_phase == "committing"
    if current_phase == "committing":
        return next_phase in {"committed", "rolled_back"}
    return False


def get_restore_journal_path(project_root: str) -> str:
    journal_path = join_data_abs(project_root, *RESTORE_JOURNAL_RELATIVE_PATH)
    ensure_restore_destination_is_safe(journal_path)
    return journal_path


def require_no_pending_restore(project_root: str) -> None:
    if os.path.lexists(get_restore_journal_path(project_root)):
        raise ConflictError(
            "A backup restore still requires recovery. Start the installed application to complete restore recovery before updating."
        )


def _sync_load_restore_journal(project_root: str) -> RestoreJournalState | None:
    journal_path = get_restore_journal_path(project_root)
    if not os.path.lexists(journal_path):
        return None
    raw = read_regular_file_no_symlink(
        journal_path,
        max_bytes=_MAX_JOURNAL_BYTES,
        not_found_message="Restore journal disappeared during startup recovery.",
        symlink_message="Restore journal must not be a symlink.",
        regular_file_message="Restore journal must be a regular file.",
    )
    return parse_restore_journal_state(raw, maximum_bytes=_MAX_JOURNAL_BYTES)


async def load_restore_journal(project_root: str) -> RestoreJournalState | None:
    return await asyncio.to_thread(_sync_load_restore_journal, project_root)


async def create_restore_journal(
    project_root: str,
    *,
    snapshot_path: str,
    items: dict[str, RestoreJournalItem],
) -> RestoreJournalState:
    state = RestoreJournalState(
        "snapshotting",
        validate_restore_absolute_path(snapshot_path, field="snapshot_path"),
        dict(items),
        None,
    )
    state = parse_restore_journal_state(
        serialize_restore_journal_state(state).encode("utf-8", errors="strict"),
        maximum_bytes=_MAX_JOURNAL_BYTES,
    )

    def _sync_create() -> None:
        with guard_installation_transaction_admission(project_root):
            journal_path = get_restore_journal_path(project_root)
            atomic_create_text_content_exclusive(
                journal_path,
                serialize_restore_journal_state(state),
                errors="strict",
                parent_mode=0o700,
                fsync=True,
                file_mode=0o600,
                fsync_parent_directory=True,
            )
            journal_parent = os.path.dirname(journal_path)
            fsync_directory(journal_parent, strict=True)
            fsync_directory(os.path.dirname(journal_parent), strict=True)

    await run_joined_thread_call(_sync_create, task_name="backup-restore-journal-create")
    return state


async def transition_restore_journal(
    project_root: str,
    *,
    expected_state: RestoreJournalState,
    phase: RestoreJournalPhase,
    completion: RestoreCompletionRecord | None = None,
) -> RestoreJournalState:
    if not _transition_is_allowed(expected_state.phase, phase):
        raise StateError(f"Invalid restore journal transition: {expected_state.phase} -> {phase}.")
    next_state = RestoreJournalState(
        phase,
        expected_state.snapshot_path,
        expected_state.items,
        completion,
    )
    serialized = serialize_restore_journal_state(next_state)
    next_state = parse_restore_journal_state(
        serialized.encode("utf-8", errors="strict"),
        maximum_bytes=_MAX_JOURNAL_BYTES,
    )

    def _sync_transition() -> None:
        current_state = _sync_load_restore_journal(project_root)
        if current_state != expected_state:
            raise StateError("Restore journal changed during transaction commit.")
        journal_path = get_restore_journal_path(project_root)
        atomic_write_text_content(
            journal_path,
            serialized,
            errors="strict",
            parent_mode=0o700,
            fsync=True,
            file_mode=0o600,
            fsync_parent_directory=True,
        )
        fsync_directory(os.path.dirname(journal_path), strict=True)

    await run_joined_thread_call(
        _sync_transition,
        task_name="backup-restore-journal-transition",
    )
    return next_state


async def remove_restore_journal(
    project_root: str,
    *,
    expected_state: RestoreJournalState,
) -> None:
    def _sync_remove() -> None:
        current_state = _sync_load_restore_journal(project_root)
        if current_state != expected_state:
            raise StateError("Restore journal changed before transaction cleanup.")
        journal_path = get_restore_journal_path(project_root)
        os.unlink(journal_path)
        fsync_directory(os.path.dirname(journal_path), strict=True)

    await run_joined_thread_call(_sync_remove, task_name="backup-restore-journal-remove")
