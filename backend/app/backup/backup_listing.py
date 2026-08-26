"""SoAI - Backup listing helpers [backend/app/backup/backup_listing.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from app.backup.backup_retention import list_completed_backups
from core.logging.rate_limited_logger import RateLimitedLogger
from core.logging.trace import get_logger

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("build_backup_listing",)

LOGGER_NAME = "SoAI.app.backup.backup_listing"


async def build_backup_listing(
    backups_path: str,
    invalid_manifest_log_limiter: RateLimitedLogger,
) -> list[JSONDict]:
    backups = await list_completed_backups(backups_path=backups_path)
    result: list[JSONDict] = []
    invalid_manifest_count = 0
    for backup_path, timestamp_ms, manifest in backups:
        backup_id = os.path.basename(backup_path)
        recovery = manifest.get("licensing_recovery")
        if not isinstance(recovery, dict) or recovery.get("state") not in {
            "not_applicable",
            "complete",
            "incomplete",
        }:
            invalid_manifest_count += 1
            continue
        result.append(
            {
                "backup_id": backup_id,
                "timestamp_ms": timestamp_ms,
                "timestamp_iso": manifest.get("timestamp_iso"),
                "total_size_bytes": manifest.get("total_size_bytes", 0),
                "soai_version": manifest.get("soai_version"),
                "targets_enabled": manifest.get("targets_enabled", {}),
                "targets_completed": manifest.get("targets_completed", {}),
                "licensing_recovery_state": recovery["state"],
            },
        )

    if invalid_manifest_count:
        should_log, suppressed_count = invalid_manifest_log_limiter.should_emit()
        if should_log:
            get_logger(LOGGER_NAME).warning(
                "Excluded %d invalid backup manifests from listing (suppressed=%d).",
                invalid_manifest_count,
                suppressed_count,
            )

    def _sort_timestamp(item: JSONDict) -> float:
        timestamp_value = item.get("timestamp_ms")
        if isinstance(timestamp_value, int | float) and not isinstance(timestamp_value, bool):
            return float(timestamp_value)
        return 0.0

    return sorted(result, key=_sort_timestamp, reverse=True)
