"""SoAI - Updater software installation workflow [backend/app/updater/software_install.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
from collections.abc import Callable
from typing import TYPE_CHECKING

from app.updater.disk_space import require_disk_space_for_update
from app.updater.download import download_update_file
from app.updater.install import (
    calculate_uncompressed_size_bytes,
    resolve_disk_space_tolerance_bytes,
)
from app.updater.release_bundle import PreparedReleaseBundle
from app.updater.release_manifest_types import ReleaseUpdateArchive
from app.updater.software_update.activation_state import prepare_update_activation
from app.updater.software_update.archive_installation import apply_update_from_zip
from app.updater.software_update.install_transaction import (
    AppliedUpdateTransaction,
    finalize_update_transaction,
)
from app.updater.software_update.install_transaction_persisted_state import (
    resolve_update_plugins_path,
    resolve_update_state_files,
)
from app.updater.target_runtime_preparation import prepare_target_update_runtime
from core.bootstrap.install_payload import write_install_manifest
from core.bootstrap.venv_paths import get_venv_path
from core.config.byte_sizes import mib_to_bytes, require_config_mib_to_bytes
from core.config.protocols import ConfigProtocol
from core.errors.exception_logging import log_handled_exception
from core.errors.exceptions import (
    ConfigurationError,
    InsufficientDiskSpaceError,
    StateError,
    ValidationError,
)
from core.logging.protocols import LoggerProtocol
from database.migrations.runtime import validate_database_path_for_upgrade

if TYPE_CHECKING:
    from core.hardware.protocols_storage import StorageManagerProtocol

__all__ = ("perform_update",)

OPERATION_APPLICATION_UPDATER_PERFORM_UPDATE_DISK_SPACE_CHECK = (
    "application_updater.perform_update.disk_space_check"
)

OPERATION_APPLICATION_UPDATER_PERFORM_UPDATE_CLEANUP_DOWNLOADED_ZIP = (
    "application_updater.perform_update.cleanup_downloaded_zip"
)
OPERATION_APPLICATION_UPDATER_MAX_ARCHIVE_BYTES = "application_updater.max_archive_bytes"
OPERATION_APPLICATION_UPDATER_INSTALL_METADATA = "application_updater.install_metadata"
DEFAULT_UPDATER_MAX_ARCHIVE_MB = 2048
OPERATION_APPLICATION_UPDATER_STATE_PREFLIGHT = "application_updater.state_preflight"


def perform_update(
    *,
    logger: LoggerProtocol,
    base_path: str,
    temp_path: str,
    platform_id: str,
    config: ConfigProtocol,
    config_path: str,
    download_timeout: float,
    release_bundle: PreparedReleaseBundle,
    reservation_provider: StorageManagerProtocol,
    before_commit: Callable[[], bool],
    task_id: str,
    from_version: str,
) -> bool:
    downloaded_zip = None
    update_transaction: AppliedUpdateTransaction | None = None
    update_success = False
    try:
        plugins_path = resolve_update_plugins_path(config)
        try:
            validate_database_path_for_upgrade(config.get_str("DATA.DATABASE.PATHS.SYSTEM_DB"))
        except (OSError, StateError, ValidationError) as exception:
            log_handled_exception(
                logger,
                exception,
                message="Persisted database state cannot be upgraded safely.",
                operation=OPERATION_APPLICATION_UPDATER_STATE_PREFLIGHT,
                level="error",
            )
            return False
        logger.info("Downloading signed update archive...")
        max_archive_bytes = _resolve_max_archive_bytes(config, logger=logger)
        if max_archive_bytes is None:
            return False
        archive_record = release_bundle.artifact_record
        if not isinstance(archive_record, ReleaseUpdateArchive):
            raise ValidationError("Archive update received a non-archive release artifact.")
        if archive_record.size_bytes > max_archive_bytes:
            logger.error("Signed update archive exceeds the configured archive size limit.")
            return False
        downloaded_zip = download_update_file(
            logger,
            url=release_bundle.artifact_download_url,
            timeout=download_timeout,
            temp_path=temp_path,
            max_download_bytes=archive_record.size_bytes,
            reservation_provider=reservation_provider,
            suffix=".zip",
        )
        if downloaded_zip is None:
            return False
        zip_path = downloaded_zip.file_path
        if (
            downloaded_zip.size_bytes != archive_record.size_bytes
            or downloaded_zip.sha256_hex != release_bundle.expected_artifact_sha256
        ):
            logger.error("Downloaded update archive does not match its signed release record.")
            return False
        uncompressed_size_bytes = calculate_uncompressed_size_bytes(zip_path, logger)
        if uncompressed_size_bytes is None:
            return False
        tolerance_bytes = resolve_disk_space_tolerance_bytes(config, logger)
        if tolerance_bytes is None:
            return False
        try:
            require_disk_space_for_update(
                base_path,
                uncompressed_size_bytes,
                tolerance_bytes,
                operation=OPERATION_APPLICATION_UPDATER_PERFORM_UPDATE_DISK_SPACE_CHECK,
            )
        except (InsufficientDiskSpaceError, ValidationError, StateError) as exception:
            log_handled_exception(
                logger,
                exception,
                message="Update disk space check failed.",
                operation=OPERATION_APPLICATION_UPDATER_PERFORM_UPDATE_DISK_SPACE_CHECK,
                level="error",
            )
            logger.error("Update aborted due to insufficient disk space.")
            return False
        logger.info("Applying update...")
        update_transaction = apply_update_from_zip(
            zip_path=zip_path,
            base_path=base_path,
            logger=logger,
            platform_id=platform_id,
            archive_record=archive_record,
            reservation_provider=reservation_provider,
            manifest=release_bundle.manifest,
            updater=release_bundle.updater,
            before_commit=before_commit,
            task_id=task_id,
            from_version=from_version,
            config_path=config_path,
            runtime_path=get_venv_path(base_path),
            state_files=resolve_update_state_files(config, config_path),
            plugins_path=plugins_path,
        )
        if update_transaction is None:
            logger.warning("Failed to apply update.")
            return False
        try:
            write_install_manifest(
                base_path,
                release_bundle.artifact_download_url,
                reservation_provider=reservation_provider,
                edition=release_bundle.manifest.edition,
                product_version=release_bundle.manifest.version,
                core_version=release_bundle.manifest.core_version,
            )
        except (OSError, InsufficientDiskSpaceError, StateError, ValidationError) as exception:
            log_handled_exception(
                logger,
                exception,
                message="Installation metadata could not be updated.",
                operation=OPERATION_APPLICATION_UPDATER_INSTALL_METADATA,
                level="error",
            )
            return False
        if not prepare_target_update_runtime(
            base_path=base_path,
            config_path=config_path,
            config=config,
            updater=release_bundle.updater,
            logger=logger,
        ):
            return False
        prepare_update_activation(update_transaction)
        update_success = True
        return True
    finally:
        if update_transaction is not None and (not update_success):
            finalize_update_transaction(
                transaction=update_transaction,
                update_success=False,
                logger=logger,
            )
        if downloaded_zip and os.path.exists(downloaded_zip.file_path):
            try:
                os.remove(downloaded_zip.file_path)
            except OSError as exception:
                log_handled_exception(
                    logger,
                    exception,
                    message="Failed to remove downloaded update archive (non-critical).",
                    operation=OPERATION_APPLICATION_UPDATER_PERFORM_UPDATE_CLEANUP_DOWNLOADED_ZIP,
                    details={"path": downloaded_zip.file_path},
                    level="debug",
                )


def _resolve_max_archive_bytes(
    config: ConfigProtocol,
    *,
    logger: LoggerProtocol,
) -> int | None:
    raw = config.get("SYSTEM.UPDATER.MAX_ARCHIVE_MB")
    if raw is None:
        return mib_to_bytes(DEFAULT_UPDATER_MAX_ARCHIVE_MB)
    try:
        return require_config_mib_to_bytes(
            raw,
            field="SYSTEM.UPDATER.MAX_ARCHIVE_MB",
            invalid_message="SYSTEM.UPDATER.MAX_ARCHIVE_MB must be a valid integer.",
            positive_message="SYSTEM.UPDATER.MAX_ARCHIVE_MB must be greater than 0.",
            allow_zero=False,
        )
    except ConfigurationError as exception:
        log_handled_exception(
            logger,
            exception,
            message="Invalid updater max archive size configuration.",
            operation=OPERATION_APPLICATION_UPDATER_MAX_ARCHIVE_BYTES,
            level="error",
        )
        return None
