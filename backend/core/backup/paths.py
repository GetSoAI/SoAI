"""SoAI - Backup manifest relative paths and restore target mappings [backend/core/backup/paths.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import posixpath

__all__ = (
    "get_backup_relative_config_path",
    "get_backup_relative_database_path",
    "get_backup_relative_encryption_key_path",
    "get_backup_relative_files_path",
    "get_backup_relative_gpu_settings_path",
    "get_backup_relative_logs_path",
    "get_backup_relative_plugin_config_path",
    "get_backup_relative_wallpaper_path",
)

_DATABASE_PATH = ("data", "database", "soai.db")
_CONFIG_PATH = ("data", "config", "config.yaml")
_GPU_SETTINGS_PATH = ("data", "gpu", "gpu_settings_slots.json")
_ENCRYPTION_KEY_PATH = ("data", "secret.key")
_FILES_PATH = ("data", "files")
_LOGS_PATH = ("data", "logs")
_WALLPAPER_PATH = ("data", "wallpaper")

ALLOWED_RESTORE_FILE_DESTINATION_KEYS: tuple[tuple[tuple[str, ...], str], ...] = (
    (_CONFIG_PATH, "config_path"),
    (_GPU_SETTINGS_PATH, "gpu_settings_path"),
    (_ENCRYPTION_KEY_PATH, "encryption_key_path"),
    (_DATABASE_PATH, "db_path"),
)
ALLOWED_RESTORE_DIRECTORY_DESTINATION_KEYS: tuple[tuple[tuple[str, ...], str], ...] = (
    (_FILES_PATH, "files_storage_path"),
    (_LOGS_PATH, "logs_path"),
    (_WALLPAPER_PATH, "wallpaper_path"),
)


def get_backup_relative_database_path() -> str:
    return posixpath.join(*_DATABASE_PATH)


def get_backup_relative_config_path() -> str:
    return posixpath.join(*_CONFIG_PATH)


def get_backup_relative_gpu_settings_path() -> str:
    return posixpath.join(*_GPU_SETTINGS_PATH)


def get_backup_relative_encryption_key_path() -> str:
    return posixpath.join(*_ENCRYPTION_KEY_PATH)


def get_backup_relative_files_path() -> str:
    return posixpath.join(*_FILES_PATH)


def get_backup_relative_logs_path() -> str:
    return posixpath.join(*_LOGS_PATH)


def get_backup_relative_wallpaper_path() -> str:
    return posixpath.join(*_WALLPAPER_PATH)


def get_backup_relative_plugin_config_path(file_name: str) -> str:
    return posixpath.join("plugins", file_name)
