"""SoAI - Backup naming helpers [backend/app/backup/backup_naming.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
from datetime import UTC, datetime

from core.errors.exceptions import ValidationError
from core.timing.formatting import utc_now

__all__ = (
    "generate_backup_name",
    "generate_unique_backup_path",
)


def _require_utc_timestamp(timestamp: datetime | None) -> datetime:
    if timestamp is None:
        return utc_now()
    if not isinstance(timestamp, datetime):
        raise ValidationError("timestamp must be a datetime.")
    if timestamp.tzinfo is None:
        raise ValidationError("timestamp must be timezone-aware (UTC).")
    return timestamp.astimezone(UTC)


def generate_backup_name(timestamp: datetime | None = None) -> str:
    timestamp_utc = _require_utc_timestamp(timestamp)
    return f"soai_backup_{timestamp_utc.strftime('%Y%m%d_%H%M%S')}"


def generate_unique_backup_path(
    base_path: str,
    timestamp: datetime | None = None,
) -> tuple[str, str]:
    timestamp_utc = _require_utc_timestamp(timestamp)
    base_name = generate_backup_name(timestamp_utc)
    suffix = 0
    while True:
        suffix_fragment = f"_{suffix:02d}" if suffix else ""
        backup_id = f"{base_name}{suffix_fragment}"
        final_path = os.path.join(base_path, backup_id)
        part_path = f"{final_path}.part"
        if not os.path.exists(final_path) and not os.path.exists(part_path):
            return (final_path, part_path)
        suffix += 1
