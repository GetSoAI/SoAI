"""SoAI - Backup path resolution and target selection [backend/app/backup/backup_target_paths.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os

from app.backup.internal_protocols import (
    ConfigProviderProtocol,
    FilesProviderProtocol,
    UserDataSource,
)
from core.backup.paths import (
    get_backup_relative_files_path,
    get_backup_relative_user_files_path,
    get_backup_relative_wallpaper_path,
)
from core.errors.exceptions import StateError, ValidationError
from core.files.path_policy import is_path_inside_directory
from core.files.workspace_path import resolve_existing_workspace_directory
from core.validation.booleans import parse_bool
from core.workspaces.user_workspace_path import managed_user_workspace_root

__all__ = (
    "all_enabled_targets_completed",
    "get_base_path",
    "get_db_path",
    "get_enabled_backup_targets",
    "get_encryption_key_path",
    "get_files_storage_path",
    "get_gpu_settings_path",
    "get_user_data_source_paths",
    "get_user_files_path",
    "get_wallpaper_path",
    "select_user_data_sources",
)

_FILES_STORAGE_PATH_KEY = "DATA.FILES.PATHS.FILES_STORAGE"
_WALLPAPER_PATH_KEY = "SERVER.WEBUI.WALLPAPER_STORAGE_PATH"

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
        _FILES_STORAGE_PATH_KEY,
        error_message=f"{_FILES_STORAGE_PATH_KEY} is missing or invalid.",
    )


def get_wallpaper_path(config: ConfigProviderProtocol, files: FilesProviderProtocol) -> str:
    return resolve_required_path(
        config,
        files,
        _WALLPAPER_PATH_KEY,
        error_message=f"{_WALLPAPER_PATH_KEY} is missing or invalid.",
    )


def get_gpu_settings_path(config: ConfigProviderProtocol, files: FilesProviderProtocol) -> str:
    return resolve_required_path(
        config,
        files,
        "SYSTEM.HARDWARE.GPU_SETTINGS_SLOTS_PATH",
        error_message="SYSTEM.HARDWARE.GPU_SETTINGS_SLOTS_PATH is missing or invalid.",
    )


def get_user_files_path(files: FilesProviderProtocol) -> str:
    return files.resolve_path(managed_user_workspace_root())


def _configured_user_data_sources(
    config: ConfigProviderProtocol,
    files: FilesProviderProtocol,
) -> tuple[tuple[str, UserDataSource], ...]:
    return (
        (
            _WALLPAPER_PATH_KEY,
            UserDataSource(get_backup_relative_wallpaper_path(), get_wallpaper_path(config, files)),
        ),
        (
            _FILES_STORAGE_PATH_KEY,
            UserDataSource(get_backup_relative_files_path(), get_files_storage_path(config, files)),
        ),
    )


def get_user_data_source_paths(
    config: ConfigProviderProtocol,
    files: FilesProviderProtocol,
) -> tuple[str, ...]:
    return (
        *(source.source_path for _key, source in _configured_user_data_sources(config, files)),
        get_user_files_path(files),
    )


def _require_separate_user_data_folders(folders: tuple[tuple[str, str], ...]) -> None:
    real_folders = tuple((label, path, os.path.realpath(path)) for label, path in folders)
    for index, (first_label, first_path, first_real_path) in enumerate(real_folders):
        for second_label, second_path, second_real_path in real_folders[index + 1 :]:
            if is_path_inside_directory(first_real_path, second_real_path) or (
                is_path_inside_directory(second_real_path, first_real_path)
            ):
                raise ValidationError(
                    f"{first_label} ({first_path}) and {second_label} ({second_path}) must not contain each other, because a backup could not restore them separately. Move a configured folder to a separate location, update its setting and back up again."
                )


def select_user_data_sources(
    config: ConfigProviderProtocol,
    files: FilesProviderProtocol,
) -> tuple[UserDataSource, ...]:
    configured_sources = _configured_user_data_sources(config, files)
    sources = tuple(source for _key, source in configured_sources)
    existing_folders = tuple(
        (setting_key, source.source_path)
        for setting_key, source in configured_sources
        if os.path.isdir(source.source_path)
    )
    configured_workspace_root = get_user_files_path(files)
    if not os.path.lexists(configured_workspace_root):
        _require_separate_user_data_folders(existing_folders)
        return sources
    workspace_root = resolve_existing_workspace_directory(configured_workspace_root)
    _require_separate_user_data_folders(
        (*existing_folders, ("the account workspaces folder", workspace_root))
    )
    return (*sources, UserDataSource(get_backup_relative_user_files_path(), workspace_root))
