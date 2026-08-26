"""SoAI - Backup size estimation providers [backend/app/backup/backup_size_estimation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import os

from app.backup.backup_target_paths import (
    get_db_path,
    get_encryption_key_path,
    get_files_storage_path,
    get_gpu_settings_path,
    get_wallpaper_path,
)
from app.backup.backup_target_paths_extra import (
    get_core_config_path,
    get_logs_path,
    get_plugins_path,
)
from app.backup.internal_protocols import ConfigProviderProtocol, FilesProviderProtocol
from app.backup.sqlite_backup_source import get_sqlite_source_physical_size_bytes
from core.errors.exception_logging import log_exception
from core.errors.exceptions import DatabaseError, StateError, ValidationError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.filesystem.async_queries import async_isdir, async_islink, async_path_exists
from core.filesystem.size_calculation import get_path_size
from core.logging.protocols import StandardLogger
from core.logging.trace import get_logger
from core.plugins.file_suffixes import PLUGIN_CONFIG_FILE_SUFFIX
from core.validation.integers import is_strict_int

__all__ = ("estimate_backup_required_bytes",)

LOGGER_NAME = "SoAI.app.backup.backup_size_estimation"
OPERATION_BACKUP_PROVIDERS_ESTIMATE_BACKUP_REQUIRED_BYTES_ISLINK = (
    "backup.providers.estimate_backup_required_bytes.islink"
)
OPERATION_BACKUP_PROVIDERS_ESTIMATE_BACKUP_REQUIRED_BYTES_LIST_PLUGINS_DIR = (
    "backup.providers.estimate_backup_required_bytes.list_plugins_dir"
)
OPERATION_BACKUP_PROVIDERS_ESTIMATE_BACKUP_REQUIRED_BYTES_DATABASE = (
    "backup.providers.estimate_backup_required_bytes.database"
)


async def estimate_backup_required_bytes(
    config: ConfigProviderProtocol,
    files: FilesProviderProtocol,
    enabled_targets_map: dict[str, bool],
) -> int:
    logger = get_logger(LOGGER_NAME)
    if not isinstance(enabled_targets_map, dict):
        raise ValidationError(
            "enabled_targets_map must be a dict.",
            details={"type": type(enabled_targets_map).__name__},
        )
    total_bytes = 0
    paths_to_check: list[tuple[str, str]] = []
    if enabled_targets_map.get("DATABASE"):
        total_bytes += await _estimate_database_bytes(logger, get_db_path(config, files))
    if enabled_targets_map.get("CONFIG"):
        paths_to_check.append(("CONFIG", get_core_config_path(config, files)))
    if enabled_targets_map.get("ENCRYPTION_KEY"):
        paths_to_check.append(("ENCRYPTION_KEY", get_encryption_key_path(config, files)))
    if enabled_targets_map.get("GPU_SETTINGS"):
        paths_to_check.append(("GPU_SETTINGS", get_gpu_settings_path(config, files)))
    if enabled_targets_map.get("USER_DATA"):
        paths_to_check.append(("USER_DATA_WALLPAPER", get_wallpaper_path(config, files)))
        paths_to_check.append(("USER_DATA_FILES", get_files_storage_path(config, files)))
    if enabled_targets_map.get("LOGS"):
        paths_to_check.append(("LOGS", get_logs_path(config, files)))
    total_bytes += await _estimate_target_bytes(logger, paths_to_check)
    if enabled_targets_map.get("PLUGIN_CONFIGS"):
        total_bytes += await _estimate_plugin_config_bytes(logger, config, files)
    return total_bytes


async def _estimate_database_bytes(logger: StandardLogger, source_path: str) -> int:
    if not isinstance(source_path, str) or not source_path.strip():
        return 0
    if not await async_path_exists(source_path):
        return 0
    try:
        return await asyncio.to_thread(get_sqlite_source_physical_size_bytes, source_path)
    except RECOVERABLE_EXCEPTIONS as exception:
        log_exception(
            logger,
            exception,
            message="Failed to estimate SQLite database backup size.",
            operation=OPERATION_BACKUP_PROVIDERS_ESTIMATE_BACKUP_REQUIRED_BYTES_DATABASE,
            details={"source_path": source_path},
        )
        raise DatabaseError(
            "Failed to estimate SQLite database backup size.",
            details={"source_path": source_path},
            operation=OPERATION_BACKUP_PROVIDERS_ESTIMATE_BACKUP_REQUIRED_BYTES_DATABASE,
        ) from exception


async def _estimate_plugin_config_bytes(
    logger: StandardLogger,
    config: ConfigProviderProtocol,
    files: FilesProviderProtocol,
) -> int:
    plugin_configs_bytes = 0
    plugins_path = get_plugins_path(config, files)
    if not (
        isinstance(plugins_path, str) and plugins_path.strip() and await async_isdir(plugins_path)
    ):
        return 0
    try:
        entries = await asyncio.to_thread(os.listdir, plugins_path)
    except RECOVERABLE_EXCEPTIONS as exception:
        log_exception(
            logger,
            exception,
            message="Failed to list plugins directory for backup size estimation.",
            operation=OPERATION_BACKUP_PROVIDERS_ESTIMATE_BACKUP_REQUIRED_BYTES_LIST_PLUGINS_DIR,
            details={"plugins_path": plugins_path},
        )
        raise StateError(
            "Failed to list plugins directory for backup size estimation.",
            details={"plugins_path": plugins_path},
        ) from exception
    for entry in entries:
        if not entry.endswith(PLUGIN_CONFIG_FILE_SUFFIX):
            continue
        file_path = os.path.join(plugins_path, entry)
        try:
            if await async_islink(file_path):
                continue
        except RECOVERABLE_EXCEPTIONS as exception:
            log_exception(
                logger,
                exception,
                message="Failed to inspect plugin config symlink during backup size estimation.",
                operation=OPERATION_BACKUP_PROVIDERS_ESTIMATE_BACKUP_REQUIRED_BYTES_ISLINK,
                details={"file_path": file_path},
            )
            raise StateError(
                "Failed to inspect plugin config symlink during backup size estimation.",
                details={"file_path": file_path},
            ) from exception
        plugin_configs_bytes += await _coerce_positive_size(logger, "PLUGIN_CONFIGS", file_path)
    return plugin_configs_bytes


async def _estimate_target_bytes(
    logger: StandardLogger,
    paths_to_check: list[tuple[str, str]],
) -> int:
    total_bytes = 0
    for target_name, source_path in paths_to_check:
        total_bytes += await _coerce_positive_size(logger, target_name, source_path)
    return total_bytes


async def _coerce_positive_size(
    logger: StandardLogger,
    target_name: str,
    source_path: str,
) -> int:
    if not isinstance(source_path, str) or not source_path.strip():
        return 0
    if not await async_path_exists(source_path):
        return 0
    size_value = await get_path_size(source_path)
    if not is_strict_int(size_value):
        logger.warning(
            "Invalid %s size (%s): %s",
            target_name,
            source_path,
            size_value,
        )
        raise StateError(
            f"Failed to estimate size for {target_name}.",
            details={"target_name": target_name, "source_path": source_path},
        )
    if size_value < 0:
        raise StateError(
            f"Failed to estimate size for {target_name}.",
            details={
                "target_name": target_name,
                "source_path": source_path,
                "size_value": size_value,
            },
        )
    return size_value
