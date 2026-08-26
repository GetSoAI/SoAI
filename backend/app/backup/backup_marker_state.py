"""SoAI - Backup marker state helpers [backend/app/backup/backup_marker_state.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import os

from app.backup.archive_io import read_first_backup_marker
from app.backup.backup_target_paths import (
    all_enabled_targets_completed,
    get_enabled_backup_targets,
)
from app.backup.internal_protocols import ConfigProviderProtocol
from core.types.json import JSONDict, JSONValue
from core.types.json_value import coerce_json_dict

__all__ = ("load_initial_backup_marker_state",)


async def load_initial_backup_marker_state(
    backups_path: str,
    config: ConfigProviderProtocol,
) -> tuple[str, dict[str, bool], bool]:
    marker_path = os.path.join(backups_path, ".first_backup_complete")
    existing_marker = await asyncio.to_thread(
        read_first_backup_marker,
        marker_path,
    )
    empty_targets: JSONDict = {}
    previously_completed_raw: JSONValue = (
        existing_marker.get("targets_completed", empty_targets)
        if existing_marker
        else empty_targets
    )
    previously_completed_mapping = coerce_json_dict(previously_completed_raw)
    previously_completed: dict[str, bool] = {}
    if previously_completed_mapping is not None:
        for key, value in previously_completed_mapping.items():
            if isinstance(value, bool):
                previously_completed[key] = value
    all_targets_previously_completed = (
        existing_marker is not None
        and all_enabled_targets_completed(
            get_enabled_backup_targets(config),
            previously_completed,
        )
    )
    return marker_path, previously_completed, all_targets_previously_completed
