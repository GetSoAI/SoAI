"""SoAI - Updater software installation workflow [backend/app/updater/software_install.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
import sys
from subprocess import CalledProcessError
from typing import TYPE_CHECKING

from app.updater.disk_space import require_disk_space_for_update
from app.updater.download import download_zip
from app.updater.install import (
    calculate_uncompressed_size_bytes,
    resolve_disk_space_tolerance_bytes,
)
from app.updater.release_bundle import PreparedReleaseBundle
from app.updater.software_update.install_transaction import (
    AppliedUpdateTransaction,
    apply_update_from_zip,
    finalize_update_transaction,
)
from core.config.byte_sizes import mib_to_bytes, require_config_mib_to_bytes
from core.config.numeric import coerce_int_or_none
from core.config.protocols import ConfigProtocol
from core.errors.exception_logging import log_exception, log_handled_exception
from core.errors.exceptions import (
    ConfigurationError,
    InsufficientDiskSpaceError,
    StateError,
    ValidationError,
)
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.protocols import LoggerProtocol
from core.system.commands import run_argv_capture

if TYPE_CHECKING:
    from core.hardware.protocols_storage import StorageManagerProtocol

__all__ = ("perform_update",)

OPERATION_APPLICATION_UPDATER_PERFORM_UPDATE_DISK_SPACE_CHECK = (
    "application_updater.perform_update.disk_space_check"
)

OPERATION_APPLICATION_UPDATER_PERFORM_UPDATE_CLEANUP_DOWNLOADED_ZIP = (
    "application_updater.perform_update.cleanup_downloaded_zip"
)
OPERATION_APPLICATION_UPDATER_POST_UPDATE_HOOK = "application_updater.post_update_hook"
OPERATION_APPLICATION_UPDATER_MAX_ARCHIVE_BYTES = "application_updater.max_archive_bytes"
DEFAULT_UPDATER_MAX_ARCHIVE_MB = 2048


def perform_update(
    *,
    logger: LoggerProtocol,
    base_path: str,
    temp_path: str,
    platform_id: str,
    config: ConfigProtocol,
    download_timeout: float,
    release_bundle: PreparedReleaseBundle,
    reservation_provider: StorageManagerProtocol,
) -> bool:
    downloaded_zip = None
    update_transaction: AppliedUpdateTransaction | None = None
    update_success = False
    try:
        logger.info("Downloading signed update archive...")
        max_archive_bytes = _resolve_max_archive_bytes(config, logger=logger)
        if max_archive_bytes is None:
            return False
        archive_record = release_bundle.archive_record
        if archive_record.size_bytes > max_archive_bytes:
            logger.error("Signed update archive exceeds the configured archive size limit.")
            return False
        downloaded_zip = download_zip(
            logger,
            url=release_bundle.archive_download_url,
            timeout=download_timeout,
            temp_path=temp_path,
            max_archive_bytes=archive_record.size_bytes,
            reservation_provider=reservation_provider,
        )
        if downloaded_zip is None:
            return False
        zip_path = downloaded_zip.file_path
        if (
            downloaded_zip.size_bytes != archive_record.size_bytes
            or downloaded_zip.sha256_hex != release_bundle.expected_archive_sha256
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
        )
        if update_transaction is None:
            logger.warning("Failed to apply update.")
            return False
        hook_module = release_bundle.updater.post_update_hook_module
        hook_script = os.path.join(
            base_path,
            release_bundle.updater.post_update_hook_relative_path,
        )
        if os.path.exists(hook_script):
            logger.info("Executing post-update hook script...")
            hook_timeout = _resolve_post_update_hook_timeout_seconds(config, logger=logger)
            if hook_timeout is None:
                return False
            try:
                pythonpath = os.pathsep.join((os.path.join(base_path, "backend"), base_path))
                env = dict(os.environ)
                existing_pythonpath = env.get("PYTHONPATH")
                env["PYTHONPATH"] = (
                    f"{pythonpath}{os.pathsep}{existing_pythonpath}"
                    if existing_pythonpath
                    else pythonpath
                )
                result = run_argv_capture(
                    [sys.executable, "-m", hook_module],
                    cwd=base_path,
                    timeout=hook_timeout,
                    check=True,
                    env=env,
                )
                logger.info("Post-update hook finished successfully:\n%s", result.stdout)
            except CalledProcessError as exception:
                log_handled_exception(
                    logger,
                    exception,
                    message="Post-update hook failed.",
                    operation=OPERATION_APPLICATION_UPDATER_POST_UPDATE_HOOK,
                    details={
                        "returncode": exception.returncode,
                        "stdout": str(exception.output or "").strip(),
                        "stderr": str(exception.stderr or "").strip(),
                    },
                    level="error",
                )
                return False
            except RECOVERABLE_EXCEPTIONS as exception:
                log_exception(
                    logger,
                    exception,
                    message="Post-update hook failed.",
                    operation=OPERATION_APPLICATION_UPDATER_POST_UPDATE_HOOK,
                    level="error",
                )
                return False
        update_success = True
        if not finalize_update_transaction(
            transaction=update_transaction,
            update_success=True,
            logger=logger,
        ):
            logger.error("Update transaction finalization failed.")
            update_success = False
            return False
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


def _resolve_post_update_hook_timeout_seconds(
    config: ConfigProtocol,
    *,
    logger: LoggerProtocol,
) -> int | None:
    raw = config.get("SYSTEM.UPDATER.POST_UPDATE_HOOK_TIMEOUT_SEC", 7200)
    if raw is None:
        return 7200
    return coerce_int_or_none(
        raw,
        minimum=1,
        invalid_message="SYSTEM.UPDATER.POST_UPDATE_HOOK_TIMEOUT_SEC must be a positive integer.",
        below_minimum_message="SYSTEM.UPDATER.POST_UPDATE_HOOK_TIMEOUT_SEC must be greater than 0.",
        logger=logger,
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
