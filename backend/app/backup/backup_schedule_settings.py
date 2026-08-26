"""SoAI - Backup schedule configuration helpers [backend/app/backup/backup_schedule_settings.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from app.backup.internal_protocols import ConfigProviderProtocol
from core.validation.booleans import parse_bool

__all__ = ("resolve_backup_schedule_settings",)


def resolve_backup_schedule_settings(
    config: ConfigProviderProtocol,
) -> tuple[float | None, bool]:
    interval_value = config.get("DATA.BACKUP.SCHEDULE.INTERVAL_HOURS", 24)
    if (
        isinstance(interval_value, int | float)
        and not isinstance(interval_value, bool)
        and interval_value > 0
    ):
        interval_hours = float(interval_value)
    else:
        interval_hours = None
    run_on_startup = parse_bool(
        config.get("DATA.BACKUP.SCHEDULE.RUN_ON_STARTUP", False),
        default=False,
    )
    return interval_hours, run_on_startup
