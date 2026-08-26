"""SoAI - CLI status storage inspection [backend/app/cli/status/storage.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
import shutil

from app.cli.offline_mode import resolve_config_path
from app.cli.status.types import StorageInfo
from app.config.io import ConfigIO, ConfigIODependencies
from core.config.layout import ConfigPathResolutionError, apply_config_layout
from core.errors.exception_logging import log_handled_exception
from core.errors.exceptions import ConfigurationError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.filesystem.open_files import open_text
from core.logging.trace import get_logger
from core.meta.paths import get_database_path, get_soai_log_path

__all__ = ("get_storage_quick",)

LOGGER_NAME = "SoAI.app.cli.storage"
OPERATION = "app.cli.status.get_storage_quick"


def _resolve_status_config_path(base_dir: str) -> str:
    return resolve_config_path(base_dir)


def _try_resolve_storage_paths_from_config(
    base_dir: str,
) -> tuple[str | None, str | None, str | None]:
    config_path = _resolve_status_config_path(base_dir)
    if not os.path.exists(config_path):
        return None, None, None

    logger = get_logger(LOGGER_NAME)
    try:
        with open_text(config_path, encoding="utf-8") as handle:
            raw_contents = handle.read()
    except OSError:
        return None, None, None

    if not raw_contents.strip():
        return None, None, None

    config_io = ConfigIO(
        ConfigIODependencies(
            base_path=base_dir,
            core_config_path=config_path,
            plugins_path=None,
            lock_directory=None,
            logger=logger,
        ),
    )
    try:
        parsed = config_io.parse_config_contents(
            raw_contents,
            config_name="core",
            config_path=config_path,
        )
        config_dict = dict(parsed)
        system_data_path = apply_config_layout(config_dict, base_path=os.path.abspath(base_dir))
    except (ConfigurationError, ConfigPathResolutionError) as exception:
        log_handled_exception(
            logger,
            exception,
            message="Failed to load config paths for CLI storage output (non-critical).",
            operation=OPERATION,
            level="debug",
        )
        return None, None, None
    except RECOVERABLE_EXCEPTIONS as exception:
        log_handled_exception(
            logger,
            exception,
            message="Failed to load config paths for CLI storage output (non-critical).",
            operation=OPERATION,
            level="debug",
        )
        return None, None, None

    data_value = config_dict.get("DATA")
    database_value = data_value.get("DATABASE") if isinstance(data_value, dict) else None
    database_paths_value = database_value.get("PATHS") if isinstance(database_value, dict) else None
    db_path_value = (
        database_paths_value.get("SYSTEM_DB") if isinstance(database_paths_value, dict) else None
    )
    db_path = str(db_path_value).strip() if isinstance(db_path_value, str) else None
    if not db_path:
        db_path = None

    observability_value = config_dict.get("OBSERVABILITY")
    log_manager_value = (
        observability_value.get("LOGGING") if isinstance(observability_value, dict) else None
    )
    logs_dir_value = (
        log_manager_value.get("LOGS_PATH") if isinstance(log_manager_value, dict) else None
    )
    logs_dir = str(logs_dir_value).strip() if isinstance(logs_dir_value, str) else None
    if not logs_dir:
        logs_dir = None
    main_log_name_value = (
        log_manager_value.get("MAIN_LOG") if isinstance(log_manager_value, dict) else None
    )
    main_log_name = (
        str(main_log_name_value).strip()
        if isinstance(main_log_name_value, str) and main_log_name_value.strip()
        else "soai.log"
    )
    main_log_path = os.path.join(logs_dir, main_log_name) if logs_dir else None

    system_data_for_usage: str | None = None
    if system_data_path and os.path.exists(system_data_path):
        system_data_for_usage = system_data_path
    return db_path, main_log_path, system_data_for_usage


def get_storage_quick(base_dir: str) -> StorageInfo | None:
    try:
        db_path, log_path, disk_usage_path = _try_resolve_storage_paths_from_config(base_dir)
        if db_path is None:
            db_path = get_database_path(base_dir)
        if log_path is None:
            log_path = get_soai_log_path(base_dir)
        usage_path = disk_usage_path if disk_usage_path is not None else base_dir
        db_size = os.stat(db_path).st_size if os.path.exists(db_path) else 0
        log_size = os.stat(log_path).st_size if os.path.exists(log_path) else 0
        disk_usage = shutil.disk_usage(usage_path)
        return StorageInfo(
            db_size_bytes=int(db_size),
            log_size_bytes=int(log_size),
            disk_total_bytes=int(disk_usage.total),
            disk_free_bytes=int(disk_usage.free),
        )
    except RECOVERABLE_EXCEPTIONS as exception:
        log_handled_exception(
            get_logger(LOGGER_NAME),
            exception,
            message="Failed to get storage info (non-critical).",
            operation=OPERATION,
            level="debug",
        )
        return None
