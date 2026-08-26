"""SoAI - Backup plugin, log, and config path resolution [backend/app/backup/backup_target_paths_extra.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from app.backup.backup_target_paths import resolve_required_path
from app.backup.internal_protocols import ConfigProviderProtocol, FilesProviderProtocol

__all__ = (
    "get_core_config_path",
    "get_logs_path",
    "get_plugins_path",
)


def get_plugins_path(config: ConfigProviderProtocol, files: FilesProviderProtocol) -> str:
    return resolve_required_path(
        config,
        files,
        "PLUGINS.PATHS.PLUGINS",
        error_message="PLUGINS.PATHS.PLUGINS is missing or invalid.",
    )


def get_logs_path(config: ConfigProviderProtocol, files: FilesProviderProtocol) -> str:
    return resolve_required_path(
        config,
        files,
        "OBSERVABILITY.LOGGING.LOGS_PATH",
        error_message="OBSERVABILITY.LOGGING.LOGS_PATH is missing or invalid.",
    )


def get_core_config_path(config: ConfigProviderProtocol, files: FilesProviderProtocol) -> str:
    return resolve_required_path(
        config,
        files,
        "CONFIG_PATH",
        error_message="CONFIG_PATH is missing or invalid.",
        absolute=True,
    )
