"""SoAI - Durable update rollback snapshot preparation [backend/app/updater/software_update/install_transaction_preparation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
import time
from typing import TYPE_CHECKING

from app.backup.backup_removal import sync_remove_tree_no_symlinks
from app.backup.restore_destinations import ensure_restore_destination_is_safe
from app.updater.software_update.activation_identity import UpdateActivationIdentity
from app.updater.software_update.install_transaction_inventory import (
    ROLLBACK_INVENTORY_FILENAME,
    RollbackContentMismatch,
    RollbackSourceFailure,
    UpdateRollbackInventory,
    inspect_rollback_inventory,
    installed_original_path,
    plan_replacement_roots,
)
from app.updater.software_update.install_transaction_inventory_writer import (
    WrittenRollbackInventory,
    write_rollback_inventory,
)
from app.updater.software_update.install_transaction_managed_data import (
    copy_managed_data_to_rollback,
    prepare_managed_data_commit,
)
from app.updater.software_update.install_transaction_snapshot_evidence import (
    CHECK_INSTALLED_ORIGINAL,
    CHECK_RECOPY,
    CHECK_RETAINED_COPY,
    SnapshotProgress,
    UpdateSnapshotEvidenceError,
    UpdateSnapshotOutcomeError,
    build_content_mismatch_report,
    build_operation_failure_report,
    read_expected_descriptors,
    record_snapshot_report,
    snapshot_preparation_failure,
)
from app.updater.software_update.install_transaction_state import (
    OLD_COMPLETE_MARKER,
    PREPARING_MARKER,
    ROLLBACK_REQUIRED_MARKER,
    UpdateTransactionPaths,
    marker_path,
    write_marker,
)
from app.updater.software_update.install_transaction_state_transfer import (
    copy_persisted_update_state,
)
from app.updater.software_update.update_lock import (
    require_software_update_lock_owner,
    resolve_software_update_lock_dir,
)
from core.bootstrap.filename_normalization import validate_filename_destinations
from core.bootstrap.install_payload_transaction import copy_install_entry
from core.errors.exceptions import SoAIError, StateError
from core.files.path_policy import safe_join_relative_under_base_lexical
from core.filesystem.atomic_write_primitives import fsync_directory
from core.filesystem.file_sync import fsync_install_entry

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("prepare_update_rollback",)


def _copy_snapshot(
    paths: UpdateTransactionPaths,
    written: WrittenRollbackInventory,
    replacement_roots: tuple[str, ...],
    progress: SnapshotProgress,
    retained_installation_root: str | None,
) -> None:
    copy_started = time.monotonic()
    copy_persisted_update_state(
        paths, written.state, retained_installation_root=retained_installation_root
    )
    copy_managed_data_to_rollback(paths, retained_installation_root=retained_installation_root)
    source_root = retained_installation_root or paths.base_path
    for item_name in replacement_roots:
        if not os.path.lexists(os.path.join(source_root, item_name)):
            continue
        copy_install_entry(os.path.join(source_root, item_name), paths.rollback_old_path)
        fsync_directory(paths.rollback_old_path, strict=True)
        fsync_directory(paths.base_path, strict=True)
    progress.copy_seconds = time.monotonic() - copy_started
    sync_started = time.monotonic()
    fsync_install_entry(paths.rollback_old_path)
    progress.sync_seconds = time.monotonic() - sync_started


def _inspect_snapshot(
    paths: UpdateTransactionPaths,
    written: WrittenRollbackInventory,
    progress: SnapshotProgress,
    *,
    retained: bool,
    retained_installation_root: str | None = None,
) -> UpdateRollbackInventory | RollbackContentMismatch:
    progress.check = CHECK_RETAINED_COPY if retained else CHECK_INSTALLED_ORIGINAL
    verification_started = time.monotonic()
    inspection = inspect_rollback_inventory(
        paths,
        old_complete=retained,
        originals_at_installation=not retained,
        retained_installation_root=retained_installation_root,
    )
    progress.verification_seconds = time.monotonic() - verification_started
    if isinstance(inspection, RollbackSourceFailure):
        raise snapshot_preparation_failure(
            written.diagnostics,
            build_operation_failure_report(
                classification="snapshot_operation_failed" if retained else "source_unverifiable",
                progress=progress,
                entry=inspection.entry,
                entry_index=inspection.entry_index,
                exception=inspection.exception,
            ),
            cause=inspection.exception,
        ) from inspection.exception
    if inspection is None:
        raise StateError("Prepared update is missing its original inventory.")
    return inspection


def _mismatch_report(
    written: WrittenRollbackInventory,
    progress: SnapshotProgress,
    mismatch: RollbackContentMismatch,
    *,
    classification: str,
    recopy_forbidden_reason: str | None,
) -> JSONDict:
    return build_content_mismatch_report(
        classification=classification,
        mismatch=mismatch,
        expected=read_expected_descriptors(
            written.diagnostics,
            index=mismatch.entry_index,
            entry=mismatch.entry,
            aggregate=mismatch.expected_aggregate,
        ),
        progress=progress,
        recopy_forbidden_reason=recopy_forbidden_reason,
    )


def _require_originals_unchanged(
    paths: UpdateTransactionPaths,
    written: WrittenRollbackInventory,
    progress: SnapshotProgress,
    retained_installation_root: str | None = None,
) -> None:
    originals = _inspect_snapshot(
        paths,
        written,
        progress,
        retained=False,
        retained_installation_root=retained_installation_root,
    )
    if isinstance(originals, RollbackContentMismatch):
        raise snapshot_preparation_failure(
            written.diagnostics,
            _mismatch_report(
                written,
                progress,
                originals,
                classification="installed_original_changed",
                recopy_forbidden_reason="installed_original_changed",
            ),
            cause=None,
        )


def _require_recopy_permitted(
    paths: UpdateTransactionPaths, identity: UpdateActivationIdentity
) -> None:
    if not os.path.isfile(marker_path(paths.transaction_path, PREPARING_MARKER)) or any(
        os.path.lexists(marker_path(paths.transaction_path, marker))
        for marker in (OLD_COMPLETE_MARKER, ROLLBACK_REQUIRED_MARKER)
    ):
        raise StateError("Update snapshot repair is only permitted during unarmed preparation.")
    require_software_update_lock_owner(
        resolve_software_update_lock_dir(paths.base_path),
        base_path=paths.base_path,
        edition=identity.edition,
        expected_pid=os.getpid(),
    )


def _recopy_failed_entry(
    paths: UpdateTransactionPaths,
    written: WrittenRollbackInventory,
    identity: UpdateActivationIdentity,
    mismatch: RollbackContentMismatch,
    progress: SnapshotProgress,
) -> None:
    progress.check = CHECK_RECOPY
    recopy_started = time.monotonic()
    _require_recopy_permitted(paths, identity)
    original = installed_original_path(paths, mismatch.entry, written.state)
    retained = safe_join_relative_under_base_lexical(
        base_path=paths.rollback_old_path,
        relative_path=mismatch.entry,
        description="Update rollback original",
        error_cls=StateError,
    )
    retained_parent = os.path.dirname(retained)
    ensure_restore_destination_is_safe(retained_parent)
    if (
        not os.path.isdir(retained_parent)
        or not os.path.lexists(retained)
        or retained != os.path.join(retained_parent, os.path.basename(original))
    ):
        raise StateError("Update snapshot entry cannot be repaired from its recorded identity.")
    sync_remove_tree_no_symlinks(retained)
    fsync_directory(retained_parent, strict=True)
    copy_install_entry(original, retained_parent)
    fsync_install_entry(retained)
    fsync_directory(retained_parent, strict=True)
    progress.recopy_seconds = time.monotonic() - recopy_started


def _verify_snapshot(
    paths: UpdateTransactionPaths,
    written: WrittenRollbackInventory,
    identity: UpdateActivationIdentity,
    progress: SnapshotProgress,
    retained_installation_root: str | None,
) -> None:
    retained = _inspect_snapshot(paths, written, progress, retained=True)
    if isinstance(retained, RollbackContentMismatch):
        if retained_installation_root is not None:
            raise snapshot_preparation_failure(
                written.diagnostics,
                _mismatch_report(
                    written,
                    progress,
                    retained,
                    classification="retained_copy_mismatch",
                    recopy_forbidden_reason="installer_originals_retained",
                ),
                cause=None,
            )
        report = _mismatch_report(
            written,
            progress,
            retained,
            classification="retained_copy_mismatch",
            recopy_forbidden_reason=None,
        )
        reference = record_snapshot_report(written.diagnostics, report, cause=None)
        if report["expected_descriptors"] != "available":
            raise UpdateSnapshotEvidenceError(
                "Update snapshot comparison evidence is unavailable; recopy is forbidden.",
                details={
                    "classification": "evidence_unavailable",
                    "check": progress.check,
                    "entry": retained.entry,
                    "reference": reference,
                },
            )
        _require_originals_unchanged(paths, written, progress)
        _recopy_failed_entry(paths, written, identity, retained, progress)
        progress.attempt += 1
        repaired = _inspect_snapshot(paths, written, progress, retained=True)
        if isinstance(repaired, RollbackContentMismatch):
            raise snapshot_preparation_failure(
                written.diagnostics,
                _mismatch_report(
                    written,
                    progress,
                    repaired,
                    classification="retained_copy_mismatch",
                    recopy_forbidden_reason="recopy_exhausted",
                ),
                cause=None,
            )
    _require_originals_unchanged(paths, written, progress, retained_installation_root)


def prepare_update_rollback(
    paths: UpdateTransactionPaths,
    *,
    identity: UpdateActivationIdentity,
    state_files: tuple[str, ...] = (),
    state_directories: tuple[str, ...] = (),
    additional_roots: tuple[str, ...] = (),
    retained_installation_root: str | None = None,
) -> None:
    if os.path.lexists(os.path.join(paths.transaction_path, ROLLBACK_INVENTORY_FILENAME)) or (
        os.listdir(paths.rollback_old_path)
    ):
        raise StateError("Update rollback preparation already has evidence; recover it first.")
    validate_filename_destinations(paths.staged_new_path, paths.base_path)
    replacement_roots = plan_replacement_roots(paths, identity.edition, additional_roots)
    prepare_managed_data_commit(paths)
    written = write_rollback_inventory(
        paths,
        replacement_roots,
        identity,
        state_files,
        state_directories,
        retained_installation_root=retained_installation_root,
    )
    write_marker(paths.transaction_path, PREPARING_MARKER)
    progress = SnapshotProgress()
    try:
        _copy_snapshot(paths, written, replacement_roots, progress, retained_installation_root)
        _verify_snapshot(paths, written, identity, progress, retained_installation_root)
    except UpdateSnapshotOutcomeError:
        raise
    except (OSError, SoAIError) as exception:
        raise snapshot_preparation_failure(
            written.diagnostics,
            build_operation_failure_report(
                classification="snapshot_operation_failed",
                progress=progress,
                entry=None,
                entry_index=None,
                exception=exception,
            ),
            cause=exception,
        ) from exception
    write_marker(paths.transaction_path, OLD_COMPLETE_MARKER)
