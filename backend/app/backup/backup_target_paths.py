"""SoAI - Backup path resolution and target selection [backend/app/backup/backup_target_paths.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os

from app.backup.internal_protocols import ConfigProviderProtocol, FilesProviderProtocol
from core.errors.exceptions import StateError
from core.validation.booleans import parse_bool

__all__ = (
    "all_enabled_targets_completed",
    "get_base_path",
    "get_db_path",
    "get_enabled_backup_targets",
    "get_encryption_key_path",
    "get_files_storage_path",
    "get_gpu_settings_path",
    "get_wallpaper_path",
)

_BACKUP_TARGET_DEFAULTS: tuple[tuple[str, bool], ...] = (
    ("DATABASE", True),
    ("CONFIG", True),
    ("ENCRYPTION_KEY", True),
    ("PLUGIN_CONFIGS", True),
    ("GPU_SETTINGS", True),
    ("USER_DATA", True),
    ("LOGS", False),
)


def get_base_path(config: ConfigProviderProtocol) -> str:
    base_path = config.get("SYSTEM.PATHS.BASE")
    if not isinstance(base_path, str) or not base_path.strip():
        raise StateError("SYSTEM.PATHS.BASE is not configured.")
    return base_path


def get_enabled_backup_targets(config: ConfigProviderProtocol) -> dict[str, bool]:
    targets = config.get("DATA.BACKUP.TARGETS", {})
    if not isinstance(targets, dict):
        targets = {}
    return {
        target_name: parse_bool(targets.get(target_name, default_value), default=default_value)
        for target_name, default_value in _BACKUP_TARGET_DEFAULTS
    }


def all_enabled_targets_completed(
    targets_enabled: dict[str, bool],
    targets_completed: dict[str, bool],
) -> bool:
    for target_name, is_enabled in targets_enabled.items():
        if is_enabled and not targets_completed.get(target_name, False):
            return False
    return True


def resolve_required_path(
    config: ConfigProviderProtocol,
    files: FilesProviderProtocol,
    key: str,
    *,
    error_message: str,
    absolute: bool = False,
) -> str:
    raw_value = config.get(key)
    if not isinstance(raw_value, str) or not raw_value.strip():
        raise StateError(error_message)
    resolved_path = files.resolve_path(raw_value)
    return os.path.abspath(resolved_path) if absolute else resolved_path


def get_db_path(config: ConfigProviderProtocol, files: FilesProviderProtocol) -> str:
    return resolve_required_path(
        config,
        files,
        "DATA.DATABASE.PATHS.SYSTEM_DB",
        error_message="DATA.DATABASE.PATHS.SYSTEM_DB is missing or invalid.",
    )


def get_encryption_key_path(config: ConfigProviderProtocol, files: FilesProviderProtocol) -> str:
    return resolve_required_path(
        config,
        files,
        "SYSTEM.PATHS.SYSTEM_ENCRYPTION_KEY",
        error_message="SYSTEM.PATHS.SYSTEM_ENCRYPTION_KEY is missing or invalid.",
    )


def get_files_storage_path(config: ConfigProviderProtocol, files: FilesProviderProtocol) -> str:
    return resolve_required_path(
        config,
        files,
        "DATA.FILES.PATHS.FILES_STORAGE",
        error_message="DATA.FILES.PATHS.FILES_STORAGE is missing or invalid.",
    )


def get_wallpaper_path(config: ConfigProviderProtocol, files: FilesProviderProtocol) -> str:
    return resolve_required_path(
        config,
        files,
        "SERVER.WEBUI.WALLPAPER_STORAGE_PATH",
        error_message="SERVER.WEBUI.WALLPAPER_STORAGE_PATH is missing or invalid.",
    )


def get_gpu_settings_path(config: ConfigProviderProtocol, files: FilesProviderProtocol) -> str:
    return resolve_required_path(
        config,
        files,
        "SYSTEM.HARDWARE.GPU_SETTINGS_SLOTS_PATH",
        error_message="SYSTEM.HARDWARE.GPU_SETTINGS_SLOTS_PATH is missing or invalid.",
    )
