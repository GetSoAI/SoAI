"""SoAI - Updater progress formatting and reporting [backend/app/updater/progress.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sys

from core.logging.protocols import LoggerProtocol
from core.progress.progress_bar import format_progress_bar

__all__ = ("report_progress",)


def report_progress(
    _logger_instance: LoggerProtocol,
    filename: str,
    downloaded_size: int,
    total_size: int,
    last_reported_percent: int,
) -> int:
    if total_size <= 0:
        return last_reported_percent
    current_percent = min(100, int(downloaded_size / total_size * 100))
    if current_percent > last_reported_percent:
        progress_bar_str = format_progress_bar(
            current_percent,
            downloaded_size / 1024**2,
            total_size / 1024**2,
        )
        sys.stdout.write(f"\rDownloading {filename} {progress_bar_str}")
        sys.stdout.flush()
        if current_percent == 100:
            sys.stdout.write("\n")
        return current_percent
    return last_reported_percent
