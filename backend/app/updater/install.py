"""SoAI - Update installation from zip with backup and verification [backend/app/updater/install.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import fnmatch
import os
import zipfile

from app.backup.copy_no_symlinks.constants import UPDATER_EXCLUSIONS
from core.archives.resource_limits import default_archive_resource_limits
from core.archives.zip_directory_budget import validate_zip_directory_budget
from core.config.byte_sizes import require_config_mib_to_bytes
from core.config.protocols import ConfigProtocol
from core.errors.exception_logging import log_exception, log_handled_exception
from core.errors.exceptions import ConfigurationError, ValidationError
from core.filesystem.open_files import open_binary
from core.logging.protocols import LoggerProtocol

__all__ = (
    "calculate_uncompressed_size_bytes",
    "estimate_installation_size",
    "resolve_disk_space_tolerance_bytes",
)

OPERATION_APPLICATION_UPDATER_CALCULATE_UNCOMPRESSED_SIZE = (
    "application_updater.calculate_uncompressed_size"
)
OPERATION_APPLICATION_UPDATER_DISK_SPACE_TOLERANCE = "application_updater.disk_space_tolerance"
OPERATION_APPLICATION_UPDATER_ESTIMATE_INSTALLATION_SIZE = (
    "application_updater.estimate_installation_size"
)


def resolve_disk_space_tolerance_bytes(
    config: ConfigProtocol,
    logger: LoggerProtocol,
) -> int | None:
    hardware_manager_config = config.get("SYSTEM.HARDWARE")
    if not isinstance(hardware_manager_config, dict):
        logger.error("SYSTEM.HARDWARE configuration section is missing or invalid in config.yaml.")
        return None
    raw_tolerance = config.get("SYSTEM.HARDWARE.DISK_FREE_SPACE_TOLERANCE_MB")
    if raw_tolerance is None:
        logger.error("SYSTEM.HARDWARE.DISK_FREE_SPACE_TOLERANCE_MB is missing in config.yaml.")
        return None
    try:
        return require_config_mib_to_bytes(
            raw_tolerance,
            field="SYSTEM.HARDWARE.DISK_FREE_SPACE_TOLERANCE_MB",
            invalid_message=(
                "SYSTEM.HARDWARE.DISK_FREE_SPACE_TOLERANCE_MB is not a valid integer."
            ),
            positive_message="SYSTEM.HARDWARE.DISK_FREE_SPACE_TOLERANCE_MB must be non-negative.",
            allow_zero=True,
        )
    except ConfigurationError as exception:
        log_handled_exception(
            logger,
            exception,
            message="Invalid disk space tolerance configuration.",
            operation=OPERATION_APPLICATION_UPDATER_DISK_SPACE_TOLERANCE,
            level="error",
        )
        return None


def estimate_installation_size(base_path: str, logger: LoggerProtocol) -> int:
    total_size = 0
    try:
        for dirpath, dirnames, filenames in os.walk(base_path):
            dirnames[:] = [
                dirname
                for dirname in dirnames
                if not any(fnmatch.fnmatch(dirname, pattern) for pattern in UPDATER_EXCLUSIONS)
            ]
            for filename in filenames:
                if any(fnmatch.fnmatch(filename, pattern) for pattern in UPDATER_EXCLUSIONS):
                    continue
                filepath = os.path.join(dirpath, filename)
                try:
                    total_size += os.path.getsize(filepath)
                except OSError:
                    continue
    except OSError as exception:
        log_exception(
            logger,
            exception,
            message="Failed to estimate installation size",
            operation=OPERATION_APPLICATION_UPDATER_ESTIMATE_INSTALLATION_SIZE,
        )
        return 0
    return total_size


def calculate_uncompressed_size_bytes(zip_path: str, logger: LoggerProtocol) -> int | None:
    try:
        with open_binary(zip_path, mode="rb") as archive_handle:
            validate_zip_directory_budget(archive_handle, default_archive_resource_limits())
            with zipfile.ZipFile(archive_handle, "r") as zip_file:
                uncompressed_size_bytes = sum(info.file_size for info in zip_file.infolist())
    except (ValidationError, zipfile.BadZipFile) as exception:
        log_exception(
            logger,
            exception,
            message="Failed to read zip file for size calculation",
            operation=OPERATION_APPLICATION_UPDATER_CALCULATE_UNCOMPRESSED_SIZE,
            details={"zip_path": zip_path},
        )
        return None
    return uncompressed_size_bytes
