"""SoAI - Update transaction disposal with diagnostic evidence preservation [backend/app/updater/software_update/install_transaction_cleanup.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
import stat

from app.backup.backup_removal import sync_remove_tree_no_symlinks
from app.installation_transaction_admission import TRANSACTION_CLEANUP_PREFIX, TRANSACTION_PREFIX
from app.updater.software_update.activation_state import (
    ACTIVATION_IDENTITY_FILENAME,
    read_update_activation_identity,
    validate_update_recovery_evidence,
)
from app.updater.software_update.install_transaction_snapshot_evidence import (
    discard_expected_descriptors,
)
from app.updater.software_update.install_transaction_state import (
    OLD_COMPLETE_MARKER,
    PREPARING_MARKER,
    ROLLBACK_INVENTORY_REQUIRED_MARKER,
    SUCCESS_COMPLETE_MARKER,
    UpdateTransactionPaths,
    marker_path,
    paths_from_transaction_directory,
)
from core.bootstrap.filename_normalization import normalize_installed_filenames
from core.errors.exception_logging import log_exception
from core.errors.exceptions import ConflictError, SecurityError, StateError, ValidationError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.filesystem.atomic_write_primitives import fsync_directory
from core.logging.protocols import LoggerProtocol
from core.tasks.software_update_diagnostic_reports import (
    preserve_update_diagnostics,
    record_interrupted_update_preparation,
    release_update_diagnostics,
    verify_update_diagnostics_preserved,
)
from core.tasks.software_update_diagnostics import (
    UpdateDiagnosticsContext,
    read_transaction_diagnostics_locator,
    read_update_diagnostics_context,
    read_update_diagnostics_locator,
)

__all__ = (
    "cleanup_update_transaction",
    "finish_update_cleanup",
    "release_transaction_diagnostics",
    "verify_cleanup_diagnostics",
)

OPERATION_CLEANUP_UPDATE_TRANSACTION = "application_updater.cleanup_update_transaction"
OPERATION_RELEASE_UPDATE_DIAGNOSTICS = "application_updater.release_update_diagnostics"
PHASE_INVENTORY_RECORDED = "inventory_recorded"
PHASE_SNAPSHOT_EVIDENCE_CAPTURE = "snapshot_evidence_capture"
PHASE_SNAPSHOT_COPY_OR_VERIFICATION = "snapshot_copy_or_verification"

TRANSACTION_DISPOSAL_EXCEPTIONS = RECOVERABLE_EXCEPTIONS + (
    OSError,
    ConflictError,
    SecurityError,
    StateError,
    ValidationError,
)


def _interrupted_preparation_phase(transaction_path: str) -> str | None:
    if os.path.lexists(marker_path(transaction_path, OLD_COMPLETE_MARKER)):
        return None
    if os.path.lexists(marker_path(transaction_path, PREPARING_MARKER)):
        return PHASE_SNAPSHOT_COPY_OR_VERIFICATION
    if os.path.lexists(marker_path(transaction_path, ROLLBACK_INVENTORY_REQUIRED_MARKER)):
        return PHASE_INVENTORY_RECORDED
    return PHASE_SNAPSHOT_EVIDENCE_CAPTURE


def _read_transaction_diagnostics(
    paths: UpdateTransactionPaths, *, transaction_name: str
) -> UpdateDiagnosticsContext | None:
    context = read_update_diagnostics_context(
        base_path=paths.base_path,
        transaction_path=paths.transaction_path,
        transaction_name=transaction_name,
    )
    if context is None and not os.path.lexists(
        os.path.join(paths.transaction_path, ACTIVATION_IDENTITY_FILENAME)
    ):
        return None
    identity = read_update_activation_identity(paths)
    if context is None:
        if read_update_diagnostics_locator(paths.base_path, identity.task_id) is not None:
            raise StateError("Update diagnostics context is missing from its recorded transaction.")
        return None
    if (
        context.task_id != identity.task_id
        or context.from_version != identity.from_version
        or context.to_version != identity.to_version
    ):
        raise StateError("Update diagnostics context does not match its activation identity.")
    return context


def _preserve_transaction_diagnostics(
    paths: UpdateTransactionPaths,
) -> UpdateDiagnosticsContext | None:
    context = _read_transaction_diagnostics(
        paths, transaction_name=os.path.basename(paths.transaction_path)
    )
    if context is None:
        return None
    phase = _interrupted_preparation_phase(paths.transaction_path)
    if phase is not None:
        record_interrupted_update_preparation(context, phase=phase)
    if not preserve_update_diagnostics(context):
        discard_expected_descriptors(context)
    return context


def verify_cleanup_diagnostics(
    base_path: str, cleanup_path: str
) -> UpdateDiagnosticsContext | None:
    transaction_name = os.path.basename(cleanup_path).replace(
        TRANSACTION_CLEANUP_PREFIX, TRANSACTION_PREFIX, 1
    )
    paths = paths_from_transaction_directory(base_path, cleanup_path)
    context = read_transaction_diagnostics_locator(base_path, transaction_name)
    retained_context = read_update_diagnostics_context(
        base_path=base_path, transaction_path=cleanup_path, transaction_name=transaction_name
    )
    if retained_context is not None and retained_context != context:
        raise StateError("Cleanup diagnostics context does not match its external locator.")
    if context is None:
        return _read_transaction_diagnostics(paths, transaction_name=transaction_name)
    if os.path.lexists(os.path.join(cleanup_path, ACTIVATION_IDENTITY_FILENAME)):
        identity = read_update_activation_identity(paths)
        if (
            context.task_id != identity.task_id
            or context.from_version != identity.from_version
            or context.to_version != identity.to_version
        ):
            raise StateError("Cleanup diagnostics locator does not match its activation identity.")
    verify_update_diagnostics_preserved(context)
    return context


def finish_update_cleanup(base_path: str, cleanup_path: str, logger: LoggerProtocol) -> None:
    paths = paths_from_transaction_directory(base_path, os.path.abspath(cleanup_path))
    if os.path.dirname(paths.transaction_path) != paths.base_path or not os.path.basename(
        paths.transaction_path
    ).startswith(TRANSACTION_CLEANUP_PREFIX):
        raise StateError(
            "Update cleanup storage must belong to the installation cleanup namespace."
        )
    if not stat.S_ISDIR(os.lstat(paths.transaction_path).st_mode):
        raise StateError("Update cleanup storage must be a regular directory.")
    context = verify_cleanup_diagnostics(paths.base_path, paths.transaction_path)
    normalize_installed_filenames(paths.base_path)
    sync_remove_tree_no_symlinks(paths.transaction_path)
    fsync_directory(paths.base_path, strict=True)
    release_transaction_diagnostics(paths.base_path, context, logger)


def release_transaction_diagnostics(
    base_path: str, context: UpdateDiagnosticsContext | None, logger: LoggerProtocol
) -> None:
    if context is None:
        return
    try:
        release_update_diagnostics(base_path, context)
    except (OSError, StateError, ValidationError) as exception:
        log_exception(
            logger,
            exception,
            message="Update diagnostics without reports could not be released.",
            operation=OPERATION_RELEASE_UPDATE_DIAGNOSTICS,
            details={"task_id": context.task_id},
            level="warning",
        )


def cleanup_update_transaction(
    paths: UpdateTransactionPaths,
    logger: LoggerProtocol,
    *,
    deferrable: bool = False,
    log_deferral: bool = True,
    retain_storage: bool = False,
) -> bool:
    try:
        if os.path.exists(marker_path(paths.transaction_path, SUCCESS_COMPLETE_MARKER)):
            validate_update_recovery_evidence(paths)
            normalize_installed_filenames(paths.base_path, previous_root=paths.rollback_old_path)
        if retain_storage:
            return True
        context = _preserve_transaction_diagnostics(paths)
        cleanup_path = os.path.join(
            paths.base_path,
            os.path.basename(paths.transaction_path).replace(
                TRANSACTION_PREFIX, TRANSACTION_CLEANUP_PREFIX, 1
            ),
        )
        os.rename(paths.transaction_path, cleanup_path)
        fsync_directory(paths.base_path, strict=True)
        sync_remove_tree_no_symlinks(cleanup_path)
        fsync_directory(paths.base_path, strict=True)
    except TRANSACTION_DISPOSAL_EXCEPTIONS as exception:
        if deferrable and not log_deferral:
            if isinstance(exception, OSError):
                return False
            raise
        log_exception(
            logger,
            exception,
            message=(
                "Update transaction storage is still in use; the next recovery removes it."
                if deferrable
                else "Failed to clean up update transaction storage."
            ),
            operation=OPERATION_CLEANUP_UPDATE_TRANSACTION,
            details={"transaction_path": paths.transaction_path},
            level="info" if deferrable else "warning",
        )
        return False
    release_transaction_diagnostics(paths.base_path, context, logger)
    return True
