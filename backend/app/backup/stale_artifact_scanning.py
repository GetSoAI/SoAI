"""SoAI - Backup artifact stale path discovery by mtime [backend/app/backup/stale_artifact_scanning.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
from collections.abc import Callable

__all__ = ("sync_collect_stale_paths_by_mtime",)


def sync_collect_stale_paths_by_mtime(
    parent: str,
    *,
    now_seconds: float,
    max_age_seconds: float,
    include_entry: Callable[[os.DirEntry[str]], bool] | None = None,
) -> list[str]:
    expired: list[str] = []
    with os.scandir(parent) as it:
        for entry in it:
            if include_entry is not None and not include_entry(entry):
                continue
            try:
                stat_info = entry.stat(follow_symlinks=False)
            except FileNotFoundError:
                continue
            age_seconds = now_seconds - float(stat_info.st_mtime)
            if age_seconds <= max_age_seconds:
                continue
            expired.append(entry.path)
    return expired
