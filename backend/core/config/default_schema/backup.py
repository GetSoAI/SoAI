"""SoAI - Default config schema: backup [backend/core/config/default_schema/backup.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.config.value_types import ConfigDict

__all__ = ("build_backup_defaults",)


def build_backup_defaults() -> ConfigDict:
    return {
        "BACKUP": {
            "ENABLED": True,
            "BACKUPS_PATH": "backups",
            "SQLITE_BACKUP_TIMEOUT_SECONDS": 3600,
            "SQLITE_BACKUP_TIMEOUT_SECONDS_PER_GIB": 900,
            "CONFIG_LOCK_TIMEOUT_SECONDS": 30,
            "PLUGIN_LOCK_TIMEOUT_SECONDS": 15,
            "OPERATIONS_LOCK_TIMEOUT_SECONDS": 300,
            "EXPORT_LOCK_TIMEOUT_SECONDS": 5,
            "RESTORE_COPY_TIMEOUT_SECONDS": 1800,
            "RESTORE_PROGRESS_INTERVAL_SECONDS": 2.0,
            "SCHEDULE": {
                "INTERVAL_HOURS": 24,
                "RUN_ON_STARTUP": False,
                "ON_SHUTDOWN": False,
                "ON_SHUTDOWN_TIMEOUT_SEC": 120,
                "RETRY_BASE_SECONDS": 60,
                "RETRY_MAX_SECONDS": 1800,
            },
            "RETENTION": {
                "MAX_BACKUPS": 7,
                "MAX_AGE_HOURS": 720,
                "STALE_PART_THRESHOLD_HOURS": 1,
                "ORPHAN_AGE_HOURS": 168,
            },
            "TARGETS": {
                "DATABASE": True,
                "CONFIG": True,
                "ENCRYPTION_KEY": True,
                "PLUGIN_CONFIGS": True,
                "USER_DATA": True,
                "GPU_SETTINGS": True,
                "LOGS": False,
            },
        },
    }
