"""SoAI - Transactional software update installation [backend/app/updater/software_update/install_transaction.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
import zipfile
from typing import TYPE_CHECKING

from app.backup.backup_removal import sync_remove_tree_no_symlinks
from app.edition_composition import UpdaterComposition
from app.updater.release_manifest_types import ReleaseManifestV1, ReleaseUpdateArchive
from app.updater.software_update.install_transaction_managed_data import (
    install_staged_managed_data,
    move_managed_data_to_rollback,
    prepare_managed_data_commit,
)
from app.updater.software_update.install_transaction_recovery import (
    cleanup_uncommitted_transaction,
    restore_transaction,
)
from app.updater.software_update.install_transaction_state import (
    NEW_COMPLETE_MARKER,
    OLD_COMPLETE_MARKER,
    ROLLBACK_REQUIRED_MARKER,
    SUCCESS_COMPLETE_MARKER,
    UPDATE_COMPONENT_IGNORE_PATTERNS,
    AppliedUpdateTransaction,
    UpdateTransactionPaths,
    allocate_update_transaction,
    build_rollback_top_level_ignore_patterns,
    build_update_extraction_top_level_ignore_patterns,
    build_update_top_level_ignore_patterns,
    is_preserved_top_level_item,
    marker_path,
    paths_from_transaction_directory,
    remove_marker,
    write_marker,
)
from app.updater.software_update.update_payload_validation import (
    validate_and_prepare_staged_update,
)
from core.archives.errors import ArchivePathTraversalError
from core.archives.zip_extraction import (
    ZipExtractionOptions,
    safe_zip_extract_with_options,
)
from core.errors.exception_logging import log_exception
from core.errors.exceptions import StateError, ValidationError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.protocols import LoggerProtocol

if TYPE_CHECKING:
    from core.hardware.protocols_storage import StorageManagerProtocol

__all__ = (
    "AppliedUpdateTransaction",
    "apply_update_from_zip",
    "finalize_update_transaction",
)

OPERATION_APPLICATION_UPDATER_APPLY_UPDATE_FROM_ZIP = "application_updater.apply_update_from_zip"
OPERATION_APPLICATION_UPDATER_FINALIZE_TRANSACTION = (
    "application_updater.finalize_update_transaction"
)
TRANSACTION_COMMIT_EXCEPTIONS = RECOVERABLE_EXCEPTIONS + (OSError, StateError)
TRANSACTION_CLEANUP_EXCEPTIONS = RECOVERABLE_EXCEPTIONS + (OSError,)


def _commit_staged_update(
    *,
    paths: UpdateTransactionPaths,
    top_level_ignore_patterns: tuple[str, ...],
    logger: LoggerProtocol,
) -> AppliedUpdateTransaction:
    try:
        prepare_managed_data_commit(paths)
        write_marker(paths.transaction_path, ROLLBACK_REQUIRED_MARKER)
        move_managed_data_to_rollback(paths)
        for item_name in os.listdir(paths.base_path):
            if is_preserved_top_level_item(item_name, top_level_ignore_patterns):
                continue
            os.rename(
                os.path.join(paths.base_path, item_name),
                os.path.join(paths.rollback_old_path, item_name),
            )
        write_marker(paths.transaction_path, OLD_COMPLETE_MARKER)
        install_staged_managed_data(paths)
        for item_name in os.listdir(paths.staged_new_path):
            destination_item = os.path.join(paths.base_path, item_name)
            if os.path.lexists(destination_item):
                raise StateError(f"Update destination already exists: {destination_item}")
            os.rename(os.path.join(paths.staged_new_path, item_name), destination_item)
        write_marker(paths.transaction_path, NEW_COMPLETE_MARKER)
        return AppliedUpdateTransaction(
            base_path=paths.base_path,
            transaction_path=paths.transaction_path,
        )
    except TRANSACTION_COMMIT_EXCEPTIONS:
        restore_transaction(
            paths=paths,
            top_level_ignore_patterns=top_level_ignore_patterns,
            logger=logger,
        )
        raise


def apply_update_from_zip(
    *,
    zip_path: str,
    base_path: str,
    logger: LoggerProtocol,
    platform_id: str,
    archive_record: ReleaseUpdateArchive,
    reservation_provider: StorageManagerProtocol,
    manifest: ReleaseManifestV1,
    updater: UpdaterComposition,
) -> AppliedUpdateTransaction | None:
    operational_exceptions = RECOVERABLE_EXCEPTIONS + (
        OSError,
        zipfile.BadZipFile,
        ArchivePathTraversalError,
    )
    top_level_ignore_patterns = build_update_top_level_ignore_patterns()
    extraction_top_level_ignore_patterns = build_update_extraction_top_level_ignore_patterns()
    try:
        paths = allocate_update_transaction(base_path)
    except OSError as exception:
        log_exception(
            logger,
            exception,
            message="Failed to allocate update transaction.",
            operation=OPERATION_APPLICATION_UPDATER_APPLY_UPDATE_FROM_ZIP,
            level="error",
        )
        return None
    try:
        logger.info("Extracting update into transaction staging area...")
        result = safe_zip_extract_with_options(
            zip_path,
            paths.staged_new_path,
            ZipExtractionOptions(
                ignore_patterns=UPDATE_COMPONENT_IGNORE_PATTERNS,
                top_level_ignore_patterns=extraction_top_level_ignore_patterns,
                strip_root_prefix=True,
            ),
            reservation_provider=reservation_provider,
        )
        if not result.extracted_files:
            raise ValidationError("Update archive contains no extractable files.")
        if result.root_prefix != archive_record.archive_root:
            raise ValidationError("Update archive root does not match the signed release manifest.")
        validate_and_prepare_staged_update(
            staged_root=paths.staged_new_path,
            platform_id=platform_id,
            archive_record=archive_record,
            manifest=manifest,
            updater=updater,
        )
        logger.info("Committing staged update transaction...")
        return _commit_staged_update(
            paths=paths,
            top_level_ignore_patterns=top_level_ignore_patterns,
            logger=logger,
        )
    except (ValidationError, StateError):
        if os.path.exists(paths.transaction_path) and not os.path.exists(
            marker_path(paths.transaction_path, ROLLBACK_REQUIRED_MARKER),
        ):
            cleanup_uncommitted_transaction(paths, logger)
        raise
    except operational_exceptions as exception:
        log_exception(
            logger,
            exception,
            message="Error applying update from zip.",
            operation=OPERATION_APPLICATION_UPDATER_APPLY_UPDATE_FROM_ZIP,
            details={"transaction_path": paths.transaction_path},
            level="error",
        )
        if os.path.exists(paths.transaction_path) and not os.path.exists(
            marker_path(paths.transaction_path, ROLLBACK_REQUIRED_MARKER),
        ):
            cleanup_uncommitted_transaction(paths, logger)
        return None


def _finalize_successful_transaction(
    *,
    paths: UpdateTransactionPaths,
    logger: LoggerProtocol,
) -> bool:
    try:
        write_marker(paths.transaction_path, SUCCESS_COMPLETE_MARKER)
        remove_marker(paths.transaction_path, ROLLBACK_REQUIRED_MARKER)
        sync_remove_tree_no_symlinks(paths.transaction_path)
        return True
    except TRANSACTION_CLEANUP_EXCEPTIONS as exception:
        if os.path.exists(marker_path(paths.transaction_path, SUCCESS_COMPLETE_MARKER)) or (
            not os.path.exists(marker_path(paths.transaction_path, ROLLBACK_REQUIRED_MARKER))
        ):
            log_exception(
                logger,
                exception,
                message="Update transaction is committed but cleanup failed.",
                operation=OPERATION_APPLICATION_UPDATER_FINALIZE_TRANSACTION,
                details={"transaction_path": paths.transaction_path},
                level="warning",
            )
            return True
        log_exception(
            logger,
            exception,
            message="Failed to finalize successful update transaction.",
            operation=OPERATION_APPLICATION_UPDATER_FINALIZE_TRANSACTION,
            details={"transaction_path": paths.transaction_path},
        )
        return False


def finalize_update_transaction(
    *,
    transaction: AppliedUpdateTransaction,
    update_success: bool,
    logger: LoggerProtocol,
) -> bool:
    paths = paths_from_transaction_directory(
        transaction.base_path,
        transaction.transaction_path,
    )
    top_level_ignore_patterns = build_rollback_top_level_ignore_patterns(paths.transaction_path)
    if not os.path.isdir(paths.transaction_path):
        return True
    if update_success:
        return _finalize_successful_transaction(paths=paths, logger=logger)
    return restore_transaction(
        paths=paths,
        top_level_ignore_patterns=top_level_ignore_patterns,
        logger=logger,
    )
