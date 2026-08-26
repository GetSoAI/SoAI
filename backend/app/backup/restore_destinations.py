"""SoAI - Backup restore destination helpers [backend/app/backup/restore_destinations.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
import posixpath

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
from core.backup.paths import (
    ALLOWED_RESTORE_DIRECTORY_DESTINATION_KEYS,
    ALLOWED_RESTORE_FILE_DESTINATION_KEYS,
)
from core.errors.exceptions import SecurityError, ValidationError

__all__ = (
    "build_restore_destinations",
    "ensure_restore_destination_is_safe",
    "resolve_restore_destination",
)


def ensure_restore_destination_is_safe(destination_path: str) -> None:
    if not isinstance(destination_path, str) or not destination_path.strip():
        raise ValidationError("destination_path is required.")
    if not os.path.isabs(destination_path):
        raise SecurityError(f"Restore destination must be an absolute path: {destination_path}")
    candidate = os.path.abspath(destination_path)
    if candidate == os.sep:
        raise SecurityError("Refusing to restore to filesystem root.")
    drive, tail = os.path.splitdrive(candidate)
    prefix = (drive + os.sep) if drive else os.sep
    segments = tail.strip(os.sep).split(os.sep) if tail.strip(os.sep) else []
    for segment in segments:
        prefix = os.path.join(prefix, segment)
        if os.path.lexists(prefix) and os.path.islink(prefix):
            raise SecurityError(f"Restore destination traverses a symlinked path segment: {prefix}")


def resolve_restore_destination(rel_path: str, *, restore_destinations: dict[str, str]) -> str:
    if not isinstance(restore_destinations, dict) or not restore_destinations:
        raise ValidationError("restore_destinations are required.")

    def _require_path(key: str) -> str:
        raw_value = restore_destinations.get(key)
        if not isinstance(raw_value, str) or not raw_value.strip():
            raise ValidationError(f"Restore destination '{key}' is required.")
        return raw_value

    destination_key: str | None = None
    for path_parts, key in ALLOWED_RESTORE_FILE_DESTINATION_KEYS:
        if rel_path == posixpath.join(*path_parts):
            destination_key = key
            break
    if destination_key is None:
        for path_parts, key in ALLOWED_RESTORE_DIRECTORY_DESTINATION_KEYS:
            if rel_path == posixpath.join(*path_parts):
                destination_key = key
                break

    if destination_key is not None:
        destination = _require_path(destination_key)
    elif rel_path.startswith("plugins/"):
        plugin_file_name = rel_path[len("plugins/") :]
        destination = os.path.join(_require_path("plugins_path"), plugin_file_name)
    else:
        raise SecurityError(f"Restore target is not allowed: {rel_path}")

    ensure_restore_destination_is_safe(destination)
    return os.path.abspath(destination)


def build_restore_destinations(
    config: ConfigProviderProtocol,
    files: FilesProviderProtocol,
) -> dict[str, str]:
    destinations = {
        "db_path": os.path.abspath(get_db_path(config, files)),
        "encryption_key_path": os.path.abspath(get_encryption_key_path(config, files)),
        "files_storage_path": os.path.abspath(get_files_storage_path(config, files)),
        "gpu_settings_path": os.path.abspath(get_gpu_settings_path(config, files)),
        "config_path": os.path.abspath(get_core_config_path(config, files)),
        "wallpaper_path": os.path.abspath(get_wallpaper_path(config, files)),
        "logs_path": os.path.abspath(get_logs_path(config, files)),
        "plugins_path": os.path.abspath(get_plugins_path(config, files)),
    }
    for dest in destinations.values():
        ensure_restore_destination_is_safe(dest)
    return destinations
