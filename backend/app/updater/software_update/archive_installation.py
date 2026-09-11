"""SoAI - Verified archive update preparation and installation [backend/app/updater/software_update/archive_installation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
import zipfile
from collections.abc import Callable
from typing import TYPE_CHECKING

from app.edition_composition import UpdaterComposition
from app.updater.disk_space import require_disk_space_for_update
from app.updater.release_manifest_types import ReleaseManifestV1, ReleaseUpdateArchive
from app.updater.software_update.activation_state import record_update_activation_identity
from app.updater.software_update.install_transaction import commit_staged_update
from app.updater.software_update.install_transaction_inventory import plan_replacement_roots
from app.updater.software_update.install_transaction_persisted_state import (
    plan_persisted_update_state,
)
from app.updater.software_update.install_transaction_state import (
    ROLLBACK_REQUIRED_MARKER,
    UPDATE_COMPONENT_IGNORE_PATTERNS,
    AppliedUpdateTransaction,
    allocate_update_transaction,
    build_update_extraction_top_level_ignore_patterns,
    build_update_top_level_ignore_patterns,
    cleanup_update_transaction,
    marker_path,
)
from app.updater.software_update.plugin_reconciliation import (
    plan_plugin_reconciliation,
    reconcile_staged_plugins,
    stage_configured_plugins,
)
from app.updater.software_update.update_payload_validation import validate_and_prepare_staged_update
from core.archives.errors import ArchivePathTraversalError
from core.archives.zip_extraction import ZipExtractionOptions, safe_zip_extract_with_options
from core.bootstrap.install_payload import validate_existing_install_edition
from core.bootstrap.install_payload_transaction import install_entry_copy_size
from core.bootstrap.python_dependencies import runtime_dependencies_need_install
from core.errors.exception_logging import log_exception
from core.errors.exceptions import (
    InsufficientDiskSpaceError,
    SecurityError,
    StateError,
    ValidationError,
)
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.protocols import LoggerProtocol

if TYPE_CHECKING:
    from core.hardware.protocols_storage import StorageManagerProtocol

__all__ = ("apply_update_from_zip",)

OPERATION_APPLICATION_UPDATER_APPLY_UPDATE_FROM_ZIP = "application_updater.apply_update_from_zip"


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
    before_commit: Callable[[], bool],
    task_id: str,
    from_version: str,
    config_path: str,
    state_files: tuple[str, ...] = (),
    state_directories: tuple[str, ...] = (),
    runtime_path: str | None = None,
    plugins_path: str | None = None,
) -> AppliedUpdateTransaction | None:
    validate_existing_install_edition(base_path, updater.edition)
    operational_exceptions = RECOVERABLE_EXCEPTIONS + (
        OSError,
        InsufficientDiskSpaceError,
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
        record_update_activation_identity(
            paths,
            task_id=task_id,
            edition=updater.edition,
            from_version=from_version,
            to_version=manifest.version,
            config_path=config_path,
        )
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
            artifact_record=archive_record,
            manifest=manifest,
            updater=updater,
        )
        if runtime_path is not None and runtime_dependencies_need_install(
            paths.staged_new_path, runtime_path=runtime_path
        ):
            state_directories = (*state_directories, runtime_path)
        plan_plugin_reconciliation(
            installed_plugins=os.path.join(paths.base_path, "plugins"),
            staged_plugins=os.path.join(paths.staged_new_path, "plugins"),
            target_version=manifest.core_version,
        )
        external_plugins = (
            plugins_path
            if plugins_path is not None
            and os.path.normcase(plugins_path)
            != os.path.normcase(os.path.join(base_path, "plugins"))
            else None
        )
        if external_plugins is not None:
            state_directories = (*state_directories, external_plugins)
        persisted_state = plan_persisted_update_state(
            paths,
            plan_replacement_roots(paths, updater.edition),
            state_files,
            state_directories,
        )
        if external_plugins is not None:
            if external_plugins not in persisted_state.directory_destinations:
                raise StateError(
                    "Configured plugin storage overlaps another changing runtime directory."
                )
            plugin_plan = plan_plugin_reconciliation(
                installed_plugins=external_plugins,
                staged_plugins=os.path.join(paths.staged_new_path, "plugins"),
                target_version=manifest.core_version,
            )
            require_disk_space_for_update(
                external_plugins,
                plugin_plan.required_bytes
                + install_entry_copy_size(os.path.join(paths.staged_new_path, "plugins")),
                0,
            )
        if not before_commit():
            cleanup_update_transaction(paths, logger)
            return None
        logger.info("Committing staged update transaction...")
        staged_directories: dict[str, str] = {}
        if external_plugins is not None:
            staged_directories[external_plugins] = stage_configured_plugins(
                installed_plugins=external_plugins,
                bundled_plugins=os.path.join(paths.staged_new_path, "plugins"),
                staging_parent=os.path.join(paths.transaction_path, "configured_plugins"),
                target_version=manifest.core_version,
                reservation_provider=reservation_provider,
            )
        reconcile_staged_plugins(
            installed_plugins=os.path.join(paths.base_path, "plugins"),
            staged_plugins=os.path.join(paths.staged_new_path, "plugins"),
            target_version=manifest.core_version,
            reservation_provider=reservation_provider,
        )
        return commit_staged_update(
            paths=paths,
            top_level_ignore_patterns=top_level_ignore_patterns,
            logger=logger,
            edition=updater.edition,
            state_files=state_files,
            state_directories=state_directories,
            staged_directories=staged_directories,
        )
    except (ValidationError, StateError, SecurityError):
        if os.path.exists(paths.transaction_path) and not os.path.exists(
            marker_path(paths.transaction_path, ROLLBACK_REQUIRED_MARKER),
        ):
            cleanup_update_transaction(paths, logger)
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
            cleanup_update_transaction(paths, logger)
        return None
