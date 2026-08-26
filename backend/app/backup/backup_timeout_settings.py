"""SoAI - Backup timeout and threshold settings [backend/app/backup/backup_timeout_settings.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import math

from app.backup.internal_protocols import ConfigProviderProtocol
from core.config.numeric_lenient import coerce_positive_timeout_seconds

__all__ = (
    "get_backup_retry_base_seconds",
    "get_backup_retry_max_seconds",
    "get_config_lock_timeout_seconds",
    "get_export_lock_timeout_seconds",
    "get_operations_lock_timeout_seconds",
    "get_orphan_age_threshold_hours",
    "get_plugin_lock_timeout_seconds",
    "get_positive_float_config",
    "get_sqlite_backup_timeout_seconds",
    "get_sqlite_backup_timeout_seconds_per_gib",
    "get_stale_part_threshold_seconds",
)


def get_positive_float_config(
    config: ConfigProviderProtocol,
    config_key: str,
    default_value: float,
    *,
    multiplier: float = 1.0,
) -> float:
    raw_value = config.get(config_key, default_value)
    timeout_seconds = coerce_positive_timeout_seconds(raw_value, default=default_value)
    multiplier_value = coerce_positive_timeout_seconds(multiplier, default=1.0)
    scaled_timeout_seconds = timeout_seconds * multiplier_value
    if math.isfinite(scaled_timeout_seconds) and scaled_timeout_seconds > 0:
        return scaled_timeout_seconds
    fallback_timeout_seconds = coerce_positive_timeout_seconds(default_value, default=1.0)
    fallback_scaled_timeout_seconds = fallback_timeout_seconds * multiplier_value
    if math.isfinite(fallback_scaled_timeout_seconds) and fallback_scaled_timeout_seconds > 0:
        return fallback_scaled_timeout_seconds
    return 1.0


def get_sqlite_backup_timeout_seconds(config: ConfigProviderProtocol) -> float:
    return get_positive_float_config(config, "DATA.BACKUP.SQLITE_BACKUP_TIMEOUT_SECONDS", 3600.0)


def get_sqlite_backup_timeout_seconds_per_gib(config: ConfigProviderProtocol) -> float:
    return get_positive_float_config(
        config,
        "DATA.BACKUP.SQLITE_BACKUP_TIMEOUT_SECONDS_PER_GIB",
        900.0,
    )


def get_config_lock_timeout_seconds(config: ConfigProviderProtocol) -> float:
    return get_positive_float_config(config, "DATA.BACKUP.CONFIG_LOCK_TIMEOUT_SECONDS", 30.0)


def get_plugin_lock_timeout_seconds(config: ConfigProviderProtocol) -> float:
    return get_positive_float_config(config, "DATA.BACKUP.PLUGIN_LOCK_TIMEOUT_SECONDS", 15.0)


def get_operations_lock_timeout_seconds(config: ConfigProviderProtocol) -> float:
    return get_positive_float_config(config, "DATA.BACKUP.OPERATIONS_LOCK_TIMEOUT_SECONDS", 300.0)


def get_export_lock_timeout_seconds(config: ConfigProviderProtocol) -> float:
    return get_positive_float_config(config, "DATA.BACKUP.EXPORT_LOCK_TIMEOUT_SECONDS", 5.0)


def get_backup_retry_base_seconds(config: ConfigProviderProtocol) -> float:
    return get_positive_float_config(config, "DATA.BACKUP.SCHEDULE.RETRY_BASE_SECONDS", 60.0)


def get_backup_retry_max_seconds(config: ConfigProviderProtocol) -> float:
    return get_positive_float_config(config, "DATA.BACKUP.SCHEDULE.RETRY_MAX_SECONDS", 1800.0)


def get_stale_part_threshold_seconds(config: ConfigProviderProtocol) -> float:
    return get_positive_float_config(
        config,
        "DATA.BACKUP.RETENTION.STALE_PART_THRESHOLD_HOURS",
        1.0,
        multiplier=3600.0,
    )


def get_orphan_age_threshold_hours(config: ConfigProviderProtocol) -> float:
    return get_positive_float_config(config, "DATA.BACKUP.RETENTION.ORPHAN_AGE_HOURS", 168.0)
